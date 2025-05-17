from flask import Blueprint, render_template, request, jsonify, redirect
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import text
from extensions import db
from models import CommandExecution
from tasks import execute_command
from auth import token_required, admin_required

main = Blueprint('main', __name__)

def get_session():
    return scoped_session(sessionmaker(bind=db.engine))

@main.route('/health')
def health_check():
    """
    Health check endpoint for Docker and other monitoring services.
    No authentication required.
    """
    try:
        # Verify database connection
        session = get_session()
        session.execute(text("SELECT 1")).fetchone()
        session.remove()
        # If we get here, database is working
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'message': 'Service is up and running'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'error',
            'message': str(e)
        }), 500

@main.route('/')
def index():
    """Home page -  command execution form."""
    return render_template('index.html')

@main.route('/execute_command', methods=['POST'])
@token_required
def trigger_command():
    """
    Triggers the execution of a command via Celery.
    Requires authentication.
    """
    session = get_session()
    try:
        data = request.get_json()
        command_name = data.get('command_name')
        target_host = data.get('target_host')
        params = data.get('params', [])
        stream_to_ui = data.get('stream_to_ui', False)
        
        # Use the authenticated user from the token
        user = request.username

        # Create a CommandExecution record in the database
        execution = CommandExecution(
            command_name=command_name,
            target_host=target_host,
            user=user
        )
        session.add(execution)
        session.commit()

        execution_id = execution.id

        # Trigger the Celery task
        task = execute_command.delay(execution_id, command_name, target_host, params, user)
        
        # If direct streaming to UI is requested, return redirect info
        if stream_to_ui:
            stream_url = f"/stream-output/{execution_id}"
            return jsonify({
                'execution_id': execution_id, 
                'task_id': task.id, 
                'status': 'pending',
                'stream_url': stream_url,
                'redirect': True
            }), 202
        
        # Otherwise, return standard response
        return jsonify({'execution_id': execution_id, 'task_id': task.id, 'status': 'pending'}), 202

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
    No authentication required - all users can view execution status.
    """
    session = get_session()
    try:
        execution = session.get(CommandExecution, execution_id)
        if not execution:
            return jsonify({'error': 'Execution not found'}), 404
        
        return jsonify({
            'id': execution.id,
            'command_name': execution.command_name,
            'target_host': execution.target_host,
            'status': execution.status,
            'start_time': execution.start_time.isoformat() if execution.start_time else None,
            'end_time': execution.end_time.isoformat() if execution.end_time else None,
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
    Gets the output of a command execution.
    Renders the output.html template with real-time streaming capability.
    Authentication is handled client-side by JavaScript.
    """
    session = get_session()
    try:
        execution = session.get(CommandExecution, execution_id)
        if not execution:
            return render_template('output.html', execution=None, error="Execution not found")
        
        return render_template(
            'output.html', 
            execution=execution,
            auto_connect=True,
            streaming_mode=True
        )
    except Exception as e:
        return render_template('output.html', execution=None, error=str(e))
    finally:
        session.remove()

@main.route('/api/output/<int:execution_id>')
def get_output_api(execution_id):
    """
    API endpoint that returns the raw output data for a command execution.
    No authentication required - all users can view command outputs.
    """
    session = get_session()
    try:
        execution = session.get(CommandExecution, execution_id)
        if not execution:
            return jsonify({'error': 'Execution not found'}), 404
        
        # Return the output - no auth check required
        return jsonify({'output': execution.output or ''}), 200
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
        # Return all executions - filtering will happen client-side
        executions_query = session.query(CommandExecution).order_by(CommandExecution.start_time.desc()).all()
        
        # Convert SQLAlchemy objects to dictionaries for JSON serialization
        executions = []
        for exe in executions_query:
            exe_dict = {
                'id': exe.id,
                'command_name': exe.command_name,
                'target_host': exe.target_host,
                'status': exe.status,
                'start_time': exe.start_time.isoformat() if exe.start_time else None,
                'end_time': exe.end_time.isoformat() if exe.end_time else None,
                'exit_code': exe.exit_code if exe.exit_code is not None else None,
                'user': exe.user
            }
            executions.append(exe_dict)
        
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
        # Return all executions for all users regardless of admin status
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

@main.route('/stream-output/<int:execution_id>')
def stream_output(execution_id):
    """
    Render a page for streaming command output in real-time.
    """
    session = get_session()
    try:
        execution = session.get(CommandExecution, execution_id)
        if not execution:
            return render_template('output.html', execution=None, error="Execution not found")
        
        return render_template(
            'output.html', 
            execution=execution,
            auto_connect=True,
            streaming_mode=True
        )
    except Exception as e:
        return render_template('output.html', execution=None, error=str(e))
    finally:
        session.remove()
