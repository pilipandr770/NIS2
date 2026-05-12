"""
Payments blueprint — Pricing page + Stripe webhook (stub, extend as needed).
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user

from app.extensions import db

payments_bp = Blueprint('payments', __name__, template_folder='../templates/payments')


@payments_bp.route('/pricing')
def pricing():
    return render_template('payments/pricing.html')


@payments_bp.route('/upgrade')
@login_required
def upgrade():
    """Redirect to pricing if Stripe not configured, else start checkout."""
    if not current_app.config.get('STRIPE_SECRET_KEY'):
        flash('Online-Zahlung ist noch nicht konfiguriert. Bitte kontaktieren Sie uns.', 'info')
        return redirect(url_for('payments.pricing'))
    return redirect(url_for('payments.pricing'))


@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Stripe webhook — update subscription_plan on successful payment."""
    import stripe
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    if not secret:
        return 'Webhook not configured', 400

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception:
        return 'Invalid signature', 400

    if event['type'] == 'customer.subscription.updated':
        _handle_subscription_updated(event['data']['object'])
    elif event['type'] == 'customer.subscription.deleted':
        _handle_subscription_deleted(event['data']['object'])

    return 'OK', 200


def _handle_subscription_updated(subscription):
    from app.models import User
    customer_id = subscription.get('customer')
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return
    price_id = subscription['items']['data'][0]['price']['id']
    cfg = current_app.config
    if price_id == cfg.get('STRIPE_PRICE_PROFESSIONAL'):
        user.subscription_plan = 'professional'
    elif price_id == cfg.get('STRIPE_PRICE_BASIC'):
        user.subscription_plan = 'basic'
    user.stripe_subscription_id = subscription['id']
    db.session.commit()


def _handle_subscription_deleted(subscription):
    from app.models import User
    customer_id = subscription.get('customer')
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return
    user.subscription_plan = 'trial'
    db.session.commit()
