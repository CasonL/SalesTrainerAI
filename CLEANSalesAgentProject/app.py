"""
Sales Training AI - Main Flask Application

This is the main entry point for the Sales Training AI application.
The app uses Flask with a SQLite database for storing user data and conversations.
"""
import os
from datetime import datetime
import secrets
from flask import Flask, render_template, g, session, redirect, url_for
from flask_login import LoginManager
from config_manager import config
from models import db, User

def create_app():
    """Create and configure Flask application."""
    
    # Create and configure app
    app = Flask(__name__)
    
    # Load configuration
    app.config['SECRET_KEY'] = config.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///salestrainer.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_COOKIE_SECURE'] = config.get('SESSION_COOKIE_SECURE', True)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Initialize extensions
    db.init_app(app)
    
    # Initialize login manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Generate CSRF token for all requests
    @app.before_request
    def before_request():
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_hex(16)
        g.csrf_token = session['_csrf_token']
        g.csp_nonce = secrets.token_hex(16)
        g.current_year = datetime.now().year
    
    # Register blueprints
    from auth_routes import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)
    
    from chat_routes import chat as chat_blueprint
    app.register_blueprint(chat_blueprint)
    
    # Root route
    @app.route('/')
    def index():
        return render_template('landing.html')
    
    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500
    
    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('429.html'), 429
    
    return app

# Create database tables if they don't exist
def setup_database(app):
    with app.app_context():
        db.create_all()
        print("Database tables created")

if __name__ == '__main__':
    app = create_app()
    
    # Check if database exists, if not create tables
    if not os.path.exists('instance/salestrainer.db'):
        setup_database(app)
    
    # Run the application
    app.run(
        host=config.get('FLASK_HOST', '0.0.0.0'),
        port=int(config.get('FLASK_PORT', '5000')),
        debug=config.get('FLASK_DEBUG', False)
    )
