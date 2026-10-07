"""
Authentication service handling user registration, password hashing, and login verification.
"""
from typing import Optional, Dict, Any, Tuple
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, DatabaseError, get_user_by_email, get_user_by_id, clear_user_cache
from utils import validate_user_input, is_valid_email, sanitize_string

logger = logging.getLogger(__name__)


class AuthService:
    """Service providing authentication and user management functions."""

    @staticmethod
    def register_user(name: str, email: str, password: str) -> Tuple[bool, str, Optional[int]]:
        """
        Validate and register a new customer user.

        Returns:
            Tuple of (success, message, user_id).
        """
        name = sanitize_string(name)
        email = sanitize_string(email)

        is_valid, error_msg = validate_user_input(name, email, password)
        if not is_valid:
            return False, error_msg, None

        if 'admin' in email.lower():
            return False, 'Admin accounts cannot be created via signup. Please log in directly.', None

        if get_user_by_email(email):
            return False, 'Email already registered!', None

        try:
            hashed_password = generate_password_hash(password)
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO users (name, email, password, role)
                        VALUES (%s, %s, %s, 'customer')
                        RETURNING id
                    ''', (name, email, hashed_password))
                    user_id = cursor.fetchone()[0]

            clear_user_cache(email, user_id)
            logger.info(f"User {email} registered successfully with ID {user_id}")
            return True, 'Registration successful! Please login.', user_id
        except DatabaseError as e:
            logger.error(f"Error registering user: {e}")
            return False, 'Registration failed. Please try again.', None

    @staticmethod
    def authenticate_user(email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Authenticate customer credentials.

        Returns:
            Tuple of (success, message, user_dict).
        """
        email = sanitize_string(email)
        if not is_valid_email(email) or not password:
            return False, 'Invalid email or password', None

        try:
            user = get_user_by_email(email)
            if not user or not check_password_hash(user['password'], password):
                logger.warning(f"Failed customer login attempt for {email}")
                return False, 'Invalid email or password', None

            if user.get('role') == 'admin':
                return False, 'Admin accounts must log in via the Admin Portal.', user

            return True, 'Login successful!', user
        except DatabaseError as e:
            logger.error(f"Error during customer authentication: {e}")
            return False, 'Login failed. Please try again.', None

    @staticmethod
    def authenticate_admin(email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Authenticate administrator credentials.

        Returns:
            Tuple of (success, message, admin_dict).
        """
        email = sanitize_string(email)
        if not is_valid_email(email) or not password:
            return False, 'Invalid admin email or password', None

        try:
            user = get_user_by_email(email)
            if not user or not check_password_hash(user['password'], password):
                logger.warning(f"Failed admin login attempt for {email}")
                return False, 'Invalid admin email or password', None

            if user.get('role') != 'admin':
                return False, 'Access denied. Customer accounts cannot use the Admin Portal.', None

            return True, 'Welcome to the Admin Control Panel!', user
        except DatabaseError as e:
            logger.error(f"Error during admin authentication: {e}")
            return False, 'Authentication failed. Please try again.', None

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve user by ID."""
        return get_user_by_id(user_id)

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Retrieve user by email."""
        return get_user_by_email(email)

