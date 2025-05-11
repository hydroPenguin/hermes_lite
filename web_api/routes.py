from flask import Blueprint, render_template, request, jsonify
from sqlalchemy.orm import scoped_session, sessionmaker
from extensions import db
from models import CommandExecution, User, Host
from tasks import execute_command
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity
from utils import CommandExecutor
import json
from datetime import datetime
from flask_socketio import emit
from extensions import socketio
import os

main = Blueprint('main', __name__)

def get_session():
    return scoped_session(sessionmaker(bind=db.engine))

@main.route('/')
def index():
    """Home page -  command execution form."""
    return render_template('index.html')  # Create this template

@main.route('/execute_command', methods=['POST'])
def trigger_command():
    """
    Triggers the execution of a command via Celery.
    """
    session = get_session() #get the session
    try:
        data = request.get_json()
        command_name = data.get('command_name')
        target_host = data.get('target_host')
        params = data.get('params', [])
        user = "current_user" #  Replace with actual user authentication

        # 1. Create a CommandExecution record in the database.
        execution = CommandExecution(
            command_name=command_name,
            target_host=target_host,
            user=user
        )
        session.add(execution)
        session.commit()  # Commit immediately to get the execution.id

        execution_id = execution.id  # Get the generated ID

        # 2. Trigger the Celery task.
        task = execute_command.delay(execution_id, command_name, target_host, params, user)

        # 3. Store the Celery task ID (optional, for task management)
        # execution.celery_task_id = task.id # Removed: Not storing Celery task ID in DB
        # db.session.commit()

        return jsonify({'execution_id': execution_id, 'task_id': task.id, 'status': 'pending'}), 202  # 202 Accepted

    except Exception as e:
        session.rollback()
        error_message = str(e)
        return jsonify({'error': f'Failed to trigger command: {error_message}'}), 500
    finally:
        session.remove()

@main.route('/status/<int:execution_id>')
def get_status(execution_id):
    """
    Gets the status of a command execution.
    """
    session = get_session()
    try:
        execution = session.get(CommandExecution, execution_id) # Use get
        if not execution:
            return jsonify({'error': 'Execution not found'}), 404
        #  Do not return the full output here, might be too large.
        return jsonify({
            'id': execution.id,
            'command_name': execution.command_name,
            'target_host': execution.target_host,
            'status': execution.status,
            'start_time': execution.start_time,
            'end_time': execution.end_time,
            'exit_code': execution.exit_code,
            'user': execution.user
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error fetching status: {str(e)}'}), 500
    finally:
        session.remove()

@main.route('/output/<int:execution_id>')
def get_output(execution_id):
    """
    Gets the output of a command execution.  Only returns *final* output.
    """
    session = get_session()
    try:
        execution = session.get(CommandExecution, execution_id) # Use get
        if not execution:
            return jsonify({'error': 'Execution not found'}), 404
        return jsonify({'output': execution.output}), 200
    except Exception as e:
        return jsonify({'error': f'Error fetching output: {str(e)}'}), 500
    finally:
        session.remove()

@main.route('/dashboard')
def dashboard():
    """
    Dashboard for viewing command execution status and history.
    """
    session = get_session()
    try:
        executions = session.query(CommandExecution).order_by(CommandExecution.start_time.desc()).all()
        return render_template('dashboard.html', executions=executions) # Pass data to template
    except Exception as e:
        return jsonify({'error': f'Error fetching executions: {str(e)}'}), 500
    finally:
        session.remove()

# Authentication routes
@main.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
        
    user = User(
        username=data['username'],
        email=data['email'],
        is_admin=data.get('is_admin', False)
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'User created successfully'}), 201

@main.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    
    if user and user.check_password(data['password']):
        access_token = create_access_token(identity=user.id)
        return jsonify({'access_token': access_token}), 200
        
    return jsonify({'error': 'Invalid credentials'}), 401

# Host management routes
@main.route('/api/hosts', methods=['GET'])
@jwt_required()
def get_hosts():
    hosts = Host.query.all()
    return jsonify([{
        'id': host.id,
        'hostname': host.hostname,
        'ip_address': host.ip_address,
        'host_group': host.host_group,
        'is_active': host.is_active
    } for host in hosts])

@main.route('/api/hosts', methods=['POST'])
@jwt_required()
def add_host():
    data = request.get_json()
    host = Host(**data)
    db.session.add(host)
    db.session.commit()
    return jsonify({'message': 'Host added successfully'}), 201

# Command execution routes
@main.route('/api/commands', methods=['GET'])
@jwt_required()
def get_commands():
    executor = CommandExecutor(None)
    commands = executor.load_commands()
    return jsonify(commands)

@main.route('/api/commands/execute', methods=['POST'])
@jwt_required()
def execute_command():
    data = request.get_json()
    user_id = get_jwt_identity()
    
    # Create execution record
    execution = CommandExecution(
        command_name=data['command_name'],
        target_host=data['target_host'],
        user_id=user_id,
        parameters=json.dumps(data.get('parameters', {}))
    )
    db.session.add(execution)
    db.session.commit()
    
    # Get host details
    host = Host.query.filter_by(hostname=data['target_host']).first()
    if not host:
        execution.status = 'failure'
        execution.error = 'Host not found'
        db.session.commit()
        return jsonify({'error': 'Host not found'}), 404
    
    # Execute command
    try:
        executor = CommandExecutor(
            host=host.ip_address,
            port=host.ssh_port,
            username=os.getenv('SSH_USERNAME')
        )
        
        # Load command definition
        commands = executor.load_commands()
        command_def = next((cmd for cmd in commands['commands'] if cmd['name'] == data['command_name']), None)
        
        if not command_def:
            raise ValueError('Command not found')
            
        # Validate parameters
        executor.validate_parameters(command_def, data.get('parameters', {}))
        
        # Format command
        command = executor.format_command(command_def['command'], data.get('parameters', {}))
        
        # Update execution status
        execution.status = 'running'
        db.session.commit()
        
        # Execute command and stream output
        output_lines = []
        for line in executor.execute_command(command, timeout=command_def['timeout']):
            output_lines.append(line)
            # Emit real-time updates via WebSocket
            socketio.emit('command_output', {
                'execution_id': execution.id,
                'output': line
            })
        
        # Update execution record
        execution.status = 'success'
        execution.output = '\n'.join(output_lines)
        execution.end_time = datetime.utcnow()
        
    except Exception as e:
        execution.status = 'failure'
        execution.error = str(e)
        execution.end_time = datetime.utcnow()
        
    finally:
        db.session.commit()
        if 'executor' in locals():
            executor.close()
    
    return jsonify({
        'execution_id': execution.id,
        'status': execution.status
    })

@main.route('/api/executions', methods=['GET'])
@jwt_required()
def get_executions():
    executions = CommandExecution.query.order_by(CommandExecution.start_time.desc()).all()
    return jsonify([{
        'id': ex.id,
        'command_name': ex.command_name,
        'target_host': ex.target_host,
        'user': ex.user.username,
        'start_time': ex.start_time.isoformat(),
        'end_time': ex.end_time.isoformat() if ex.end_time else None,
        'status': ex.status,
        'exit_code': ex.exit_code
    } for ex in executions])

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    emit('connection_response', {'data': 'Connected'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
