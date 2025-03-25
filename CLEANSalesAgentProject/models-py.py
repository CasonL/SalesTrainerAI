"""
Database models for the Sales Training AI application.

This module provides SQLAlchemy models for the simplified version of the app
that replaces Firebase with a local SQLite database.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import json

db = SQLAlchemy()

class User(db.Model, UserMixin):
    """User model for authentication and profile data."""
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # User stats and training data
    completed_roleplays = db.Column(db.Integer, default=0)
    sales_skills = db.Column(db.Text, default='{}')  # JSON string with skill ratings
    strengths = db.Column(db.Text, default='[]')     # JSON string with strengths list
    weaknesses = db.Column(db.Text, default='[]')    # JSON string with areas to improve
    
    # Google Auth
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    
    # Relationships
    conversations = db.relationship('Conversation', backref='user', lazy=True, cascade="all, delete-orphan")
    
    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against stored hash."""
        return check_password_hash(self.password_hash, password)
    
    @property
    def skills_dict(self):
        """Get sales skills as dictionary."""
        try:
            return json.loads(self.sales_skills)
        except:
            return {
                "rapport_building": 0,
                "needs_discovery": 0,
                "objection_handling": 0,
                "closing": 0,
                "product_knowledge": 0
            }
    
    @skills_dict.setter
    def skills_dict(self, value):
        """Set sales skills from dictionary."""
        self.sales_skills = json.dumps(value)
    
    @property
    def strengths_list(self):
        """Get strengths as list."""
        try:
            return json.loads(self.strengths)
        except:
            return []
    
    @strengths_list.setter
    def strengths_list(self, value):
        """Set strengths from list."""
        self.strengths = json.dumps(value)
    
    @property
    def weaknesses_list(self):
        """Get weaknesses as list."""
        try:
            return json.loads(self.weaknesses)
        except:
            return []
    
    @weaknesses_list.setter
    def weaknesses_list(self, value):
        """Set weaknesses from list."""
        self.weaknesses = json.dumps(value)
    
    def __repr__(self):
        return f'<User {self.email}>'


class Conversation(db.Model):
    """Conversation model for storing chat history."""
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), default="New Conversation")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Sales context information
    product_service = db.Column(db.Text, nullable=True)
    target_market = db.Column(db.String(50), nullable=True)
    sales_experience = db.Column(db.String(50), nullable=True)
    
    # AI persona for this conversation
    persona = db.Column(db.Text, nullable=True)
    
    # Relationships
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Conversation {self.id}: {self.title}>'


class Message(db.Model):
    """Message model for storing individual chat messages."""
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Message {self.id}: {self.role}>'
