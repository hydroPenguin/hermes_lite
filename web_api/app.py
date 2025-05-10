import os
from flask import Flask
from extensions import db, socketio, celery
from routes import main as main_blueprint
from database import init_db  # Add this import

# Initialize Flask
def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY='your_secret_key',
        SQLALCHEMY_DATABASE_URI=(
            f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__),'.', 'data', 'hermes_lite.db'))}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        CELERY_BROKER_URL=os.getenv('CELERY_BROKER_URL')
    )

    db.init_app(app)
    init_db(app)
    socketio.init_app(app)

    # tie celery to Flask config
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask

    # register routes
    app.register_blueprint(main_blueprint)
    return app

app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
