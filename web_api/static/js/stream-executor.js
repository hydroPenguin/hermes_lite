/**
 * Stream Executor
 * 
 * A utility to execute commands and immediately redirect to streaming output.
 * Include this file in any HTML page that needs to trigger command execution with streaming.
 */

class StreamExecutor {
    constructor() {
        this.token = localStorage.getItem('auth_token');
    }

    /**
     * Execute a command and immediately go to the streaming output page.
     * 
     * @param {string} commandName - Name of the command to execute
     * @param {string} targetHost - Name of the target host
     * @param {Array} params - Command parameters 
     * @param {Function} onError - Error callback function (optional)
     */
    executeAndStream(commandName, targetHost, params = [], onError = null) {
        // Always get the latest token from localStorage
        const token = localStorage.getItem('auth_token');
        
        if (!token) {
            const errorMsg = 'Authentication token not found. Please log in.';
            if (onError) onError(errorMsg);
            return;
        }

        const payload = {
            command_name: commandName,
            target_host: targetHost,
            params: params,
            stream_to_ui: true
        };

        fetch('/execute_command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to execute command: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.redirect && data.stream_url) {
                // Redirect to the streaming output page
                window.location.href = data.stream_url;
            } else {
                // If no redirect info, go to the regular output page
                window.location.href = `/output/${data.execution_id}`;
            }
        })
        .catch(error => {
            if (onError) onError(error.message);
        });
    }

    /**
     * Execute a long running task with streaming
     * 
     * @param {string} targetHost - Target host name
     * @param {Function} onError - Error callback
     */
    executeLongRunningTask(targetHost, onError = null) {
        this.executeAndStream('long_running_task.sh', targetHost, [], onError);
    }
}

// Create a global executor instance
window.streamExecutor = new StreamExecutor(); 