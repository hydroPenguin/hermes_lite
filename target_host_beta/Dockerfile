# target_host_alpha/Dockerfile
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

FROM ubuntu:22.04

# Install SSH server and other utilities
RUN apt-get update && apt-get install -y \
    openssh-server \
    curl \
    htop \
    vim \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH
RUN mkdir /var/run/sshd
RUN echo 'root:demo_password' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Create a demo user with sudo privileges
RUN useradd -m -s /bin/bash demo_user && \
    echo 'demo_user:demo_password' | chpasswd && \
    usermod -aG sudo demo_user

# Configure sudo for demo_user
RUN echo "demo_user ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/demo_user

# Create some demo log files
RUN mkdir -p /var/log/demo && \
    chown -R demo_user:demo_user /var/log/demo
RUN echo "This is a demo log file from beta host" > /var/log/demo/app.log && \
    echo "Another log entry from beta" >> /var/log/demo/app.log && \
    chown demo_user:demo_user /var/log/demo/app.log

# SSH security hardening
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitEmptyPasswords no/PermitEmptyPasswords no/' /etc/ssh/sshd_config && \
    sed -i 's/#X11Forwarding yes/X11Forwarding no/' /etc/ssh/sshd_config

# Expose SSH port
EXPOSE 22

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD nc -z localhost 22 || exit 1

# Start SSH server
CMD ["/usr/sbin/sshd", "-D"]