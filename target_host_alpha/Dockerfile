# target_host_alpha/Dockerfile
FROM python:3.9-alpine AS base

# Set working directory
WORKDIR /app

# Copy the agent files from the mounted volume (see docker-compose.yml)
# In docker-compose, ./agent is mounted to /agent_files in the service definition.
# Here, we assume the build context for this Dockerfile *is* target_host_alpha,
# but the agent files are made available via the volume mount at runtime.
# For a standalone build of this image (without compose's volume mount during build),
# you'd need to adjust paths or use a multi-stage build.
# Given the docker-compose setup, the agent files will be at /agent_files at runtime.
# We need to install dependencies for the agent.
COPY /agent_files/requirements.txt /app/agent_requirements.txt
RUN pip install --no-cache-dir -r /app/agent_requirements.txt

# Copy the agent script and predefined commands into the image
# This makes the image more self-contained if you were to run it outside of the compose setup
# where the volume mount is defined.
COPY /agent_files/agent.py /app/agent.py
COPY /agent_files/predefined_commands /app/predefined_commands/

# Environment variable for the agent's port (can be overridden in docker-compose.yml)
ENV AGENT_PORT=9000
ENV FLASK_APP=agent.py # For flask run, though we run directly with python
ENV PYTHONUNBUFFERED=1 # Ensures print statements and logs are sent directly to terminal

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