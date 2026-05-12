"""
User model for the NIS2 Compliance Platform.
Standalone — no dependency on external CRM/VAT modules.
"""

import os
import secrets
from datetime import datetime, timedelta

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db

SCHEMA = os.environ.get('DB_SCHEMA') or None
_sp = f'{SCHEMA}.' if SCHEMA else ''


class User(UserMixin, db.Model):
    """User with authentication and subscription plan."""

    __tablename__ = 'users'
    __table_args__ = ({'schema': SCHEMA} if SCHEMA else {})

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Profile
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    company_name = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    country = db.Column(db.String(2), default='DE')

    # Account status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_email_confirmed = db.Column(db.Boolean, default=False)
    email_confirmation_token = db.Column(db.String(100), unique=True)

    # Subscription: 'trial' | 'basic' | 'professional' | 'enterprise'
    subscription_plan = db.Column(db.String(20), default='trial')
    trial_ends_at = db.Column(db.DateTime)
    stripe_customer_id = db.Column(db.String(100))
    stripe_subscription_id = db.Column(db.String(100))

    # Password reset
    password_reset_token = db.Column(db.String(100), unique=True)
    password_reset_expires = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_login = db.Column(db.DateTime)

    def __repr__(self):
        return f'<User {self.email}>'

    # ── Password ──────────────────────────────────────────────────────────

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # ── Email confirmation ────────────────────────────────────────────────

    def generate_confirmation_token(self) -> str:
        self.email_confirmation_token = secrets.token_urlsafe(32)
        return self.email_confirmation_token

    def confirm_email(self):
        self.is_email_confirmed = True
        self.email_confirmation_token = None

    # ── Password reset ────────────────────────────────────────────────────

    def generate_reset_token(self) -> str:
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=2)
        return self.password_reset_token

    def is_reset_token_valid(self, token: str) -> bool:
        return (
            self.password_reset_token == token
            and self.password_reset_expires
            and datetime.utcnow() < self.password_reset_expires
        )

    # ── Subscription helpers ──────────────────────────────────────────────

    @property
    def is_trial_active(self) -> bool:
        if self.subscription_plan != 'trial':
            return False
        if not self.trial_ends_at:
            return False
        return datetime.utcnow() < self.trial_ends_at

    @property
    def has_access(self) -> bool:
        """Full NIS2 access: trial (active) OR paid plan OR admin."""
        if self.is_admin:
            return True
        if self.subscription_plan in ('basic', 'professional', 'enterprise'):
            return True
        return self.is_trial_active

    @property
    def display_name(self) -> str:
        if self.first_name:
            return f'{self.first_name} {self.last_name or ""}'.strip()
        return self.company_name or self.email.split('@')[0]

    @property
    def plan_label(self) -> str:
        labels = {
            'trial': 'Testphase',
            'basic': 'Basic',
            'professional': 'Professional',
            'enterprise': 'Enterprise',
        }
        return labels.get(self.subscription_plan, self.subscription_plan)
