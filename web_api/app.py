import os
from flask import Flask
from extensions import db, socketio, create_celery_app
from routes import main as main_blueprint
from auth_routes import auth as auth_blueprint
from database import init_db

# Initialize Flask
def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'your_secret_key'),
        SQLALCHEMY_DATABASE_URI=(
            f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'data', 'hermes_lite.db'))}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        CELERY_BROKER_URL=os.getenv('CELERY_BROKER_URL', 'amqp://user:password@rabbitmq:5672//'),
        # Added default values
        CELERY_RESULT_BACKEND=os.getenv('CELERY_RESULT_BACKEND', 'db+sqlite:///data/hermes_lite.db'),
        JWT_SECRET=os.getenv('JWT_SECRET', 'your_secure_jwt_secret')
    )

    db.init_app(app)
    init_db(app)
    socketio.init_app(app)

    # register routes
    app.register_blueprint(main_blueprint)
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    return app

app = create_app()
celery = create_celery_app(app)  # Initialize Celery *after* creating the Flask app

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
