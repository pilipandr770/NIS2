"""
NIS2 Compliance Platform — Configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # ── Database ──────────────────────────────────────────────────────────
    _db_url = os.environ.get('DATABASE_URL') or \
              os.environ.get('LOCAL_DATABASE_URL') or \
              'postgresql://postgres:postgres@localhost:5432/nis2_dev'

    # Render.com uses postgres:// — fix it
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    _engine_opts = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 5,
        'max_overflow': 10,
    }
    if _db_url.startswith('postgresql://'):
        _connect_args = {
            'options': f'-csearch_path={os.environ.get("DB_SCHEMA", "public")}',
            'connect_timeout': 10,
        }
        if 'render.com' in _db_url or os.environ.get('RENDER'):
            _connect_args['sslmode'] = 'require'
        _engine_opts['connect_args'] = _connect_args
    SQLALCHEMY_ENGINE_OPTIONS = _engine_opts

    # ── Mail / SMTP ───────────────────────────────────────────────────────
    MAIL_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('SMTP_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME = os.environ.get('SMTP_USERNAME')
    MAIL_PASSWORD = os.environ.get('SMTP_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get(
        'MAIL_DEFAULT_SENDER', 'noreply@nis2-compliance.de'
    )

    # ── AI (Claude) ───────────────────────────────────────────────────────
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

    # ── Stripe ────────────────────────────────────────────────────────────
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_BASIC = os.environ.get('STRIPE_PRICE_BASIC')
    STRIPE_PRICE_PROFESSIONAL = os.environ.get('STRIPE_PRICE_PROFESSIONAL')

    # ── NIS2 Microservice (optional Docker pentest engine) ────────────────
    NIS2_MICROSERVICE_URL = os.environ.get('NIS2_MICROSERVICE_URL')

    # ── Trial period (days) ───────────────────────────────────────────────
    TRIAL_DAYS = int(os.environ.get('TRIAL_DAYS', 14))

    # ── Site URL ──────────────────────────────────────────────────────────
    BASE_URL = os.environ.get('SITE_BASE_URL', 'https://nis2-compliance.de')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False

    def __init__(self):
        required = {
            'SECRET_KEY': os.environ.get('SECRET_KEY'),
            'DATABASE_URL': os.environ.get('DATABASE_URL'),
        }
        missing = [k for k, v in required.items()
                   if not v or v == 'dev-secret-key-change-in-production']
        if missing:
            raise RuntimeError(
                f'Production startup blocked. Missing env vars: {", ".join(missing)}'
            )


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    DISABLE_NIS2_SCHEDULER = True
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
