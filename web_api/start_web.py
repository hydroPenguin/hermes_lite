# Ensure eventlet monkey patching happens first
import eventlet
eventlet.monkey_patch()

import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv('DEBUG', 'false').lower() == 'true' else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set specific loggers to debug level
for logger_name in ['socketio', 'engineio', 'werkzeug']:
    logging.getLogger(logger_name).setLevel(logging.DEBUG)

# Import Flask app and socketio
from app import socketio, app

if __name__ == '__main__':
    print("Starting Hermes Lite web server with Socket.IO support...")
    # Run the Flask app with SocketIO using eventlet
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) 