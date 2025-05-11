# target_host_alpha/Dockerfile
FROM ubuntu:22.04

# Install SSH server and other utilities
RUN apt-get update && apt-get install -y \
    openssh-server \
    curl \
    htop \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH
RUN mkdir /var/run/sshd
RUN echo 'root:demo_password' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Create a demo user
RUN useradd -m -s /bin/bash demo_user
RUN echo 'demo_user:demo_password' | chpasswd

# Create some demo log files
RUN mkdir -p /var/log/demo
RUN echo "This is a demo log file" > /var/log/demo/app.log
RUN echo "Another log entry" >> /var/log/demo/app.log

# Expose SSH port
EXPOSE 22

# Start SSH server
CMD ["/usr/sbin/sshd", "-D"]