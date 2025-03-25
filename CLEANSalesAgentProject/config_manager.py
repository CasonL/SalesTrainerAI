"""
Configuration Manager for Sales Training AI

This module provides a secure way to manage application configuration and sensitive credentials.
"""

import os
import logging
import secrets
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ConfigManager")

class ConfigManager:
    """Secure configuration manager that handles environment variables and sensitive credentials."""
    
    _instance = None
    _config = {}
    
    def __new__(cls):
        """Implement as a singleton to ensure consistent configuration access."""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the configuration manager if not already initialized."""
        if not getattr(self, '_initialized', False):
            self._load_environment()
            self._initialize_config()
            self._initialized = True
    
    def _load_environment(self) -> None:
        """Load environment variables from .env file."""
        # Load from .env file
        load_dotenv()
        logger.info("Environment variables loaded")
    
    def _initialize_config(self) -> None:
        """Initialize configuration with required settings and defaults."""
        # Core application settings
        self._config = {
            # Flask settings
            'FLASK_SECRET_KEY': os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32)),
            'FLASK_DEBUG': os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
            'FLASK_HOST': os.getenv('FLASK_HOST', '0.0.0.0'),
            'FLASK_PORT': int(os.getenv('FLASK_PORT', '5000')),
            
            # API Keys
            'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
            
            # Google OAuth settings
            'GOOGLE_CLIENT_ID': os.getenv('GOOGLE_CLIENT_ID'),
            'GOOGLE_CLIENT_SECRET': os.getenv('GOOGLE_CLIENT_SECRET'),
            
            # Security settings
            'SESSION_LIFETIME': int(os.getenv('SESSION_LIFETIME', '86400')),  # 24 hours
            'SESSION_REFRESH_EACH_REQUEST': True,
            'SESSION_COOKIE_SECURE': os.getenv('SESSION_COOKIE_SECURE', 'True').lower() == 'true',
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax',
            'CSRF_ENABLED': True,
            'PASSWORD_MIN_LENGTH': int(os.getenv('PASSWORD_MIN_LENGTH', '8')),
            'RATE_LIMIT_WINDOW': int(os.getenv('RATE_LIMIT_WINDOW', '60')),  # Window in seconds
            'RATE_LIMIT': int(os.getenv('RATE_LIMIT', '10')),  # Max requests per window
            'MAX_LOGIN_ATTEMPTS': int(os.getenv('MAX_LOGIN_ATTEMPTS', '5')),
            'LOCKOUT_TIME': int(os.getenv('LOCKOUT_TIME', '300')),  # Seconds
        }
        
        # Check for required API keys
        self._validate_required_keys()
    
    def _validate_required_keys(self) -> None:
        """Validate that required API keys are present."""
        required_keys = ['ANTHROPIC_API_KEY', 'FLASK_SECRET_KEY']
        missing_keys = [key for key in required_keys if not self._config.get(key)]
        
        if missing_keys:
            logger.warning(f"Missing required configuration keys: {', '.join(missing_keys)}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: The configuration key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            The configuration value or default
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value at runtime.
        
        Args:
            key: The configuration key to set
            value: The value to set
        """
        self._config[key] = value
        logger.debug(f"Configuration updated: {key}")
    
    def is_production(self) -> bool:
        """
        Check if the application is running in production mode.
        
        Returns:
            True if running in production, False otherwise
        """
        return not self.get('FLASK_DEBUG', False)

# Create a singleton instance for import and use elsewhere
config = ConfigManager()