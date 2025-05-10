from celery import Celery
from app import create_app, db  # Import Flask app and db
from models import CommandExecution
import subprocess
import time
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

# Create Celery app
celery = Celery('tasks', broker='amqp://user:password@rabbitmq:5672//')

# Initialize Celery with Flask app context
def init_celery(app):
    celery.config_from_object(app.config)
    celery.conf.update(
        {
            "worker_tmp_dir": "/tmp",  # Needed for some tasks
            "worker_log_format": "[%(asctime)s: %(levelname)s] %(message)s",
            "worker_task_log_format": "[%(asctime)s: %(levelname)s] %(message)s",
        }
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                self.Session = scoped_session(sessionmaker(bind=db.engine)) # Use scoped_session
                return self.run(*args, **kwargs)

        def after_return(self, *args, **kwargs):
            self.Session.remove()

    celery.Task = ContextTask
    return celery

# Create a Flask app instance for Celery to use
flask_app = create_app()  # You'll need to define this function in app.py
celery = init_celery(flask_app)

@celery.task(bind=True)  # 'bind=True' for access to self
def execute_command(self, execution_id, command_name, target_host, params, user):
    """
    Executes the command on the target host using subprocess (simulated).
    """
    #  Get the db session.
    session = self.Session

    # Simulate command execution (replace with your actual execution logic)
    try:
        # Get the CommandExecution object from the database
        execution = session.get(CommandExecution, execution_id)  # Use get
        if not execution:
            raise Exception(f"Execution record with id {execution_id} not found")

        # Update status to running
        execution.status = 'running'
        session.commit()

        # Construct the command (same as in your agent.py)
        if command_name.endswith(".sh"):
            full_command = ['/bin/sh', f'/agent_files/predefined_commands/{command_name}'] + params
        else:
            full_command = [f'/agent_files/predefined_commands/{command_name}'] + params

        # Simulate streaming output (replace with actual subprocess)
        process = subprocess.Popen(full_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        while True:
            line = process.stdout.readline()
            if not line:
                break
            # Use Socket.IO to send output to the client in real-time
            #  This requires a running SocketIO server (see app.py)
            from app import socketio  # Import socketio instance
            socketio.emit('output', {'execution_id': execution_id, 'output': line}, namespace='/realtime')
            time.sleep(0.1)  # Simulate a short delay

        # Get final output and error
        stdout, stderr = process.communicate()
        exit_code = process.returncode

        # Update database with results
        execution.output = stdout
        execution.error = stderr
        execution.exit_code = exit_code
        execution.end_time = func.now()

        if exit_code == 0:
            execution.status = 'success'
        else:
            execution.status = 'failure'
        session.commit()

        return {
            'status': execution.status,
            'output': stdout,
            'error': stderr,
            'exit_code': exit_code,
            'execution_id': execution_id
        }
    except Exception as e:
        # Handle exceptions robustly.  Log the error.  Update the database.
        error_message = str(e)
        print(f"Error in execute_command: {error_message}") # Log
        if execution: # execution might not be defined if error occurs before DB entry
            execution.status = 'failure'
            execution.end_time = func.now()
            execution.error = error_message
            session.commit()
        return {
            'status': 'failure',
            'error': error_message,
            'execution_id': execution_id
        }
    finally:
        session.close()
