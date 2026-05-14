"""
NIS2 Compliance Platform — Application Factory
"""

import os
import logging
from datetime import UTC, datetime, timedelta

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
        return db.session.get(User, int(user_id))

    # Ensure DB schema exists (PostgreSQL)
    _ensure_schema(app)

    # ── Blueprints ────────────────────────────────────────────────────────
    from auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from payments.routes import payments_bp
    app.register_blueprint(payments_bp, url_prefix='/payments')

    from app.nis2 import nis2_bp
    app.register_blueprint(nis2_bp, url_prefix='/nis2')

    from legal.routes import legal_bp
    app.register_blueprint(legal_bp, url_prefix='/legal')

    from app.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/superadmin')

    from seo import seo_bp
    app.register_blueprint(seo_bp)

    # ── NIS2 monitoring scheduler ─────────────────────────────────────────
    if not app.config.get('DISABLE_NIS2_SCHEDULER', False):
        try:
            from app.nis2.continuous_monitoring.scheduler import init_nis2_monitoring_scheduler
            app.nis2_scheduler = init_nis2_monitoring_scheduler(app)
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
            'now': datetime.now(UTC),
            'app_name': 'NIS2 Compliance Platform',
        }

    # ── CLI commands ──────────────────────────────────────────────────────
    import click

    @app.cli.command('create-admin')
    @click.option('--email', default='pylypchukandrii770@gmail.com')
    @click.option('--password', default='Dnepr75ok10$')
    @click.option('--plan', default='enterprise')
    def create_admin(email, password, plan):
        """Create or promote a user to super-admin."""
        user = User.query.filter_by(email=email).first()
        if user:
            user.is_admin = True
            user.is_active = True
            user.subscription_plan = plan
            user.set_password(password)
            db.session.commit()
            click.echo(f'Updated existing user {email} → admin=True, plan={plan}')
        else:
            user = User(
                email=email,
                first_name='Andrii',
                last_name='Admin',
                subscription_plan=plan,
                is_admin=True,
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            click.echo(f'Created admin user {email} (plan={plan})')

    # ── Error pages ───────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return render_template('errors/405.html'), 405

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
