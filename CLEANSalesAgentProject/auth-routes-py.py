"""
Authentication routes for the Sales Training AI application.

This module provides routes for user registration, login, and logout.
It also includes Google OAuth integration.
"""
import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from auth_security import validate_password, check_rate_limit, record_failed_login, record_successful_login, csrf_required, rate_limit

# OAuth for Google login
from authlib.integrations.flask_client import OAuth

# Create blueprint
auth = Blueprint('auth', __name__, url_prefix='/auth')

# Initialize OAuth
oauth = OAuth()
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
)

@auth.route('/login')
def login():
    """Login page."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('chat.dashboard'))
    
    # Check for next parameter
    next_url = request.args.get('next')
    if next_url:
        session['next_url'] = next_url
    
    return render_template('auth/login.html')

@auth.route('/login', methods=['POST'])
@csrf_required
@rate_limit(limit=5, window=300)  # 5 requests per 5 minutes
def login_post():
    """Handle login form submission."""
    # Get form data
    if request.is_json:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        remember = data.get('remember', False)
    else:
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
    
    # Input validation
    if not email or not password:
        return jsonify({'error': 'Please provide both email and password'}), 400
    
    # Check if account is locked
    is_allowed, lockout_time = check_login_attempts(email)
    if not is_allowed:
        return jsonify({
            'error': f'Too many login attempts. Try again in {lockout_time} seconds.'
        }), 429
    
    # Find user
    user = User.query.filter_by(email=email).first()
    
    # Check password
    if not user or not user.check_password(password):
        # Record failed login
        is_locked, lockout_time = record_failed_login(email)
        
        if is_locked:
            return jsonify({
                'error': f'Account locked due to too many failed attempts. Try again in {lockout_time} seconds.'
            }), 429
        
        return jsonify({'error': 'Invalid email or password. Please try again.'}), 401
    
    # Record successful login
    record_successful_login(email)
    
    # Log user in
    login_user(user, remember=remember)
    
    # Get redirect URL
    next_url = session.pop('next_url', None) or url_for('chat.dashboard')
    
    return jsonify({
        'status': 'success',
        'redirect': next_url
    })

@auth.route('/signup')
def signup():
    """Signup page."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('chat.dashboard'))
    
    return render_template('auth/signup.html')

@auth.route('/register', methods=['POST'])
@csrf_required
@rate_limit(limit=10, window=3600)  # 10 requests per hour
def register():
    """Handle registration form submission."""
    # Get registration data
    if request.is_json:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
    else:
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
    
    # Input validation
    if not name or not email or not password:
        return jsonify({'error': 'Please provide all required fields'}), 400
    
    # Check if email already exists
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({'error': 'Email address already in use'}), 400
    
    # Validate password strength
    is_valid, error_message = validate_password(password)
    if not is_valid:
        return jsonify({'error': error_message}), 400
    
    # Create new user
    new_user = User(
        name=name,
        email=email
    )
    new_user.set_password(password)
    
    # Initialize default skills
    new_user.skills_dict = {
        "rapport_building": 0,
        "needs_discovery": 0,
        "objection_handling": 0,
        "closing": 0,
        "product_knowledge": 0
    }
    
    # Save to database
    db.session.add(new_user)
    db.session.commit()
    
    # Log in the new user
    login_user(new_user)
    
    return jsonify({
        'status': 'success',
        'redirect': url_for('chat.dashboard')
    })

@auth.route('/logout')
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('index'))

@auth.route('/google')
def google_login():
    """Initiate Google OAuth flow."""
    # Store next URL in session for redirect after auth
    next_url = request.args.get('next')
    if next_url:
        session['next_url'] = next_url
    
    redirect_uri = url_for('auth.google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@auth.route('/google/callback')
def google_callback():
    """Handle Google OAuth callback."""
    try:
        token = google.authorize_access_token()
        resp = google.get('userinfo')
        user_info = resp.json()
        
        # Check if Google ID exists in database
        user = User.query.filter_by(google_id=user_info['id']).first()
        
        # If not, check if email exists
        if not user:
            user = User.query.filter_by(email=user_info['email']).first()
        
        # If user exists, update Google ID
        if user:
            if not user.google_id:
                user.google_id = user_info['id']
                db.session.commit()
        else:
            # Create new user
            user = User(
                name=user_info['name'],
                email=user_info['email'],
                google_id=user_info['id']
            )
            
            # Initialize default skills
            user.skills_dict = {
                "rapport_building": 0,
                "needs_discovery": 0,
                "objection_handling": 0,
                "closing": 0,
                "product_knowledge": 0
            }
            
            db.session.add(user)
            db.session.commit()
        
        # Log in user
        login_user(user)
        
        # Redirect to next_url or dashboard
        next_url = session.pop('next_url', None) or url_for('chat.dashboard')
        return redirect(next_url)
        
    except Exception as e:
        flash('Google login failed. Please try again or use email login.', 'error')
        return redirect(url_for('auth.login'))