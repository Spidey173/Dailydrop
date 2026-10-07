"""
Contact service managing contact message processing and saving.
"""
from typing import Optional, Tuple
import logging
from database import get_db_connection, DatabaseError
from utils import validate_contact_data, sanitize_string

logger = logging.getLogger(__name__)


_CONTACT_CACHE = None
_CONTACT_CACHE_TIME = 0.0
_CONTACT_CACHE_TTL = 300.0


class ContactService:
    """Service providing contact message submission handling."""

    @staticmethod
    def submit_message(user_id: Optional[int], name: str, email: str, phone: str,
                       subject: str, message: str) -> Tuple[bool, str, Optional[int]]:
        """Validate and store a contact inquiry message."""
        global _CONTACT_CACHE
        name = sanitize_string(name)
        email = sanitize_string(email)
        subject = sanitize_string(subject)
        message = sanitize_string(message)

        is_valid, error_msg = validate_contact_data(name, email, subject, message)
        if not is_valid:
            return False, error_msg, None

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO contact_messages (user_id, name, email, phone, subject, message)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    ''', (user_id, name, email, phone, subject, message))
                    message_id = cursor.fetchone()[0]

            _CONTACT_CACHE = None
            logger.info(f"Contact message #{message_id} submitted from {email}")
            return True, 'Your message has been sent successfully!', message_id
        except DatabaseError as e:
            logger.error(f"Error saving contact message: {e}")
            return False, 'Error processing your request. Please try again.', None

    @staticmethod
    def get_all_messages() -> list:
        """Retrieve all contact inquiry messages from customers with in-memory caching."""
        global _CONTACT_CACHE, _CONTACT_CACHE_TIME
        import time
        now = time.time()

        if _CONTACT_CACHE is not None and (now - _CONTACT_CACHE_TIME < _CONTACT_CACHE_TTL):
            return _CONTACT_CACHE

        try:
            from psycopg2.extras import RealDictCursor
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute('''
                        SELECT id, user_id, name, email, phone, subject, message, timestamp
                        FROM contact_messages
                        ORDER BY timestamp DESC
                    ''')
                    rows = cursor.fetchall()
                    _CONTACT_CACHE = [dict(row) for row in rows]
                    _CONTACT_CACHE_TIME = now
                    return _CONTACT_CACHE
        except Exception as e:
            logger.error(f"Error retrieving contact messages: {e}")
            return _CONTACT_CACHE or []

    @staticmethod
    def delete_message(message_id: int) -> Tuple[bool, str]:
        """Delete or dismiss a customer contact message by ID."""
        global _CONTACT_CACHE
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM contact_messages WHERE id = %s', (message_id,))
            _CONTACT_CACHE = None
            logger.info(f"Deleted contact message #{message_id}")
            return True, 'Message deleted successfully.'
        except Exception as e:
            logger.error(f"Error deleting contact message #{message_id}: {e}")
            return False, f'Error deleting message: {e}'


