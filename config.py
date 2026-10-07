"""
Application configuration module.

This module contains centralized configuration settings for the Daily Drop
application, including database paths, Flask settings, and security parameters.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Get environment or use defaults
ENV = os.getenv('FLASK_ENV', 'development')
DEBUG = ENV == 'development'


class Config:
    """Base configuration."""

    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'daily-drop-neon-secure-key-2026')
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
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

    # Razorpay Payment Gateway (Loaded securely from environment variables)
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
    RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', os.getenv('RAZORPAY_KEY_SECRET', ''))


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration."""

    DEBUG = True
    TESTING = True


# Configuration dictionary
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

