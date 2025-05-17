#!/usr/bin/env python
# Ensure eventlet monkey patching happens first
import eventlet
eventlet.monkey_patch()

import os
import sys
import time
import logging
import requests
import socket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Set default hostname if not provided
worker_name = os.environ.get('WORKER_NAME', 'worker')

# Configure startup delay based on worker name or environment variable
startup_delay = int(os.environ.get('WORKER_STARTUP_DELAY', '0'))
retry_max_attempts = int(os.environ.get('WORKER_RETRY_ATTEMPTS', '15'))

# If delay is not explicitly set via env var, use defaults based on worker name
if not startup_delay:
    if worker_name == 'worker':
        startup_delay = 2  # Default delay for worker1 
        retry_max_attempts = 15
    elif worker_name == 'worker2':
        startup_delay = 10  # Longer delay for worker2
        retry_max_attempts = 30
    else:
        # For any other workers
        startup_delay = 5
        retry_max_attempts = 20

# Initialize connection parameters
socketio_url = os.environ.get('SOCKETIO_URL', 'http://web:5000')
socketio_base_url = socketio_url.rsplit(':', 1)[0] if ':' in socketio_url else socketio_url
socketio_host = socketio_base_url.replace('http://', '').replace('https://', '')
socketio_port = int(socketio_url.rsplit(':', 1)[1]) if ':' in socketio_url else 80

logger.info(f"Worker {worker_name} starting with {startup_delay}s initial delay to ensure services are ready...")
logger.info(f"Will use {retry_max_attempts} retry attempts to connect to web server at {socketio_url}")

# Initial delay based on worker name
if startup_delay > 0:
    logger.info(f"Waiting for initial delay of {startup_delay} seconds...")
    time.sleep(startup_delay)
    logger.info("Initial delay completed.")

# Function to check if a port is open
def is_port_open(host, port, timeout=1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.shutdown(socket.SHUT_RDWR)
        return True
    except (socket.timeout, socket.error):
        return False
    finally:
        sock.close()

# Function to check if the web server is responding
def is_web_server_ready(url, timeout=2):
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False

# Wait for services to be ready
max_attempts = retry_max_attempts
attempt = 0
web_ready = False

while attempt < max_attempts and not web_ready:
    attempt += 1
    logger.info(f"Checking if web server is ready (attempt {attempt}/{max_attempts})...")
    
    # First check if the port is open
    if is_port_open(socketio_host, socketio_port):
        logger.info(f"Port {socketio_port} is open on {socketio_host}")
        
        # Then check if the web server is responding
        if is_web_server_ready(socketio_url):
            logger.info(f"Web server at {socketio_url} is ready!")
            web_ready = True
        else:
            logger.info(f"Port is open but web server is not responding yet")
    else:
        logger.info(f"Port {socketio_port} is not open on {socketio_host} yet")
    
    if not web_ready and attempt < max_attempts:
        # Calculate wait time based on worker (shorter for worker1, longer for worker2)
        wait_time = min(5, attempt) if worker_name == 'worker2' else min(3, attempt)
        logger.info(f"Waiting {wait_time} seconds before next check...")
        time.sleep(wait_time)

if not web_ready:
    logger.warning(f"Web server did not become ready after {max_attempts} attempts")
    logger.warning("Continuing anyway, but Socket.IO communication might not work properly")

# Add an additional delay just to be safe, but shorter than worker2
final_delay = 5 if worker_name == 'worker2' else 2
logger.info(f"Adding final delay of {final_delay} seconds before starting worker...")
time.sleep(final_delay)
logger.info(f"Delay complete, starting worker {worker_name}...")

# Import Celery app
from extensions import celery_app

if __name__ == '__main__':
    # Build the Celery worker command
    args = [
        'worker', 
        '--loglevel=info', 
        '-P', 'eventlet', 
        '--without-gossip', 
        '--without-mingle'
    ]
    
    # Always add hostname for clarity in logs
    args.append(f'--hostname={worker_name}@%h')
    
    # Start the worker
    logger.info(f"Starting Celery worker: {worker_name}")
    celery_app.worker_main(args) 