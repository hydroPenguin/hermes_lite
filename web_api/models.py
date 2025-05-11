# web_api/models.py
from sqlalchemy import Enum, Text, String, Integer, DateTime, func, ForeignKey, Boolean
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(80), unique=True, nullable=False)
    email = db.Column(String(120), unique=True, nullable=False)
    password_hash = db.Column(String(128))
    is_admin = db.Column(Boolean, default=False)
    created_at = db.Column(DateTime, server_default=func.now())
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Host(db.Model):
    __tablename__ = 'hosts'
    
    id = db.Column(Integer, primary_key=True)
    hostname = db.Column(String(255), unique=True, nullable=False)
    ip_address = db.Column(String(45), nullable=False)
    ssh_port = db.Column(Integer, default=22)
    host_group = db.Column(String(50), nullable=False)
    is_active = db.Column(Boolean, default=True)
    last_seen = db.Column(DateTime, nullable=True)
    created_at = db.Column(DateTime, server_default=func.now())

class CommandExecution(db.Model):
    __tablename__ = 'command_executions'

    id           = db.Column(Integer, primary_key=True)
    command_name = db.Column(String(255), nullable=False)
    target_host  = db.Column(String(255), nullable=False)
    user_id      = db.Column(Integer, ForeignKey('users.id'), nullable=False)
    user         = db.relationship('User', backref='executions')
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
    parameters   = db.Column(Text, nullable=True)  # JSON string of command parameters
