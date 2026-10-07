"""
Daily Drop E-Commerce Application.

A Flask-based e-commerce platform for selling daily essentials and household items,
backed by high-performance Neon PostgreSQL and structured with modular Blueprints.
"""
import logging
import os
import json
from typing import Tuple, Optional
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_wtf.csrf import CSRFError


from config import config_dict, Config
from database import init_database, DatabaseError
from extensions import csrf, limiter
from blueprints import register_blueprints

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(config_name: Optional[str] = None) -> Flask:
    """
    Application factory initializing configuration, extensions, error handlers, and blueprints.
    """
    app = Flask(__name__)

    env = config_name or os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config_dict.get(env, config_dict['default']))

    # Initialize extensions
    csrf.init_app(app)
    limiter.init_app(app)

    # Register template filters
    @app.template_filter('from_json_or_list')
    def from_json_or_list(val):
        """Custom template filter to parse JSON string into list/dict or return if already parsed."""
        if isinstance(val, (list, dict)):
            return val
        try:
            return json.loads(val)
        except Exception:
            return []

    # Register error handlers
    @app.errorhandler(404)
    def not_found_error(error) -> Tuple[str, int]:
        """Handle 404 errors."""
        logger.warning(f"404 error: {error}")
        try:
            return render_template('404.html'), 404
        except Exception:
            return "<h2 style='color:#fff; background:#020805; padding:50px; text-align:center;'>404 - Page Not Found</h2>", 404

    @app.errorhandler(500)
    def internal_error(error) -> Tuple[str, int]:
        """Handle 500 errors."""
        logger.error(f"500 error: {error}")
        try:
            return render_template('500.html'), 500
        except Exception:
            return "<h2 style='color:#fff; background:#020805; padding:50px; text-align:center;'>500 - Internal Server Error</h2>", 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        """Handle CSRF expiration without crashing with raw 400 Bad Request."""
        logger.warning(f"CSRF error handled: {error.description}")
        flash("Your form session expired. Please try logging in again.", "error")
        return redirect(request.referrer or url_for('auth.login'))

    @app.errorhandler(429)
    def ratelimit_handler(e):
        """Handle rate limit error smoothly."""
        logger.warning(f"Rate limit exceeded: {e.description}")
        flash("Too many attempts. Please wait a few seconds and try again.", "error")
        return redirect(request.referrer or url_for('auth.login'))

    @app.after_request
    def set_auth_cookie(response):
        """Synchronize client-side cookie with session state for frontend cart."""
        if 'user_id' in session:
            response.set_cookie('is_logged_in', 'true', samesite='Lax', path='/')
        else:
            response.set_cookie('is_logged_in', 'false', samesite='Lax', path='/')
        return response

    @app.context_processor
    def inject_global_auth():
        return {
            'is_logged_in': bool('user_id' in session),
            'current_user_name': session.get('name', ''),
            'current_user_role': session.get('user_role', '')
        }



    # Register all modular blueprints
    register_blueprints(app)

    # Initialize database on startup
    with app.app_context():
        try:
            init_database()
            logger.info("Neon PostgreSQL Database initialized successfully")
        except DatabaseError as e:
            logger.error(f"Failed to initialize Neon PostgreSQL database: {e}")

    return app


# Default app instance for WSGI / CLI execution
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', os.environ.get('FLASK_RUN_PORT', 5000)))
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', True), threaded=True)


