"""
Error handling routes for Sales Training AI application.

This module provides custom error pages and handling for various HTTP errors.
"""

from flask import Blueprint, render_template, request, g

# Create blueprint for error pages
errors = Blueprint('errors', __name__)

@errors.app_errorhandler(404)
def page_not_found(e):
    """404 Not Found error handler."""
    return render_template('errors/404.html'), 404

@errors.app_errorhandler(500)
def internal_server_error(e):
    """500 Internal Server Error handler."""
    return render_template('errors/500.html'), 500

@errors.app_errorhandler(403)
def forbidden(e):
    """403 Forbidden error handler."""
    return render_template('errors/403.html'), 403

@errors.app_errorhandler(429)
def too_many_requests(e):
    """429 Too Many Requests error handler."""
    retry_after = request.headers.get('Retry-After', '60')
    return render_template('errors/429.html', retry_after=retry_after), 429, {'Retry-After': retry_after}

@errors.route('/too-many-requests')
def too_many_requests_page():
    """Direct access to rate limit exceeded page."""
    return render_template('errors/429.html', retry_after='60'), 429, {'Retry-After': '60'}