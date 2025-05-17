import subprocess
import time
import requests
import json
import os
import logging
import socketio as socketio_client
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import func
from extensions import celery_app as celery, socketio
from models import CommandExecution
import re

# Try to import flag_modified, but provide a fallback if it doesn't exist
try:
    from sqlalchemy.orm import flag_modified
    has_flag_modified = True
except ImportError:
    has_flag_modified = False
    # Define a simple replacement function that will work with older SQLAlchemy versions
    def flag_attribute_modified(obj, attr_name):
        """Mark an attribute as modified on an object manually."""
        try:
            # Standard SQLAlchemy approach
            obj._sa_instance_state.modified.add(attr_name)
        except (AttributeError, TypeError):
            # Fallback for when modified is not a set or doesn't have add method
            # Just force a commit with the current value to ensure it's saved
            logger.warning(f"Couldn't directly mark attribute '{attr_name}' as modified, using alternative approach")
            try:
                # For SQLAlchemy >= 1.4
                from sqlalchemy import inspect
                insp = inspect(obj)
                if hasattr(insp, "add_attribute_change"):
                    insp.add_attribute_change(attr_name, None, getattr(obj, attr_name, None))
                    return True
            except (ImportError, AttributeError):
                pass
            
            # Last resort: just touch the attribute to make SQLAlchemy notice the change
            current_value = getattr(obj, attr_name, None)
            setattr(obj, attr_name, current_value)
        return True

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

# Create a direct SQLAlchemy engine
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///data/hermes_lite.db')
engine = create_engine(DATABASE_URL)
SessionFactory = sessionmaker(bind=engine)

# SocketIO client for workers
sio_client = None
SOCKETIO_READY = False

def init_socketio_client():
    """Initialize a socketio client that workers can use to communicate with the Flask app."""
    global sio_client
    global SOCKETIO_READY
    
    try:
        # Create a new socket.io client
        sio_client = socketio_client.Client(
            logger=False,
            engineio_logger=False,
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=1,
            reconnection_delay_max=5,
            randomization_factor=0.5
        )
        
        # Define event handlers
        @sio_client.event(namespace='/realtime')
        def connect():
            global SOCKETIO_READY
            logger.info(f"Worker {os.environ.get('WORKER_NAME', 'worker')}: Connected to SocketIO server")
            SOCKETIO_READY = True

        @sio_client.event(namespace='/realtime')
        def connect_error(data):
            global SOCKETIO_READY
            logger.error(f"Worker {os.environ.get('WORKER_NAME', 'worker')}: Connection error to SocketIO server: {data}")
            SOCKETIO_READY = False

        @sio_client.event(namespace='/realtime')
        def disconnect():
            global SOCKETIO_READY
            logger.warning(f"Worker {os.environ.get('WORKER_NAME', 'worker')}: Disconnected from SocketIO server")
            SOCKETIO_READY = False
        
        @sio_client.event(namespace='/realtime')
        def welcome(data):
            logger.info(f"Worker received welcome message: {data}")
        
        # Connect to the Flask app's socket.io server
        server_url = os.environ.get('SOCKETIO_SERVER', 'http://web:5000')
        logger.info(f"Worker {os.environ.get('WORKER_NAME', 'worker')}: Connecting to Socket.IO server at {server_url}")
        sio_client.connect(
            server_url,
            namespaces=['/realtime'],
            transports=['websocket'],
            wait=True
        )
        
        return True
    except Exception as e:
        logger.error(f"Error initializing Socket.IO client: {e}")
        SOCKETIO_READY = False
        return False

def safe_emit(event, data, execution_id=None):
    """Safely emit a socket.io event, with fallback mechanisms."""
    global sio_client
    global SOCKETIO_READY
    
    # Get the room name for this execution
    room = f"exec_{execution_id}" if execution_id else None
    
    # Add metadata to the event
    data.update({
        'source': f"worker_{os.environ.get('WORKER_NAME', 'worker')}",
        'event_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'from_client': True
    })
    
    # Try using the client socket.io connection 
    if SOCKETIO_READY and sio_client:
        try:
            sio_client.emit(event, data, namespace='/realtime')
            return True
        except Exception as e:
            logger.error(f"Error emitting {event} via client: {e}")
            SOCKETIO_READY = False
    
    # If we have execution_id but socket.io isn't ready, try using server-side socketio
    if execution_id and not SOCKETIO_READY:
        try:
            if socketio:
                socketio.emit(event, data, namespace='/realtime', room=room)
                return True
        except Exception as e:
            logger.error(f"Error emitting using server-side socketio: {e}")
    
    # Try to reconnect the client if it's not ready
    if not SOCKETIO_READY or not sio_client:
        logger.warning(f"Worker {os.environ.get('WORKER_NAME', 'worker')}: Socket.IO not available for emitting")
        success = init_socketio_client()
        
        if success and execution_id:
            try:
                sio_client.emit('join', {'execution_id': execution_id}, namespace='/realtime')
                sio_client.emit(event, data, namespace='/realtime')
                return True
            except Exception as e:
                logger.error(f"Error joining room after reconnect: {e}")
    
    # Persist error in database if we have an execution ID
    if execution_id:
        try:
            Session = scoped_session(SessionFactory)
            session = Session()
            execution = session.query(CommandExecution).filter_by(id=execution_id).first()
            if execution:
                execution.output += f"\n[ERROR] Failed to stream output in real-time"
                session.commit()
        except Exception as db_error:
            logger.error(f"Error updating execution record: {db_error}")
        finally:
            Session.remove()
    
    return False

