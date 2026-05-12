"""
Security helpers — plan-based feature gating for NIS2 platform.

Plan hierarchy (ascending access level):
  trial < basic < professional < enterprise

@require_plan("professional") blocks users on trial/basic plans and
redirects them to the pricing page with an explanatory message.

Admin users always bypass plan checks.
"""

import functools
from flask import redirect, url_for, flash
from flask_login import current_user

# Plan hierarchy — higher index = more access
_PLAN_ORDER = ['trial', 'basic', 'professional', 'enterprise']


def _plan_rank(plan: str) -> int:
    try:
        return _PLAN_ORDER.index(plan)
    except ValueError:
        return 0


def require_plan(*required_plans: str):
    """
    Decorator that enforces a minimum subscription plan.

    Usage:
        @require_plan("professional")   # requires professional or enterprise
        @require_plan("basic")          # requires basic, professional, or enterprise

    Admin users always pass. Users without sufficient plan are redirected
    to the pricing page.
    """
    min_rank = min(_plan_rank(p) for p in required_plans) if required_plans else 0

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))

            if current_user.is_admin:
                return f(*args, **kwargs)

            user_rank = _plan_rank(current_user.subscription_plan)

            # Trial users are allowed only if the feature doesn't require a paid plan
            if current_user.subscription_plan == 'trial' and current_user.is_trial_active:
                # Trial gets access to all features during the trial period
                return f(*args, **kwargs)

            if user_rank >= min_rank:
                return f(*args, **kwargs)

            # Determine which plan is needed for the message
            needed_plan = required_plans[0] if required_plans else 'professional'
            plan_labels = {
                'basic': 'Basic',
                'professional': 'Professional',
                'enterprise': 'Enterprise',
            }
            plan_label = plan_labels.get(needed_plan, needed_plan.capitalize())
            flash(
                f'Diese Funktion erfordert den {plan_label}-Tarif. '
                f'Bitte upgraden Sie Ihren Account.',
                'warning',
            )
            return redirect(url_for('payments.pricing'))

        return wrapper
    return decorator
