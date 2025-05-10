# models.py
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class CommandExecution(Base):
    __tablename__ = 'command_executions'

    id = Column(Integer, primary_key=True)
    command_name = Column(String(255), nullable=False)
    target_host = Column(String(255), nullable=False)
    user = Column(String(255), nullable=False)  # Add user tracking
    start_time = Column(DateTime, server_default=func.now())
    end_time = Column(DateTime, nullable=True)
    status = Column(Enum("pending", "running", "success", "failure", name="execution_status"), default="pending")
    output = Column(Text, nullable=True)  # Store final output
    exit_code = Column(Integer, nullable=True)
    error = Column(Text, nullable=True) # Store error messages

