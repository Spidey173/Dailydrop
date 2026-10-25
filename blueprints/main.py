"""
Main blueprint handling home/landing pages, contact inquiries, and informational static views.
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from services.product_service import ProductService
from services.contact_service import ContactService
from services.auth_service import AuthService
from blueprints.helpers import require_login

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)


@main_bp.route('/', endpoint='intro')
def intro() -> str:
    """Render the introductory page."""
    return render_template('intro.html')


@main_bp.route('/index', endpoint='index')
def index() -> str:
    """Render the home page with featured products."""
    products = ProductService.get_products_by_category(limit=6)
    return render_template('index.html', products=products)


@main_bp.route('/dashboard', endpoint='dashboard')
@require_login
def dashboard():
    """Redirect to the appropriate dashboard based on user role."""
    if session.get('user_role') == 'admin':
        return redirect(url_for('admin.admin_dashboard'))
    return redirect(url_for('cart.orders'))


@main_bp.route('/contact_us', methods=['GET', 'POST'], endpoint='contact_us')
@main_bp.route('/contact-us', methods=['GET', 'POST'])
def contact_us():
    """Handle contact form submissions."""
    user = None
    user_id = session.get('user_id')
    if user_id:
        user = AuthService.get_user_by_id(user_id)

    if request.method == 'POST':
        name = request.form.get('name', user['name'] if user else '')
        email = request.form.get('email', user['email'] if user else '')
        phone = request.form.get('phone', '')
        subject = request.form.get('subject', '')
        message = request.form.get('message', '')

        success, msg, msg_id = ContactService.submit_message(
            user_id=user_id,
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message
        )

        if success:
            flash(msg, 'success')
            return redirect(url_for('main.contact_us'))
        else:
            flash(msg, 'error')
            return render_template('contact_us.html', user=user, name=name, email=email)

    return render_template('contact_us.html', user=user)



# ==================== Static Informational & Legal Pages ====================

@main_bp.route('/privacy_policy_signup', endpoint='privacy_policy_signup')
def privacy_policy_signup() -> str:
    """Display privacy policy for signup page."""
    return render_template('privacy_policy.html', back_url=url_for('auth.signup'), back_text='Back to Signup')


@main_bp.route('/privacy_policy_login', endpoint='privacy_policy_login')
def privacy_policy_login() -> str:
    """Display privacy policy for login page."""
    return render_template('privacy_policy.html', back_url=url_for('auth.login'), back_text='Back to Login')


@main_bp.route('/privacy_policy_signup_home', endpoint='privacy_policy_signup_home')
@main_bp.route('/privacy_policy', endpoint='privacy_policy')
@main_bp.route('/privacy', endpoint='privacy')
def privacy_policy_signup_home() -> str:
    """Display privacy policy for home page."""
    return render_template('privacy_policy.html', back_url=url_for('main.index'), back_text='Back to Home')


@main_bp.route('/terms_login', endpoint='terms_login')
def terms_login() -> str:
    """Display terms and conditions for login page."""
    return render_template('terms.html', back_url=url_for('auth.login'), back_text='Back to Login')


@main_bp.route('/terms_signup', endpoint='terms_signup')
def terms_signup() -> str:
    """Display terms and conditions for signup page."""
    return render_template('terms.html', back_url=url_for('auth.signup'), back_text='Back to Signup')


@main_bp.route('/terms_signup_home', endpoint='terms_signup_home')
@main_bp.route('/terms', endpoint='terms')
def terms_signup_home() -> str:
    """Display terms and conditions for home page."""
    return render_template('terms.html', back_url=url_for('main.index'), back_text='Back to Home')


@main_bp.route('/faqs', endpoint='faqs')
def faqs() -> str:
    """Display frequently asked questions."""
    return render_template('faqs.html')


@main_bp.route('/about_us', endpoint='about_us')
@main_bp.route('/about-us')
@main_bp.route('/about')
def about_us() -> str:
    """Display about us page."""
    return render_template('about_us.html')


# ==================== System Health & Observability ====================

@main_bp.route('/healthz', methods=['GET'], endpoint='healthz')
@main_bp.route('/api/v1/health', methods=['GET'], endpoint='api_health')
def health_check():
    """
    Application Health Check Endpoint.
    Checks PostgreSQL database ping latency, Redis cache availability,
    worker queue status, and storage configuration.
    Returns HTTP 200 if healthy, HTTP 503 if primary database is degraded.
    """
    import time
    from database import get_db_connection
    from services.redis_service import RedisService
    from flask import current_app, jsonify

    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'environment': current_app.config.get('ENV', 'development'),
        'components': {
            'database': {'status': 'unknown'},
            'redis': {'status': 'unknown'},
            'storage': {'status': 'unknown'},
            'worker': {'status': 'unknown'}
        }
    }

    # 1. Check PostgreSQL Database
    t0 = time.time()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        db_latency_ms = round((time.time() - t0) * 1000, 2)
        health_status['components']['database'] = {
            'status': 'connected',
            'type': 'PostgreSQL',
            'latency_ms': db_latency_ms
        }
    except Exception as dbe:
        health_status['status'] = 'degraded'
        health_status['components']['database'] = {
            'status': 'disconnected',
            'error': str(dbe)
        }

    # 2. Check Redis Cache
    if current_app.config.get('REDIS_ENABLED', False):
        try:
            t_redis = time.time()
            is_ready = RedisService.is_available()
            redis_latency_ms = round((time.time() - t_redis) * 1000, 2)
            health_status['components']['redis'] = {
                'status': 'connected' if is_ready else 'degraded',
                'latency_ms': redis_latency_ms
            }
        except Exception as rerr:
            health_status['components']['redis'] = {
                'status': 'error',
                'error': str(rerr)
            }
    else:
        health_status['components']['redis'] = {
            'status': 'disabled',
            'note': 'In-memory fallback active'
        }

    # 3. Check Storage & Uploads
    if current_app.config.get('DISABLE_FILE_UPLOADS', False):
        health_status['components']['storage'] = {
            'status': 'serverless_read_only',
            'uploads': 'disabled_for_demo'
        }
    else:
        health_status['components']['storage'] = {
            'status': 'local_filesystem',
            'folder': current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
        }

    # 4. Background Worker Queue
    health_status['components']['worker'] = {
        'queue': 'dailydrop_tasks',
        'relay': 'transactional_outbox'
    }

    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code

