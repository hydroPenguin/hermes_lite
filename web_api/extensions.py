# import os
# from flask_sqlalchemy import SQLAlchemy
# from flask_socketio import SocketIO
# from celery import Celery
#
# db = SQLAlchemy()
# socketio = SocketIO()
# celery = Celery(
#     __name__,
#     broker=os.getenv('CELERY_BROKER_URL', 'amqp://user:password@rabbitmq:5672//')
# )
import os
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from celery import Celery
from flask import Flask

db = SQLAlchemy()
# Initialize SocketIO with correct server-side settings
socketio = SocketIO(
    async_mode='eventlet',
    engineio_logger=True,  # Enable logging for troubleshooting
    # Server-side parameters only - remove client-side parameters
    ping_timeout=60,
    ping_interval=25
)

def create_celery_app(app: Flask = None) -> Celery:
    """
    Create a Celery application instance and configure it.
    """
    app = app or Flask(__name__)  # Create a Flask app if one isn't passed in
    celery = Celery(
        app.import_name,  # Use the Flask app's name
        broker=os.getenv('CELERY_BROKER_URL', 'amqp://user:password@rabbitmq:5672//'),
        backend=os.getenv('CELERY_RESULT_BACKEND', 'db+sqlite:///data/hermes_lite.db'),  # Add a default backend
    )
    
    # Apply Flask app config to Celery
    celery.conf.update(app.config)  # Update Celery config with Flask config
    
    # Set database URL from environment
    database_url = os.getenv('DATABASE_URL', 'sqlite:///data/hermes_lite.db')
    celery.conf.update(
        # Task configuration
        imports=('tasks',),
        task_routes={
            'extensions.execute_command': {'queue': 'celery'},
        },
        # Database configuration
        database_url=database_url,
        # Worker configuration
        worker_prefetch_multiplier=1,  # Don't prefetch more than 1 task
        task_acks_late=True,  # Only acknowledge tasks after they're completed
        worker_concurrency=2,  # Each worker can handle 2 tasks at once
    )

    class ContextTask(celery.Task):
        """
        Ensure tasks have access to what they need.
        Note: We don't use Flask app context here since we're using direct SQLAlchemy.
        """
        def __call__(self, *args, **kwargs):
            return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery_app = create_celery_app()
