# web_api/auth_routes.py
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import scoped_session, sessionmaker
from extensions import db
from models import User
from auth import generate_token, token_required, admin_required

auth = Blueprint('auth', __name__)

def get_session():
    return scoped_session(sessionmaker(bind=db.engine))

@auth.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    session = get_session()
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Check if user already exists
        existing_user = session.query(User).filter_by(username=username).first()
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 409
        
        if email:
            existing_email = session.query(User).filter_by(email=email).first()
            if existing_email:
                return jsonify({'error': 'Email already exists'}), 409
        
        # Create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        # First user is admin
        if session.query(User).count() == 0:
            new_user.is_admin = True
        
        session.add(new_user)
        session.commit()
        
        return jsonify({
            'message': 'User registered successfully',
            'user_id': new_user.id,
            'username': new_user.username
        }), 201
    
    except Exception as e:
        session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500
    finally:
        session.remove()

@auth.route('/login', methods=['POST'])
def login():
    """Authenticate user and return a JWT token"""
    session = get_session()
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Find user by username
        user = session.query(User).filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Generate token
        token = generate_token(user.id, user.username, user.is_admin)
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user_id': user.id,
            'username': user.username,
            'is_admin': user.is_admin
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500
    finally:
        session.remove()

@auth.route('/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users (admin only)"""
    session = get_session()
    try:
        users = session.query(User).all()
        user_list = [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_admin': user.is_admin,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ]
        return jsonify({'users': user_list}), 200
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve users: {str(e)}'}), 500
    finally:
        session.remove() 