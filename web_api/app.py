# Must monkey patch at the very start, before any other imports
import eventlet
eventlet.monkey_patch()

import os
import json
import time
import logging
from flask import Flask, request
from flask_cors import CORS
# Import these after monkey patching
from extensions import db, socketio, create_celery_app
from routes import main as main_blueprint
from auth_routes import auth as auth_blueprint
from database import init_db
from flask_socketio import Namespace, emit, disconnect, join_room, rooms, close_room

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

# Define a Socket.IO namespace
class RealtimeNamespace(Namespace):
    def on_connect(self, auth):
        sid = request.sid
        logger.info(f"Client {sid} connected to realtime namespace")
        emit('welcome', {'message': 'Connected to realtime namespace'}, room=sid)
    
    def on_disconnect(self, sid, reason=None):
        logger.info(f"Client {sid} disconnected from realtime namespace: {reason}")
    
    def on_error(self, e):
        sid = request.sid if hasattr(request, 'sid') else 'unknown'
        logger.error(f"Error in realtime namespace for client {sid}: {e}")

    def on_join(self, data):
        sid = request.sid
        execution_id = data.get('execution_id', "test123")
        
        if execution_id:
            room = f"exec_{execution_id}"
            join_room(room)
            logger.info(f"Client {sid} joined room: {room}")
            emit('join_response', {'status': 'success', 'room': room, 'execution_id': execution_id}, room=sid)
        else:
            logger.warning(f"Client {sid}: No execution_id provided in join event.")
            emit('join_response', {'status': 'error', 'message': 'No execution_id provided'}, room=sid)
    
    def on_ping(self):
        """Handle ping event from client to keep connection alive"""
        sid = request.sid
        emit('pong', {'time': time.time()}, room=sid)
    
    def on_test_message(self, data):
        """Handle test messages from workers or clients"""
        sid = request.sid
        emit('test_response', {'received': data, 'from_server': True}, room=sid)
        
# Initialize Flask
def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    # Enable CORS for all routes
    CORS(app)
    
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'your_secret_key'),
        SQLALCHEMY_DATABASE_URI=(
            f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'data', 'hermes_lite.db'))}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        CELERY_BROKER_URL=os.getenv('CELERY_BROKER_URL', 'amqp://user:password@rabbitmq:5672//'),
        CELERY_RESULT_BACKEND=os.getenv('CELERY_RESULT_BACKEND', 'db+sqlite:///data/hermes_lite.db'),
        JWT_SECRET=os.getenv('JWT_SECRET', 'your_secure_jwt_secret')
    )

    db.init_app(app)
    init_db(app)
    
    # Initialize SocketIO with the broker for inter-process communication
    socketio.init_app(
        app, 
        cors_allowed_origins="*",
        message_queue=os.getenv('CELERY_BROKER_URL', 'amqp://user:password@rabbitmq:5672//'),
        transports=['websocket', 'polling'],
        ping_timeout=60,
        ping_interval=25,
        max_http_buffer_size=10 * 1024 * 1024,
        engineio_logger=False
    )
    
    # Register the '/realtime' namespace
    socketio.on_namespace(RealtimeNamespace('/realtime'))
    
    # Add a health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy'}, 200
    
    # register routes
    app.register_blueprint(main_blueprint)
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    return app

app = create_app()
celery = create_celery_app(app)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
