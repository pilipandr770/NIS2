"""
Security helpers — compatibility stub for NIS2 standalone app.

In the standalone NIS2 project, access control is handled globally
by the nis2_bp.before_request hook (requires active trial or paid plan).
The require_plan decorator here is a no-op pass-through.
"""

import functools
from flask import redirect, url_for, flash
from flask_login import current_user


def require_plan(*plans):
    """
    Decorator stub — access is already enforced by the NIS2 blueprint's
    before_request hook. Kept for drop-in compatibility with copied routes.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        return wrapper
    return decorator
