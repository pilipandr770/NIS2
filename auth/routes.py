"""
Auth blueprint — Registration, Login, Logout, Email Confirmation, Password Reset.
"""

import logging
from datetime import datetime, timedelta

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message

from app.extensions import db, mail
from app.models import User

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')


# ── Register ──────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('nis2.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        company = request.form.get('company_name', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()

        # Validation
        if not email or not password:
            flash('E-Mail und Passwort sind erforderlich.', 'danger')
            return render_template('auth/register.html')

        if password != password2:
            flash('Passwörter stimmen nicht überein.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 8:
            flash('Passwort muss mindestens 8 Zeichen lang sein.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Diese E-Mail-Adresse ist bereits registriert.', 'danger')
            return render_template('auth/register.html')

        # Create user with 14-day trial
        trial_days = current_app.config.get('TRIAL_DAYS', 14)
        user = User(
            email=email,
            company_name=company,
            first_name=first_name,
            last_name=last_name,
            subscription_plan='trial',
            trial_ends_at=datetime.utcnow() + timedelta(days=trial_days),
        )
        user.set_password(password)
        user.generate_confirmation_token()

        db.session.add(user)
        db.session.commit()

        # Send confirmation email (best-effort)
        try:
            _send_confirmation_email(user)
        except Exception as exc:
            logger.warning('Could not send confirmation email: %s', exc)

        login_user(user)
        flash(
            f'Willkommen! Sie haben {trial_days} Tage kostenlosen Zugang. '
            'Bitte bestätigen Sie Ihre E-Mail-Adresse.',
            'success',
        )
        return redirect(url_for('nis2.dashboard'))

    return render_template('auth/register.html')


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('nis2.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Ungültige E-Mail-Adresse oder Passwort.', 'danger')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('Ihr Konto wurde deaktiviert. Bitte kontaktieren Sie den Support.', 'danger')
            return render_template('auth/login.html')

        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=remember)

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('nis2.dashboard'))

    return render_template('auth/login.html')


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sie wurden erfolgreich abgemeldet.', 'info')
    return redirect(url_for('index'))


# ── Email confirmation ────────────────────────────────────────────────────────

@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    user = User.query.filter_by(email_confirmation_token=token).first()
    if not user:
        flash('Ungültiger oder abgelaufener Bestätigungslink.', 'danger')
        return redirect(url_for('auth.login'))

    user.confirm_email()
    db.session.commit()
    flash('E-Mail-Adresse erfolgreich bestätigt!', 'success')
    return redirect(url_for('nis2.dashboard'))


@auth_bp.route('/resend-confirmation')
@login_required
def resend_confirmation():
    if current_user.is_email_confirmed:
        flash('Ihre E-Mail ist bereits bestätigt.', 'info')
        return redirect(url_for('nis2.dashboard'))

    current_user.generate_confirmation_token()
    db.session.commit()
    try:
        _send_confirmation_email(current_user)
        flash('Bestätigungs-E-Mail wurde erneut gesendet.', 'success')
    except Exception as exc:
        logger.warning('Resend confirmation failed: %s', exc)
        flash('E-Mail konnte nicht gesendet werden. Bitte versuchen Sie es später.', 'danger')

    return redirect(url_for('nis2.dashboard'))


# ── Password reset ────────────────────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        # Always show same message (prevent enumeration)
        flash(
            'Falls diese E-Mail-Adresse registriert ist, erhalten Sie in Kürze eine E-Mail.',
            'info',
        )

        if user:
            token = user.generate_reset_token()
            db.session.commit()
            try:
                _send_reset_email(user, token)
            except Exception as exc:
                logger.warning('Could not send reset email: %s', exc)

        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(password_reset_token=token).first()
    if not user or not user.is_reset_token_valid(token):
        flash('Ungültiger oder abgelaufener Link. Bitte fordern Sie einen neuen an.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if len(password) < 8:
            flash('Passwort muss mindestens 8 Zeichen lang sein.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        if password != password2:
            flash('Passwörter stimmen nicht überein.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        user.set_password(password)
        user.password_reset_token = None
        user.password_reset_expires = None
        db.session.commit()

        flash('Passwort wurde erfolgreich geändert. Bitte melden Sie sich an.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


# ── Profile ───────────────────────────────────────────────────────────────────

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', '').strip()
        current_user.last_name = request.form.get('last_name', '').strip()
        current_user.company_name = request.form.get('company_name', '').strip()
        current_user.phone = request.form.get('phone', '').strip()

        new_password = request.form.get('new_password', '')
        if new_password:
            if len(new_password) < 8:
                flash('Neues Passwort muss mindestens 8 Zeichen lang sein.', 'danger')
                return render_template('auth/profile.html')
            current_user.set_password(new_password)

        db.session.commit()
        flash('Profil erfolgreich aktualisiert.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _send_confirmation_email(user: User):
    token = user.email_confirmation_token
    confirm_url = url_for('auth.confirm_email', token=token, _external=True)
    msg = Message(
        subject='NIS2 Compliance — E-Mail bestätigen',
        recipients=[user.email],
        html=render_template('auth/email_confirm.html',
                             user=user, confirm_url=confirm_url),
    )
    mail.send(msg)


def _send_reset_email(user: User, token: str):
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    msg = Message(
        subject='NIS2 Compliance — Passwort zurücksetzen',
        recipients=[user.email],
        html=render_template('auth/email_reset.html',
                             user=user, reset_url=reset_url),
    )
    mail.send(msg)
