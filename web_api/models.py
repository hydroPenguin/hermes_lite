# web_api/models.py
from sqlalchemy import Enum, Text, String, Integer, DateTime, func, Boolean
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(100), unique=True, nullable=False)
    password_hash = db.Column(String(255), nullable=False)
    email = db.Column(String(255), unique=True, nullable=True)
    is_admin = db.Column(Boolean, default=False)
    created_at = db.Column(DateTime, server_default=func.now())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class CommandExecution(db.Model):
    __tablename__ = 'command_executions'

    id           = db.Column(Integer, primary_key=True)
    command_name = db.Column(String(255), nullable=False)
    target_host  = db.Column(String(255), nullable=False)
    user         = db.Column(String(255), nullable=False)
    start_time   = db.Column(DateTime, server_default=func.now())
    end_time     = db.Column(DateTime, nullable=True)
    status       = db.Column(
                     Enum(
                       "pending", "running", "success", "failure",
                       name="execution_status"
                     ),
                     default="pending"
                   )
    output       = db.Column(Text, nullable=True)
    exit_code    = db.Column(Integer, nullable=True)
    error        = db.Column(Text, nullable=True)
