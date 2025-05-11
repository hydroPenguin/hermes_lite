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
        
        # Emit status update event
        safe_emit(
            'execution_update',
            {
                'execution_id': execution_id,
                'status': 'running'
            }
        )

        # Send request to the agent on the target host
        agent_url = f"http://{target_host}:9000/execute"
        payload = {
            "command_name": command_name,
            "params": params
        }
        
        # Enable streaming for shell scripts to ensure proper output handling
        if command_name.endswith(".sh"):
            payload["stream_output"] = True
        
        print(f"Sending request to agent at {agent_url} with payload: {payload}")
        
        # Emit update that request is being sent
        safe_emit(
            'execution_output',
            {
                'execution_id': execution_id,
                'output_line': f"[{time.strftime('%H:%M:%S')}] Sending request to agent with command: {command_name}"
            }
        )
        
        # Use streaming requests session to get real-time response chunks
        with requests.Session() as http_session:
            try:
                # Use streaming=True to get content as it comes
                response = http_session.post(
                    agent_url,
                    json=payload,
                    timeout=180,  # 3-minute timeout for long-running tasks
                    stream=True
                )
                
                # Check initial response status code
                if response.status_code != 200:
                    error_msg = f"Agent returned error: {response.status_code} - {response.text}"
                    safe_emit(
                        'execution_output',
                        {
                            'execution_id': execution_id,
                            'output_line': f"[ERROR] {error_msg}"
                        }
                    )
                    raise RuntimeError(error_msg)
                
                # Initialize result with default values in case streaming fails
                result = {
                    'stdout': '',
                    'stderr': '',
                    'exit_code': -1
                }
                
                # Stream response content if available and possible
                response_consumed = False
                if hasattr(response, 'iter_lines'):
                    # For agents that support streaming responses
                    json_data = None
                    collected_output = []  # Collect all streamed output lines
                    response_consumed = True  # Mark that we've consumed the response
                    
                    # Emit start of streaming message
                    safe_emit(
                        'execution_output',
                        {
                            'execution_id': execution_id,
                            'output_line': f"[{time.strftime('%H:%M:%S')}] [STREAMING] Started streaming output for command: {command_name}"
                        }
                    )
                    
                    last_line_time = time.time()
                    
                    # Process streaming response line by line
                    for line in response.iter_lines():
                        if line:
                            line_text = line.decode('utf-8')
                            last_line_time = time.time()
                            
                            # Check if this is the final JSON data marker
                            if line_text.startswith('JSON_COMPLETE:'):
                                try:
                                    json_data = json.loads(line_text.replace('JSON_COMPLETE:', '', 1))
                                    # Indicate we received the complete data
                                    safe_emit(
                                        'execution_output',
                                        {
                                            'execution_id': execution_id,
                                            'output_line': f"[{time.strftime('%H:%M:%S')}] [INFO] Received complete output data"
                                        }
                                    )
                                    continue  # Skip emitting this line
                                except json.JSONDecodeError:
                                    pass  # If we can't parse it, treat as normal line
                            
                            # Skip empty heartbeat lines
                            if line_text.strip() == "":
                                continue
                                
                            # Collect output for DB storage
                            collected_output.append(line_text)
                            
                            # Emit the line in real-time
                            safe_emit(
                                'execution_output',
                                {
                                    'execution_id': execution_id,
                                    'output_line': line_text
                                }
                            )
                        else:
                            # If no data for a while, send a keepalive message
                            if time.time() - last_line_time > 10:
                                safe_emit(
                                    'execution_output',
                                    {
                                        'execution_id': execution_id,
                                        'output_line': f"[{time.strftime('%H:%M:%S')}] [INFO] Still executing..."
                                    }
                                )
                                last_line_time = time.time()
                    
                    # If we received JSON data at the end, use it
                    if json_data:
                        result = json_data
                        # If JSON data doesn't include full output but we collected it, add it
                        if not result.get('stdout') and collected_output:
                            result['stdout'] = '\n'.join(collected_output)
                    # If no JSON data but we collected output, create a result
                    elif collected_output:
                        result = {
                            'stdout': '\n'.join(collected_output),
                            'stderr': '',
                            'exit_code': 0  # Assume success if we got output
                        }
                    else:
                        # No JSON data and no collected output - something might be wrong
                        result = {
                            'stdout': 'No output received from command',
                            'stderr': '',
                            'exit_code': -1
                        }
                
                # Get the final JSON result if not already parsed from streaming
                if not response_consumed:
                    try:
                        result = response.json()
                    except (json.JSONDecodeError, RuntimeError) as e:
                        # If we can't parse JSON or content was already consumed
                        logger.warning(f"Error decoding response: {str(e)}")
                        try:
                            # Try to get content if not already consumed
                            result = {
                                'stdout': response.text if hasattr(response, 'text') else str(e),
                                'stderr': f"Error processing response: {str(e)}",
                                'exit_code': -1
                            }
                        except RuntimeError:
                            # Content was already consumed
                            result = {
                                'stdout': str(e),
                                'stderr': f"Error processing response: {str(e)}",
                                'exit_code': -1
                            }
            
            except requests.RequestException as e:
                error_msg = f"Request to agent failed: {str(e)}"
                safe_emit(
                    'execution_output',
                    {
                        'execution_id': execution_id,
                        'output_line': f"[ERROR] {error_msg}"
                    }
                )
                raise RuntimeError(error_msg)
        
        # Extract results
        stdout = result.get('stdout', '')
        stderr = result.get('stderr', '')
        exit_code = result.get('exit_code', -1)
        
        # Emit final output if not already streamed
        if stdout and not hasattr(response, 'iter_lines'):
            # Split by lines to make it more readable in UI
            for line in stdout.split('\n'):
                if line.strip():  # Only emit non-empty lines
                    safe_emit(
                        'execution_output',
                        {
                            'execution_id': execution_id,
                            'output_line': line
                        }
                    )
        
        # Emit any stderr
        if stderr:
            safe_emit(
                'execution_output',
                {
                    'execution_id': execution_id,
                    'output_line': f"[STDERR] {stderr}"
                }
            )

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
