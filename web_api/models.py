# web_api/models.py
from sqlalchemy import Enum, Text, String, Integer, DateTime, func
from extensions import db

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
