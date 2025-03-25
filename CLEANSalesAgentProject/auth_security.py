"""
Authentication and Security Utilities for Sales Training AI

This module provides enhanced security for authentication-related functionality
including secure password handling, rate limiting, and CSRF protection.
"""

import time
import logging
import secrets
import re
from typing import Dict, Tuple, Optional, Any
from functools import wraps
from flask import request, session, g, redirect, url_for, flash, abort

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("security.log"), logging.StreamHandler()]
)
logger = logging.getLogger("AuthSecurity")

# Import config manager
from config_manager import config

# Rate limiting storage (in-memory, replace with Redis in production)
_rate_limit_data = {}

# Login attempt tracking storage
_login_attempts = {}

def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate if a password meets security requirements.
    
    Args:
        password: The password to validate
            
    Returns:
        Tuple containing (is_valid, error_message)
    """
    min_length = config.get('PASSWORD_MIN_LENGTH', 8)
    
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long"
    
    # Check for at least one digit
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    # Check for at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for at least one lowercase letter
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for at least one special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, ""

def check_rate_limit(key: str, limit: int = None, window: int = None) -> Tuple[bool, int, int]:
    """
    Check if a rate limit has been exceeded.
    
    Args:
        key: Unique identifier for the rate limit (e.g., IP + endpoint)
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
        
    Returns:
        Tuple containing (is_allowed, remaining_attempts, retry_after)
    """
    global _rate_limit_data
    
    if limit is None:
        limit = config.get('RATE_LIMIT', 10)
        
    if window is None:
        window = config.get('RATE_LIMIT_WINDOW', 60)
    
    current_time = time.time()
    
    # Initialize or clean up old timestamps for this key
    if key not in _rate_limit_data:
        _rate_limit_data[key] = []
    
    # Remove timestamps older than the window
    _rate_limit_data[key] = [t for t in _rate_limit_data[key] 
                            if current_time - t < window]
    
    # Check if rate limit is exceeded
    if len(_rate_limit_data[key]) >= limit:
        oldest_timestamp = _rate_limit_data[key][0]
        retry_after = int(window - (current_time - oldest_timestamp))
        return False, 0, retry_after
    
    # Add timestamp and return allowed
    _rate_limit_data[key].append(current_time)
    remaining = limit - len(_rate_limit_data[key])
    return True, remaining, 0

def check_login_attempts(username: str) -> Tuple[bool, int]:
    """
    Check if a user has exceeded the maximum number of failed login attempts.
    
    Args:
        username: Username or email trying to log in
        
    Returns:
        Tuple containing (is_allowed, lockout_time_remaining)
    """
    global _login_attempts
    
    max_attempts = config.get('MAX_LOGIN_ATTEMPTS', 5)
    lockout_time = config.get('LOCKOUT_TIME', 300)  # 5 minutes
    current_time = time.time()
    
    # Initialize login attempts if needed
    if username not in _login_attempts:
        _login_attempts[username] = {
            'attempts': 0,
            'last_attempt': 0,
            'lockout_until': 0
        }
    
    user_data = _login_attempts[username]
    
    # Check if user is in lockout period
    if user_data['lockout_until'] > current_time:
        time_remaining = int(user_data['lockout_until'] - current_time)
        return False, time_remaining
    elif user_data['lockout_until'] > 0:
        # Reset after lockout period expires
        user_data['attempts'] = 0
        user_data['lockout_until'] = 0
    
    return True, 0

def record_failed_login(username: str) -> Tuple[bool, int]:
    """
    Record a failed login attempt and determine if account should be locked.
    
    Args:
        username: Username or email that failed to log in
        
    Returns:
        Tuple containing (is_locked_out, lockout_time)
    """
    global _login_attempts
    
    max_attempts = config.get('MAX_LOGIN_ATTEMPTS', 5)
    lockout_time = config.get('LOCKOUT_TIME', 300)  # 5 minutes
    current_time = time.time()
    
    # Initialize login attempts if needed
    if username not in _login_attempts:
        _login_attempts[username] = {
            'attempts': 0,
            'last_attempt': 0,
            'lockout_until': 0
        }
    
    user_data = _login_attempts[username]
    
    # Increment attempt count
    user_data['attempts'] += 1
    user_data['last_attempt'] = current_time
    
    # Check if should be locked out
    if user_data['attempts'] >= max_attempts:
        user_data['lockout_until'] = current_time + lockout_time
        logger.warning(f"Account locked due to too many failed attempts: {username}")
        return True, lockout_time
    
    return False, 0

def record_successful_login(username: str) -> None:
    """
    Record a successful login and reset failed attempt counter.
    
    Args:
        username: Username or email that successfully logged in
    """
    global _login_attempts
    
    if username in _login_attempts:
        _login_attempts[username] = {
            'attempts': 0,
            'last_attempt': time.time(),
            'lockout_until': 0
        }

def generate_csrf_token():
    """Generate a CSRF token and store it in the session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(16)
    return session['_csrf_token']

# CSRF protection decorator
def csrf_required(f):
    """Decorator to require valid CSRF token for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For GET requests, just generate a new token
        if request.method == 'GET':
            generate_csrf_token()
            return f(*args, **kwargs)
        
        # For other methods like POST, validate token
        token = request.form.get('csrf_token')
        
        # For JSON requests, check header
        if request.is_json and not token:
            token = request.headers.get('X-CSRF-Token')
        
        if not token or token != session.get('_csrf_token'):
            logger.warning(f"CSRF validation failed for {request.path}")
            if request.is_json:
                abort(403)
            flash('For security reasons, your form submission could not be processed. Please try again.', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

# Rate limiting decorator
def rate_limit(limit=None, window=None):
    """
    Decorator to apply rate limiting to a route.
    
    Args:
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get a unique key for this rate limit
            key = f"{request.remote_addr}:{request.path}"
            
            # Check rate limit
            allowed, remaining, retry_after = check_rate_limit(key, limit, window)
            
            if not allowed:
                logger.warning(f"Rate limit exceeded for {key}")
                
                # Set headers for rate limiting info
                response = redirect(url_for('errors.too_many_requests'))
                response.headers['Retry-After'] = str(retry_after)
                return response
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
