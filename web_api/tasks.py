import subprocess
import time
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import func
from extensions import celery_app as celery, db, socketio
from models import CommandExecution

@celery.task(bind=True)
def execute_command(self, execution_id, command_name, target_host, params, user):
    """
    Executes a predefined command on the target host, streams output via Socket.IO,
    and updates the database record with status, output, and timing.
    """
    # Create a new session bound to our SQLAlchemy engine
    Session = scoped_session(sessionmaker(bind=db.engine))
    session = Session()

    try:
        # Fetch the execution record
        exe = session.get(CommandExecution, execution_id)
        if not exe:
            raise RuntimeError(f"Execution record {execution_id} not found")

        # Mark as running
        exe.status = 'running'
        session.commit()

        # Build command
        if command_name.endswith('.sh'):
            cmd = ['/bin/sh', f'/agent_files/predefined_commands/{command_name}'] + params
        else:
            cmd = [f'/agent_files/predefined_commands/{command_name}'] + params

        # Launch subprocess
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Stream stdout lines
        for line in process.stdout:
            socketio.emit(
                'output',
                {'execution_id': execution_id, 'output': line},
                namespace='/realtime'
            )
            time.sleep(0.1)

        # Wait for completion and capture remaining output and errors
        stdout, stderr = process.communicate()
        exit_code = process.returncode

        # Update execution record
        exe.output = stdout
        exe.error = stderr
        exe.exit_code = exit_code
        exe.end_time = func.now()
        exe.status = 'success' if exit_code == 0 else 'failure'
        session.commit()

        return {
            'status': exe.status,
            'output': stdout,
            'error': stderr,
            'exit_code': exit_code,
            'execution_id': execution_id
        }

    except Exception as e:
        # On error, update record if possible
        err_msg = str(e)
        print(f"Error in execute_command: {err_msg}")
        if 'exe' in locals():
            exe.status = 'failure'
            exe.error = err_msg
            exe.end_time = func.now()
            session.commit()
        return {
            'status': 'failure',
            'error': err_msg,
            'execution_id': execution_id
        }

    finally:
        # Clean up the session
        Session.remove()
