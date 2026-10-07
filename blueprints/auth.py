"""
Authentication blueprint handling login, signup, admin authentication, and logout.
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from services.auth_service import AuthService
from blueprints.helpers import is_safe_url
from extensions import limiter

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/signup', methods=['GET', 'POST'], endpoint='signup')
@limiter.limit("5 per minute")
def signup() -> str:
    """Handle user registration."""
    if request.method == 'POST':
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')

        success, message, user_id = AuthService.register_user(name, email, password)
        if success:
            flash(message, 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'error')
            return render_template('signup.html')

    return render_template('signup.html')


def _clear_auth_session() -> None:
    """Clear user session variables and stale flash messages while preserving CSRF protection token."""
    session.pop('user_id', None)
    session.pop('name', None)
    session.pop('email', None)
    session.pop('user_role', None)
    session.pop('_flashes', None)


@auth_bp.route('/login', methods=['GET', 'POST'], endpoint='login')
@limiter.limit("100 per minute")
def login():
    """Handle user login with fast JSON API and standard form support."""
    if session.get('user_role') == 'customer' and 'user_id' in session:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'redirect_url': url_for('main.index')}), 200
        return redirect(url_for('main.index'))

    next_url = request.args.get('next') or request.form.get('next')
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json'

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json() or {}
            email = data.get('email', '')
            password = data.get('password', '')
            next_url = data.get('next') or next_url
        else:
            email = request.form.get('email', '')
            password = request.form.get('password', '')

        success, message, user = AuthService.authenticate_user(email, password)

        if not success:
            if is_ajax:
                return jsonify({
                    'success': False,
                    'message': message,
                    'is_admin': bool(user and user.get('role') == 'admin'),
                    'redirect_url': url_for('auth.admin_login') if (user and user.get('role') == 'admin') else None
                }), 400
            flash(message, 'error')
            if user and user.get('role') == 'admin':
                return redirect(url_for('auth.admin_login'))
            return render_template('login.html', next_url=next_url)

        # Safely reset auth keys and set customer session
        _clear_auth_session()
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['email'] = user['email']
        session['user_role'] = 'customer'
        session.permanent = True

        logger.info(f"Customer {email} logged in successfully")

        target_url = next_url if (next_url and is_safe_url(next_url)) else url_for('main.index')
        if is_ajax:
            return jsonify({'success': True, 'message': 'Login successful!', 'redirect_url': target_url}), 200

        return redirect(target_url)

    return render_template('login.html', next_url=next_url)



@auth_bp.route('/admin_login', methods=['GET', 'POST'], endpoint='admin_login')
@limiter.limit("100 per minute")
def admin_login() -> str:
    """Handle dedicated administrator authentication."""
    if session.get('user_role') == 'admin' and 'user_id' in session:
        return redirect(url_for('admin.admin_dashboard'))

    next_url = request.args.get('next') or request.form.get('next')

    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')

        success, message, admin_user = AuthService.authenticate_admin(email, password)

        if not success:
            flash(message, 'error')
            return render_template('admin_login.html', next_url=next_url)

        # Safely reset auth keys and set admin session
        _clear_auth_session()
        session['user_id'] = admin_user['id']
        session['name'] = admin_user['name']
        session['email'] = admin_user['email']
        session['user_role'] = 'admin'
        session.permanent = True

        logger.info(f"Admin {email} authenticated successfully")
        return redirect(url_for('admin.admin_dashboard'))

    return render_template('admin_login.html', next_url=next_url)


@auth_bp.route('/logout', endpoint='logout')
def logout():
    """Handle user logout."""
    user_id = session.get('user_id')
    email = session.get('email')

    _clear_auth_session()
    logger.info(f"User #{user_id} ({email}) logged out")
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


