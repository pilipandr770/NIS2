"""
NIS2 Compliance Platform — Application Factory
"""

import os
import logging
from datetime import datetime, timedelta

from flask import Flask, render_template
from sqlalchemy import text

from config import config
from app.extensions import db, login_manager, mail, csrf, migrate

logger = logging.getLogger(__name__)


def create_app(config_name: str = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    # Load config
    cfg_cls = config[config_name]
    cfg_obj = cfg_cls() if isinstance(cfg_cls, type) else cfg_cls
    app.config.from_object(cfg_obj)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # User loader
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Ensure DB schema exists (PostgreSQL)
    _ensure_schema(app)

    # ── Blueprints ────────────────────────────────────────────────────────
    from auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from payments.routes import payments_bp
    app.register_blueprint(payments_bp, url_prefix='/payments')

    from app.nis2 import nis2_bp
    app.register_blueprint(nis2_bp, url_prefix='/nis2')

    # ── NIS2 monitoring scheduler ─────────────────────────────────────────
    try:
        from app.nis2.continuous_monitoring.scheduler import start_monitoring_scheduler
        start_monitoring_scheduler(app)
    except Exception as exc:
        logger.warning('Monitoring scheduler not started: %s', exc)

    # ── Landing / root route ──────────────────────────────────────────────
    @app.route('/')
    def index():
        return render_template('landing.html')

    # ── Context processors ────────────────────────────────────────────────
    @app.context_processor
    def inject_globals():
        return {
            'now': datetime.utcnow(),
            'app_name': 'NIS2 Compliance Platform',
        }

    # ── Error pages ───────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    return app


def _ensure_schema(app: Flask):
    schema = os.environ.get('DB_SCHEMA')
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not schema or not db_uri.startswith('postgresql://'):
        return
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
                conn.commit()
    except Exception as exc:
        logger.error('Failed to ensure schema %s: %s', schema, exc)
