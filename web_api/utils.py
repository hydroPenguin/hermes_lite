import paramiko
import yaml
import json
import os
from typing import Dict, Any, Generator, Optional
from datetime import datetime

class CommandExecutor:
    def __init__(self, host: str, port: int = 22, username: str = None, key_path: str = None):
        self.host = host
        self.port = port
        self.username = username
        self.key_path = key_path
        self.client = None
        
    def connect(self) -> None:
        """Establish SSH connection to the host."""
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        if self.key_path:
            key = paramiko.RSAKey.from_private_key_file(self.key_path)
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                pkey=key
            )
        else:
            # For demo purposes, using password authentication
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=os.getenv('SSH_PASSWORD')
            )
    
    def execute_command(self, command: str, timeout: int = 30) -> Generator[str, None, None]:
        """Execute a command and yield output in real-time."""
        if not self.client:
            self.connect()
            
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        
        # Yield output in real-time
        for line in stdout:
            yield line.strip()
            
        # Check for errors
        error = stderr.read().decode()
        if error:
            yield f"Error: {error}"
            
    def close(self) -> None:
        """Close the SSH connection."""
        if self.client:
            self.client.close()
            
    @staticmethod
    def load_commands() -> Dict[str, Any]:
        """Load command definitions from YAML file."""
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'commands.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
            
    @staticmethod
    def format_command(command_template: str, parameters: Dict[str, Any]) -> str:
        """Format command template with parameters."""
        try:
            return command_template.format(**parameters)
        except KeyError as e:
            raise ValueError(f"Missing required parameter: {e}")
            
    @staticmethod
    def validate_parameters(command_def: Dict[str, Any], parameters: Dict[str, Any]) -> None:
        """Validate command parameters against definition."""
        required_params = {p['name'] for p in command_def.get('required_params', [])}
        provided_params = set(parameters.keys())
        
        missing_params = required_params - provided_params
        if missing_params:
            raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")
