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
socketio = SocketIO()
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
    celery.conf.update(app.config)  # Update Celery config with Flask config

    class ContextTask(celery.Task):
        """
        Ensure Celery tasks have the Flask application context.
        """

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
celery_app = create_celery_app()
