"""
Database initialization script for Sales Training AI.

Run this script to create the initial database schema.
"""

import os
from flask import Flask
from models import db, User
from werkzeug.security import generate_password_hash
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DatabaseInit")

def init_db():
    """Initialize the database with required tables."""
    # Create a minimal Flask app for this script
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/salestrainer.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize SQLAlchemy with this app
    db.init_app(app)
    
    # Ensure the instance folder exists
    os.makedirs('instance', exist_ok=True)
    
    with app.app_context():
        logger.info("Creating database tables...")
        db.create_all()
        
        # Check if we need to create an admin user
        admin_email = os.environ.get('ADMIN_EMAIL')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        
        if admin_email and admin_password:
            existing_admin = User.query.filter_by(email=admin_email).first()
            
            if not existing_admin:
                logger.info(f"Creating admin user: {admin_email}")
                admin = User(
                    name="Administrator",
                    email=admin_email,
                    role="admin"
                )
                admin.set_password(admin_password)
                
                # Initialize default skills
                admin.skills_dict = {
                    "rapport_building": 80,
                    "needs_discovery": 85,
                    "objection_handling": 90,
                    "closing": 85,
                    "product_knowledge": 95
                }
                
                db.session.add(admin)
                db.session.commit()
                logger.info("Admin user created successfully")
            else:
                logger.info("Admin user already exists")
        
        logger.info("Database initialization completed successfully")

if __name__ == "__main__":
    init_db()