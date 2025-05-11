# target_host_alpha/Dockerfile
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
RUN echo "This is a demo log file" > /var/log/demo/app.log && \
    echo "Another log entry" >> /var/log/demo/app.log && \
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