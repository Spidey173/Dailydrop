"""
Blueprint helper functions and route authentication decorators.
"""
from functools import wraps
from urllib.parse import urlparse, urljoin
import logging
from flask import request, session, redirect, url_for, flash, jsonify

logger = logging.getLogger(__name__)


def is_safe_url(target: str) -> bool:
    """
    Validate if a URL is safe for redirect operations.
    """
    try:
        ref_url = urlparse(request.host_url)
        test_url = urlparse(urljoin(request.host_url, target))
        return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
    except Exception as e:
        logger.warning(f"Error validating URL: {e}")
        return False


def require_login(f):
    """
    Decorator to require customer login for a route.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    Decorator to require administrator role for a route.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Admin session expired. Please log in again.'}), 401
            flash('Administrator authentication required.', 'error')
            return redirect(url_for('auth.admin_login', next=request.url))
        return f(*args, **kwargs)

    return decorated_function
