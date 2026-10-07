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
def dashboard() -> str:
    """Display user dashboard."""
    return render_template('dashboard.html')


@main_bp.route('/contact_us', methods=['GET', 'POST'], endpoint='contact_us')
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
def about_us() -> str:
    """Display about us page."""
    return render_template('about_us.html')