# Attempt to initialize the socketio client when this module is imported
try:
    init_socketio_client()
except Exception as e:
    logger.error(f"Failed to initialize SocketIO client on module import: {e}")

@celery.task(name="execute_command")
def execute_command(execution_id, command_name, target_host, params=None, user=None):
    """Execute a command on a target host."""
    if params is None:
        params = []
    
    Session = scoped_session(SessionFactory)
    session = Session()
    
    try:
        # Get the execution record
        execution = session.query(CommandExecution).filter_by(id=execution_id).first()
        
        if execution:
            # Update the execution status
            execution.status = 'running'
            execution.start_time = func.now()
            session.commit()
            
            # Make API call to the agent on the target host
            agent_url = f"http://{target_host}:9000/execute"
            payload = {
                'command_name': command_name,
                'params': params,
                'execution_id': str(execution_id)
            }
            
            response = requests.post(agent_url, json=payload, stream=True)
            
            # Stream response back for real-time feedback
            if response.status_code == 200:
                # Mark the beginning of streaming
                streaming_message = f"Starting execution of command: {command_name}"
                safe_emit('execution_output', 
                          {'execution_id': execution_id, 'output_line': streaming_message}, 
                          execution_id=execution_id)

                # Update execution with streaming message
                execution.output = streaming_message + "\n"
                session.commit()
                
                # Process streaming response
                exit_code = None
                exit_code_pattern = re.compile(r'\[EXIT_CODE:(\d+)\]')
                
                for line in response.iter_lines(decode_unicode=True):
                    if line:
                        # Check if this line contains an exit code
                        exit_code_match = exit_code_pattern.search(line)
                        if exit_code_match:
                            exit_code = int(exit_code_match.group(1))
                            logger.info(f"Extracted exit code {exit_code} from output")
                        
                        # Add line to execution output
                        if execution.output:
                            execution.output += f"\n{line}"
                        else:
                            execution.output = line
                            
                        # Use flag_modified if available for SQLAlchemy ORM
                        if has_flag_modified:
                            flag_modified(execution, 'output')
                        else:
                            flag_attribute_modified(execution, 'output')
                        
                        session.commit()
                        
                        # Emit to socket.io for real-time updates
                        safe_emit('execution_output', 
                                  {'execution_id': execution_id, 'output_line': line}, 
                                  execution_id=execution_id)
                
                # Update execution status to success
                execution.status = 'success'
                execution.end_time = func.now()
                
                # Set exit code (may have been parsed from output or set here)
                if exit_code is not None:
                    execution.exit_code = exit_code
                else:
                    execution.exit_code = 0
                    
                session.commit()
                
                # Emit completion update
                complete_data = {
                    'execution_id': execution_id, 
                    'status': 'success',
                    'end_time': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                safe_emit('execution_update', complete_data, execution_id=execution_id)
                
                return True
            else:
                error_message = f"[ERROR] Request to agent failed with status code: {response.status_code}, response: {response.text}"
                logger.error(error_message)
                
                # Update execution status to failed
                execution.status = 'failure'
                execution.output += f"\n{error_message}"
                execution.end_time = func.now()
                execution.exit_code = 1  # Non-zero exit code for failures
                session.commit()
                
                # Emit failure update
                error_data = {
                    'execution_id': execution_id, 
                    'status': 'failure',
                    'error': error_message
                }
                safe_emit('execution_update', error_data, execution_id=execution_id)
                
                return False
        else:
            logger.error(f"Execution with ID {execution_id} not found")
            return False
            
    except Exception as e:
        error_message = f"[ERROR] Failed to execute command: {str(e)}"
        logger.error(error_message)
        
        try:
            # Update execution status to failed
            if 'execution' in locals() and execution:
                execution.status = 'failure'
                execution.output += f"\n{error_message}"
                execution.end_time = func.now()
                execution.exit_code = 1  # Non-zero exit code for failures
                session.commit()
                
                # Emit failure update
                error_data = {
                    'execution_id': execution_id, 
                    'status': 'failure',
                    'error': error_message
                }
                safe_emit('execution_update', error_data, execution_id=execution_id)
        except Exception as save_error:
            logger.error(f"[ERROR] Failed to update execution record: {save_error}")
        
        return False
    finally:
        if 'Session' in locals():
            Session.remove()
