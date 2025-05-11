# target_host_beta/Dockerfile
FROM python:3.9-alpine AS base

# Set working directory
WORKDIR /app

COPY agent/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
# COPY /agent_files/requirements.txt /app/agent_requirements.txt
# RUN pip install --no-cache-dir -r /app/agent_requirements.txt

# COPY /agent_files/agent.py /app/agent.py
# COPY /agent_files/predefined_commands /app/predefined_commands/
COPY agent/agent.py /app/agent.py
COPY agent/predefined_commands /app/predefined_commands/

# Set executable permissions on all shell scripts in predefined_commands
RUN find /app/predefined_commands -name "*.sh" -type f -exec chmod +x {} \;

# Environment variable for the agent's port (can be overridden in docker-compose.yml)
ENV AGENT_PORT=9000
# ENV FLASK_APP=agent.py
# For flask run, though we run directly with python
ENV PYTHONUNBUFFERED=1
# Ensures print statements and logs are sent directly to terminal

# Expose the port the agent will listen on
EXPOSE 9000

# Command to run the agent
# We adjust PREDEFINED_COMMANDS_DIR in agent.py to /app/predefined_commands if we copy them here.
# However, the agent.py currently expects /agent_files/.
# For simplicity with the docker-compose volume mount, we'll rely on /agent_files.
# The CMD will be to run the agent.py located in /agent_files.
# The WORKDIR for the agent.py process will be /agent_files
WORKDIR /agent_files
CMD ["python", "agent.py"]