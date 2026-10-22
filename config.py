"""
Application configuration module.

This module contains centralized configuration settings for the Daily Drop
application, including database paths, Flask settings, and security parameters.
"""

import os
from typing import Optional
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Get environment or use defaults
ENV = os.getenv('FLASK_ENV', 'development')
DEBUG = ENV == 'development'


# Known insecure placeholder keys that must never be used in production
INSECURE_SECRET_KEYS = {
    'daily-drop-neon-secure-key-2026',
    'change-this-to-a-secure-random-secret-key',
    'your-secret-key-here',
    'secret',
    'default',
    'admin',
    'password',
    ''
}


class Config:
    """Base configuration."""

    ENV = ENV
    DEBUG = DEBUG
    TESTING = False

    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    SESSION_COOKIE_SECURE = not DEBUG
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Database settings (Neon PostgreSQL)
    DATABASE_URL = os.getenv('DATABASE_URL', '')
    DB_MIN_CONN = int(os.getenv('DB_MIN_CONN', 3))
    DB_MAX_CONN = int(os.getenv('DB_MAX_CONN', 15))
    DB_TIMEOUT = 30

    # Redis Cache & Distributed Lock Settings
    REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    REDIS_SOCKET_TIMEOUT = float(os.getenv('REDIS_SOCKET_TIMEOUT', 2.0))
    REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'true').lower() in ('true', '1', 'yes')
    CACHE_CATALOG_TTL = int(os.getenv('CACHE_CATALOG_TTL', 600))  # 10 minutes
    IDEMPOTENCY_TTL = int(os.getenv('IDEMPOTENCY_TTL', 86400))  # 24 hours

    # Performance & Static asset caching
    SEND_FILE_MAX_AGE_DEFAULT = 43200  # 12 hours browser caching for static files
    TEMPLATES_AUTO_RELOAD = DEBUG

    # Pagination
    ITEMS_PER_PAGE = 12
    ORDERS_PER_PAGE = 10

    # File uploads
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
    DISABLE_FILE_UPLOADS = os.getenv('DISABLE_FILE_UPLOADS', 'false').lower() in ('true', '1', 'yes') or os.getenv('VERCEL') == '1'


    # Razorpay Payment Gateway (Loaded securely from environment variables)
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
    RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', os.getenv('RAZORPAY_KEY_SECRET', ''))

    @classmethod
    def validate_config(cls, env_name: Optional[str] = None) -> bool:
        """
        Validate configuration for security and completeness based on the target environment.
        Raises ValueError with clear guidance if a critical setting is missing or insecure.
        """
        target_env = (env_name or cls.ENV).lower()
        if cls.TESTING or target_env == 'testing':
            return True

        secret = cls.SECRET_KEY or ''
        if target_env == 'production':
            if not secret or secret in INSECURE_SECRET_KEYS or len(secret) < 16:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: Production requires a strong, unique SECRET_KEY. "
                    "Insecure or placeholder keys are rejected. Generate one via: "
                    "python -c 'import secrets; print(secrets.token_hex(32))'"
                )
            if not cls.DATABASE_URL:
                raise ValueError(
                    "CRITICAL CONFIGURATION ERROR: Production requires DATABASE_URL pointing to PostgreSQL."
                )
        return True


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    TESTING = False
    # Safe development default if SECRET_KEY is not defined locally
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-local-secret-key-not-for-production-use')


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration."""

    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'test-mock-secret-key-32bytes-secure-pytest')
    DATABASE_URL = os.getenv('DATABASE_URL') or 'sqlite:///:memory:'


# Configuration dictionary
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

