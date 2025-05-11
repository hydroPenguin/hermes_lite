# web_api/auth.py
import os
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from models import User
from extensions import db

# Get JWT secret from environment or use a default for development
JWT_SECRET = os.environ.get('JWT_SECRET', 'development_secret_key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

def generate_token(user_id, username, is_admin=False):
    """Generate a JWT token for a user"""
    payload = {
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow(),
        'sub': user_id,
        'username': username,
        'is_admin': is_admin
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token):
    """Decode a JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token has expired
    except jwt.InvalidTokenError:
        return None  # Invalid token

def token_required(f):
    """Decorator to protect routes with JWT authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Authentication token required'}), 401
        
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Add user info to the request context
        request.user_id = payload['sub']
        request.username = payload['username']
        request.is_admin = payload['is_admin']
        
        return f(*args, **kwargs)
    
    return decorated

def admin_required(f):
    """Decorator to protect routes that require admin access"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Authentication token required'}), 401
        
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        if not payload.get('is_admin', False):
            return jsonify({'error': 'Admin privileges required'}), 403
        
        # Add user info to the request context
        request.user_id = payload['sub']
        request.username = payload['username']
        request.is_admin = payload['is_admin']
        
        return f(*args, **kwargs)
    
    return decorated 