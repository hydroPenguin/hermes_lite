from flask import Blueprint, render_template, request, jsonify
from sqlalchemy.orm import scoped_session, sessionmaker
from extensions import db
from models import CommandExecution
from tasks import execute_command
from auth import token_required, admin_required

main = Blueprint('main', __name__)

def get_session():
    return scoped_session(sessionmaker(bind=db.engine))

@main.route('/')
def index():
    """Home page -  command execution form."""
    return render_template('index.html')  # Create this template

@main.route('/execute_command', methods=['POST'])
@token_required
def trigger_command():
    """
    Triggers the execution of a command via Celery.
    Requires authentication.
    """
    session = get_session() #get the session
    try:
        data = request.get_json()
        command_name = data.get('command_name')
        target_host = data.get('target_host')
        params = data.get('params', [])
        
        # Use the authenticated user from the token
        user = request.username

        # 1. Create a CommandExecution record in the database.
        execution = CommandExecution(
            command_name=command_name,
            target_host=target_host,
            user=user
        )
        session.add(execution)
        session.commit()  # Commit immediately to get the execution.id

        execution_id = execution.id  # Get the generated ID

        # 2. Trigger the Celery task with the correct task name
        task = execute_command.delay(execution_id, command_name, target_host, params, user)

        return jsonify({'execution_id': execution_id, 'task_id': task.id, 'status': 'pending'}), 202  # 202 Accepted

    except Exception as e:
        session.rollback()
        error_message = str(e)
        return jsonify({'error': f'Failed to trigger command: {error_message}'}), 500
    finally:
        session.remove()

@main.route('/status/<int:execution_id>')
@token_required
def get_status(execution_id):
    """
    Gets the status of a command execution.
    Requires authentication.
    """
    session = get_session()
    try:
        execution = session.get(CommandExecution, execution_id) # Use get
        if not execution:
            return jsonify({'error': 'Execution not found'}), 404
        
        # Check if user has permission to view this execution
        if execution.user != request.username and not request.is_admin:
            return jsonify({'error': 'Unauthorized access'}), 403
        
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
    Gets the output of a command execution. Only returns *final* output.
    Authentication is handled by client-side JS when accessed directly.
    """
    session = get_session()
    try:
        execution = session.get(CommandExecution, execution_id) # Use get
        if not execution:
            return jsonify({'error': 'Execution not found'}), 404
        
        # API authentication check (optional for browser)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            from auth import decode_token
            token = auth_header.split(' ')[1]
            payload = decode_token(token)
            if payload:
                # If authenticated with token, check permissions
                username = payload['username']
                is_admin = payload['is_admin']
                if execution.user != username and not is_admin:
                    return jsonify({'error': 'Unauthorized access'}), 403
        
        # Return the output
        return jsonify({'output': execution.output}), 200
    except Exception as e:
        return jsonify({'error': f'Error fetching output: {str(e)}'}), 500
    finally:
        session.remove()

@main.route('/dashboard')
def dashboard():
    """
    Dashboard for viewing command execution status and history.
    Authentication is handled client-side by JavaScript.
    """
    session = get_session()
    try:
        # We'll handle authentication in the client-side JavaScript
        # This is a simpler approach for the demo - in production, you should use
        # server-side auth for all routes
        
        # Return all executions - filtering will happen client-side
        executions_query = session.query(CommandExecution).order_by(CommandExecution.start_time.desc()).all()
        
        # Convert SQLAlchemy objects to dictionaries for JSON serialization
        executions = []
        for exe in executions_query:
            executions.append({
                'id': exe.id,
                'command_name': exe.command_name,
                'target_host': exe.target_host,
                'status': exe.status,
                'start_time': exe.start_time.isoformat() if exe.start_time else None,
                'end_time': exe.end_time.isoformat() if exe.end_time else None,
                'exit_code': exe.exit_code,
                'user': exe.user
            })
        
        return render_template('dashboard.html', executions=executions)
    except Exception as e:
        return jsonify({'error': f'Error fetching executions: {str(e)}'}), 500
    finally:
        session.remove()

@main.route('/api/executions')
@token_required
def get_executions():
    """
    API endpoint to get command executions.
    Requires authentication.
    """
    session = get_session()
    try:
        # Non-admin users can only see their own executions
        if not request.is_admin:
            executions = session.query(CommandExecution).filter_by(user=request.username).order_by(CommandExecution.start_time.desc()).all()
        else:
            executions = session.query(CommandExecution).order_by(CommandExecution.start_time.desc()).all()
        
        result = []
        for exe in executions:
            result.append({
                'id': exe.id,
                'command_name': exe.command_name,
                'target_host': exe.target_host,
                'status': exe.status,
                'start_time': exe.start_time.isoformat() if exe.start_time else None,
                'end_time': exe.end_time.isoformat() if exe.end_time else None,
                'exit_code': exe.exit_code,
                'user': exe.user
            })
        
        return jsonify({'executions': result}), 200
    except Exception as e:
        return jsonify({'error': f'Error fetching executions: {str(e)}'}), 500
    finally:
        session.remove()
