from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from celery import Celery
import os

# Initialize Flask
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key'  # Change this!
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///./data/hermes_lite.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # silence warning
    # Initialize database
    db.init_app(app)
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    # Register blueprints
    from routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app

# Initialize SQLAlchemy
db = SQLAlchemy()
# Initialize SocketIO
socketio = SocketIO()

# Create Flask App
app = create_app()

# Initialize SocketIO with the Flask app
socketio.init_app(app,  async_mode='eventlet') # Use eventlet

# Initialize Celery
def init_celery(app):
    celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
    celery.config_from_object(app.config)
    celery.conf.update(
        {
            "worker_tmp_dir": "/tmp",  # Needed for some tasks
            "worker_log_format": "[%(asctime)s: %(levelname)s] %(message)s",
            "worker_task_log_format": "[%(asctime)s: %(levelname)s] %(message)s",
        }
    )
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = init_celery(app)

if __name__ == '__main__':
    #  Use socketio.run
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
