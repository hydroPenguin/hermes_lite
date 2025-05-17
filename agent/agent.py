# agent/agent.py
import subprocess
import os
import time
import threading
import queue
import json
from flask import Flask, request, jsonify, Response, stream_with_context

app = Flask(__name__)

# Configuration
# The volume mount in docker-compose.yml maps ./agent to /agent_files inside the container.
PREDEFINED_COMMANDS_DIR = "/agent_files/predefined_commands"
AGENT_PORT = int(os.environ.get("AGENT_PORT", 9000)) # Port to listen on

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for the agent."""
    return jsonify({"status": "healthy", "message": f"Agent on {os.uname()[1]} is up."}), 200

@app.route('/execute', methods=['POST'])
def execute_command():
    """
    Executes a predefined command.
    Expects JSON: {"command_name": "script_name.sh", "params": ["param1", "param2"]}
    """
    data = request.get_json()
    if not data or 'command_name' not in data:
        return jsonify({"error": "Missing 'command_name' in request"}), 400

    command_name = data['command_name']
    params = data.get('params', []) # Optional parameters for the script
    stream_output = data.get('stream_output', False) # Whether to stream real-time output

    # Security: Construct the full path and ensure it's within the predefined directory
    script_path = os.path.join(PREDEFINED_COMMANDS_DIR, command_name)

    # Normalize path to prevent directory traversal (e.g., ../../etc/passwd)
    normalized_script_path = os.path.normpath(script_path)

    if not normalized_script_path.startswith(os.path.normpath(PREDEFINED_COMMANDS_DIR) + os.sep):
        app.logger.error(f"Attempt to access non-predefined command path: {script_path}")
        return jsonify({"error": "Command not allowed or path traversal attempt"}), 403

    if not os.path.exists(normalized_script_path) or not os.path.isfile(normalized_script_path):
        app.logger.error(f"Command script not found or not a file: {normalized_script_path}")
        return jsonify({"error": f"Command '{command_name}' not found or is not a file."}), 404

    # Ensure the script is executable (Docker images might not preserve this from host)
    try:
        os.chmod(normalized_script_path, 0o755) # rwxr-xr-x
    except OSError as e:
        app.logger.error(f"Could not set executable bit on {normalized_script_path}: {e}")
        # Continue, as it might already be executable or run via sh

    # Construct the command to execute.
    if command_name.endswith(".sh"):
        full_command = ['/bin/sh', normalized_script_path] + params
    else:
        full_command = [normalized_script_path] + params

    app.logger.info(f"Executing command: {' '.join(full_command)}")
    
    # For all shell scripts or when explicitly requested, use streaming
    if command_name.endswith(".sh") or stream_output:
        return stream_command_output(full_command, command_name)
    
    # For non-shell commands, use the standard execution approach
    try:
        # Execute the command
        process = subprocess.Popen(
            full_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True # Decodes stdout/stderr to strings
        )
        stdout, stderr = process.communicate(timeout=300) # Add a timeout
        exit_code = process.returncode

        app.logger.info(f"Command '{command_name}' completed with exit code {exit_code}") 
        if stderr:
             app.logger.error(f"Stderr: {stderr}")

        return jsonify({
            "command": command_name,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code
        }), 200

    except FileNotFoundError:
        app.logger.error(f"Script {normalized_script_path} not found during Popen.")
        return jsonify({"error": f"Script {command_name} not found. Check agent logs."}), 500
    except subprocess.TimeoutExpired:
        app.logger.error(f"Command '{command_name}' timed out.")
        process.kill()
        stdout, stderr = process.communicate()
        return jsonify({
            "error": "Command timed out",
            "command": command_name,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": -1 # Or a specific timeout code
        }), 504 # Gateway Timeout might be appropriate
    except Exception as e:
        app.logger.error(f"Error executing command '{command_name}': {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

def stream_command_output(command, command_name):
    """
    Stream command output in real-time using a generator function.
    """
    def generate():
        process = None
        try:
            # Set environment variables to prevent buffering
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            
            # Start the process with unbuffered output
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,  # Unbuffered
                env=env
            )
            
            # Queue for collecting output
            output_queue = queue.Queue()
            collected_stdout = []
            collected_stderr = []
            
            # Thread function to read output streams
            def read_output(stream, output_list, stream_name):
                for line in iter(stream.readline, ''):
                    timestamp = time.strftime("%H:%M:%S")
                    formatted_line = f"[{timestamp}] [{stream_name}] {line.rstrip()}"
                    output_list.append(line)
                    output_queue.put(formatted_line)
                stream.close()
            
            # Start threads to read stdout and stderr
            stdout_thread = threading.Thread(
                target=read_output, 
                args=(process.stdout, collected_stdout, "STDOUT"),
                daemon=True
            )
            stderr_thread = threading.Thread(
                target=read_output, 
                args=(process.stderr, collected_stderr, "STDERR"),
                daemon=True
            )
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Track all emitted lines for final output
            all_emitted_lines = []
            
            # Record initial message in logs but don't send to client
            initial_message = f"[{time.strftime('%H:%M:%S')}] [INFO] Starting execution of '{command_name}'..."
            all_emitted_lines.append(initial_message)
            # Don't yield to client: yield initial_message + "\n"
            
            # Flag to track if we're showing "waiting" messages
            shown_waiting = False
            last_output_time = time.time()
            last_heartbeat_time = time.time()
            
            # Yield available output lines
            while process.poll() is None or not output_queue.empty():
                try:
                    line = output_queue.get(timeout=0.1)
                    all_emitted_lines.append(line)
                    yield line + "\n"
                    last_output_time = time.time()
                    last_heartbeat_time = time.time()
                    shown_waiting = False
                except queue.Empty:
                    current_time = time.time()
                    
                    # If it's been more than 30 seconds since last output and process is still running
                    if current_time - last_output_time > 30 and process.poll() is None and not shown_waiting:
                        # Don't yield the "Still waiting" info message, just record for logs
                        waiting_msg = f"[{time.strftime('%H:%M:%S')}] [INFO] Still waiting for output..."
                        all_emitted_lines.append(waiting_msg)
                        # Don't send to client: yield waiting_msg + "\n"
                        shown_waiting = True
                        last_heartbeat_time = current_time
                    
                    # Send a heartbeat every 10 seconds to keep the connection alive
                    if current_time - last_heartbeat_time >= 10 and process.poll() is None:
                        yield " \n"  # Space + newline keeps connection alive but doesn't display
                        last_heartbeat_time = current_time
                    
                    time.sleep(0.2) # Check more frequently
            
            # Wait for process to complete and threads to finish
            stdout_thread.join(timeout=2)
            stderr_thread.join(timeout=2)
            
            # Send final status
            exit_code = process.returncode
            final_status = f"[{time.strftime('%H:%M:%S')}] [INFO] Command '{command_name}' completed with exit code {exit_code}"
            all_emitted_lines.append(final_status)
            yield final_status + "\n"
            
            # After streaming, send the complete data as JSON
            # complete_data = {
            #     "command": command_name,
            #     "stdout": "\n".join(all_emitted_lines),  # Include all formatted output
            #     "raw_stdout": "".join(collected_stdout),  # Also include raw output
            #     "stderr": "".join(collected_stderr),
            #     "exit_code": exit_code
            # }
            
        except Exception as e:
            app.logger.error(f"Error in streaming command: {str(e)}")
            if process and process.poll() is None:
                process.kill()
            error_msg = f"[ERROR] Exception during execution: {str(e)}"
            yield error_msg + "\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/plain'
    )

if __name__ == '__main__':
    app.logger.info(f"Starting Hermes Agent on port {AGENT_PORT}...")
    app.logger.info(f"Predefined commands directory: {PREDEFINED_COMMANDS_DIR}")
    # Check if predefined commands dir exists and list files
    if os.path.exists(PREDEFINED_COMMANDS_DIR):
        app.logger.info(f"Available scripts: {os.listdir(PREDEFINED_COMMANDS_DIR)}")
    else:
        app.logger.error(f"Predefined commands directory {PREDEFINED_COMMANDS_DIR} not found!")

    # Make sure 0.0.0.0 is used to be accessible from other Docker containers
    app.run(host='0.0.0.0', port=AGENT_PORT, debug=False)
