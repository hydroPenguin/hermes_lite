import subprocess
import time
import requests
import json
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import func
from extensions import celery_app as celery, socketio
from models import CommandExecution

# Set up logging
logger = logging.getLogger(__name__)

# Create a direct SQLAlchemy engine
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///data/hermes_lite.db')
engine = create_engine(DATABASE_URL)
SessionFactory = sessionmaker(bind=engine)

# Safe SocketIO emitter that won't fail if SocketIO is not available
def safe_emit(event, data, namespace='/realtime'):
    """Safely emit a SocketIO event, handling the case where SocketIO is not available."""
    try:
        if socketio and hasattr(socketio, 'server') and socketio.server:
            socketio.emit(event, data, namespace=namespace)
            return True
    except Exception as e:
        logger.warning(f"Could not emit {event} event: {str(e)}")
        print(f"Could not emit {event} event: {str(e)}")
    return False

@celery.task(bind=True, name='extensions.execute_command')
def execute_command(self, execution_id, command_name, target_host, params, user):
    """
    Executes a predefined command on the target host, streams output via Socket.IO,
    and updates the database record with status, output, and timing.
    """
    # Create a session directly with SQLAlchemy
    session = SessionFactory()

    try:
        # Fetch the execution record
        exe = session.query(CommandExecution).filter_by(id=execution_id).first()
        if not exe:
            raise RuntimeError(f"Execution record {execution_id} not found")

        # Mark as running
        exe.status = 'running'
        session.commit()

        # Send request to the agent on the target host
        agent_url = f"http://{target_host}:9000/execute"
        payload = {
            "command_name": command_name,
            "params": params
        }
        
        print(f"Sending request to agent at {agent_url} with payload: {payload}")
        
        response = requests.post(
            agent_url,
            json=payload,
            timeout=120  # 2-minute timeout
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Agent returned error: {response.status_code} - {response.text}")
        
        result = response.json()
        print(f"Agent response: {result}")
        
        # Extract results
        stdout = result.get('stdout', '')
        stderr = result.get('stderr', '')
        exit_code = result.get('exit_code', -1)

        # Update execution record
        exe.output = stdout
        exe.error = stderr
        exe.exit_code = exit_code
        exe.end_time = func.now()
        exe.status = 'success' if exit_code == 0 else 'failure'
        session.commit()

        # Emit completion event (safely)
        safe_emit(
            'execution_complete',
            {
                'execution_id': execution_id,
                'status': exe.status,
                'exit_code': exit_code
            }
        )

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
            
            # Emit error event (safely)
            safe_emit(
                'execution_error',
                {
                    'execution_id': execution_id,
                    'error': err_msg
                }
            )
            
        return {
            'status': 'failure',
            'error': err_msg,
            'execution_id': execution_id
        }

    finally:
        # Clean up the session
        session.close()
