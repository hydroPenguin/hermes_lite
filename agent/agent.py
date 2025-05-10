# agent/agent.py
import subprocess
import os
from flask import Flask, request, jsonify

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
    # We explicitly call 'sh' for .sh files for better control and portability.
    # This also helps if the +x bit wasn't set correctly.
    if command_name.endswith(".sh"):
        full_command = ['/bin/sh', normalized_script_path] + params
    else:
        # For other types of executables, you might need different handling
        # For now, we assume .sh or direct executables that are on PATH or have +x
        full_command = [normalized_script_path] + params


    app.logger.info(f"Executing command: {' '.join(full_command)}")

    try:
        # Execute the command
        # Using Popen for better control over streams if needed in future (e.g. streaming output)
        process = subprocess.Popen(
            full_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True # Decodes stdout/stderr to strings
        )
        stdout, stderr = process.communicate(timeout=60) # Add a timeout
        exit_code = process.returncode

        app.logger.info(f"Command '{command_name}' completed with exit code {exit_code}")
        app.logger.debug(f"Stdout: {stdout}")
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

if __name__ == '__main__':
    app.logger.info(f"Starting Hermes Agent on port {AGENT_PORT}...")
    app.logger.info(f"Predefined commands directory: {PREDEFINED_COMMANDS_DIR}")
    # Check if predefined commands dir exists and list files
    if os.path.exists(PREDEFINED_COMMANDS_DIR):
        app.logger.info(f"Available scripts: {os.listdir(PREDEFINED_COMMANDS_DIR)}")
    else:
        app.logger.error(f"Predefined commands directory {PREDEFINED_COMMANDS_DIR} not found!")

    # Make sure 0.0.0.0 is used to be accessible from other Docker containers
    app.run(host='0.0.0.0', port=AGENT_PORT, debug=True)
