
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask import current_app as app # Import the current app
from models import CommandExecution
from tasks import execute_command
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from database import db # Import the SQLAlchemy database object

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
