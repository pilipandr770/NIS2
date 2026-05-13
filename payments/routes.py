"""
Payments blueprint — Pricing page + Stripe Checkout + Webhook.
"""

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, jsonify)
from flask_login import login_required, current_user

from app.extensions import db

payments_bp = Blueprint('payments', __name__, template_folder='../templates/payments')


@payments_bp.route('/pricing')
def pricing():
    return render_template('payments/pricing.html')


@payments_bp.route('/checkout/<plan>', methods=['POST'])
@login_required
def create_checkout(plan):
    """Create Stripe Checkout Session and redirect to hosted payment page."""
    import stripe
    cfg = current_app.config
    stripe.api_key = cfg.get('STRIPE_SECRET_KEY')

    price_map = {
        'basic': cfg.get('STRIPE_PRICE_BASIC'),
        'professional': cfg.get('STRIPE_PRICE_PROFESSIONAL'),
    }
    price_id = price_map.get(plan)
    if not price_id:
        flash('Ungültiger Plan.', 'danger')
        return redirect(url_for('payments.pricing'))

    # Create Stripe customer once and persist it
    if not current_user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            metadata={'user_id': str(current_user.id)},
        )
        current_user.stripe_customer_id = customer['id']
        db.session.commit()

    session = stripe.checkout.Session.create(
        customer=current_user.stripe_customer_id,
        payment_method_types=['card'],
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='subscription',
        success_url=url_for('payments.checkout_success', _external=True,
                            session_id='{CHECKOUT_SESSION_ID}'),
        cancel_url=url_for('payments.pricing', _external=True),
    )
    return redirect(session.url, code=303)


@payments_bp.route('/success')
@login_required
def checkout_success():
    flash('Zahlung erfolgreich! Ihr Plan wurde aktiviert.', 'success')
    return redirect(url_for('nis2.dashboard'))


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

    etype = event['type']
    obj = event['data']['object']

    if etype == 'checkout.session.completed':
        _handle_checkout_completed(obj)
    elif etype == 'customer.subscription.updated':
        _handle_subscription_updated(obj)
    elif etype == 'customer.subscription.deleted':
        _handle_subscription_deleted(obj)

    return 'OK', 200


# ── Webhook helpers ───────────────────────────────────────────────

def _handle_checkout_completed(session):
    """Fired immediately after successful payment — ensures customer link exists."""
    from app.models import User
    customer_id = session.get('customer')
    user_id = (session.get('metadata') or {}).get('user_id')

    user = None
    if customer_id:
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user and user_id:
        user = User.query.get(int(user_id))
    if not user:
        return

    if customer_id and not user.stripe_customer_id:
        user.stripe_customer_id = customer_id

    # Map price to plan from line items if available
    cfg = current_app.config
    price_id = None
    line_items = session.get('line_items', {}).get('data', [])
    if line_items:
        price_id = line_items[0].get('price', {}).get('id')

    if price_id == cfg.get('STRIPE_PRICE_PROFESSIONAL'):
        user.subscription_plan = 'professional'
    elif price_id == cfg.get('STRIPE_PRICE_BASIC'):
        user.subscription_plan = 'basic'

    db.session.commit()


def _handle_subscription_updated(subscription):
    from app.models import User
    status = subscription.get('status', '')
    if status not in ('active', 'trialing'):
        return

    customer_id = subscription.get('customer')
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    cfg = current_app.config
    price_id = subscription['items']['data'][0]['price']['id']
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
