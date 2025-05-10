import os
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from celery import Celery

db = SQLAlchemy()
socketio = SocketIO()
celery = Celery(
    __name__,
    broker=os.getenv('CELERY_BROKER_URL', 'amqp://user:password@rabbitmq:5672//')
)
