"""
Utility functions module.

This module contains validation, sanitization, and helper functions
used throughout the application.
"""

import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Email regex pattern
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Phone regex pattern (allows various formats)
PHONE_REGEX = r'^[\d\s\-\+\(\)]{10,}$'


def is_valid_email(email: str) -> bool:
    """
    Validate email format.

    Args:
        email: Email string to validate.

    Returns:
        True if valid email format, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False
    return bool(re.match(EMAIL_REGEX, email))


def is_valid_phone(phone: str) -> bool:
    """
    Validate phone number format.

    Args:
        phone: Phone number string to validate.

    Returns:
        True if valid phone format, False otherwise.
    """
    if not phone or not isinstance(phone, str):
        return False
    return bool(re.match(PHONE_REGEX, phone))


def validate_user_input(name: str, email: str, password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate user registration input.

    Args:
        name: User's name.
        email: User's email.
        password: User's password.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if not name or len(name.strip()) < 2:
        return False, "Name must be at least 2 characters long"

    if not is_valid_email(email):
        return False, "Invalid email format"

    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters long"

    return True, None


def sanitize_string(value: str) -> str:
    """
    Sanitize string input to prevent injection attacks.

    Args:
        value: String to sanitize.

    Returns:
        Sanitized string.
    """
    if not isinstance(value, str):
        return ""
    return value.strip()[:500]  # Limit length


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number by removing non-digit characters.

    Args:
        phone: Phone number to normalize.

    Returns:
        Normalized phone number.
    """
    if not phone:
        return ""
    return re.sub(r'\D', '', phone)


def validate_order_data(
    full_name: str,
    phone_number: str,
    address: str,
    products: list
) -> Tuple[bool, Optional[str]]:
    """
    Validate order data.

    Args:
        full_name: Customer's full name.
        phone_number: Customer's phone number.
        address: Delivery address.
        products: List of products in order.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if not full_name or len(full_name.strip()) < 2:
        return False, "Please provide a valid name"

    if not is_valid_phone(phone_number):
        return False, "Please provide a valid phone number"

    if not address or len(address.strip()) < 3:
        return False, "Please provide a valid address"

    if not products or not isinstance(products, list):
        return False, "Order must contain at least one product"

    return True, None


def validate_contact_data(name: str, email: str, subject: str, message: str) -> Tuple[bool, Optional[str]]:
    """
    Validate contact form data.

    Args:
        name: Sender's name.
        email: Sender's email.
        subject: Message subject.
        message: Message body.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if not name or len(name.strip()) < 2:
        return False, "Please provide a valid name"

    if not is_valid_email(email):
        return False, "Please provide a valid email"

    if not subject or len(subject.strip()) < 3:
        return False, "Subject must be at least 3 characters"

    if not message or len(message.strip()) < 10:
        return False, "Message must be at least 10 characters"

    return True, None
