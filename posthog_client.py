"""
posthog_client.py
Centralized PostHog analytics client for the Bank Management System.
Tracks user events like login, logout, and banking operations.
"""

from posthog import Client
from datetime import datetime

# ── PostHog Configuration ──────────────────────────────────────────────────
_client = Client(
    project_api_key="phc_BTSPAt8jobzbdPRsWuf7TfACiDT55PuM5wZxndNKpCW4",
    host="https://eu.i.posthog.com",   # EU Cloud region
    sync_mode=True,                     # Send events immediately (not batched)
)


def track(event: str, distinct_id: str, properties: dict = None):
    """
    Capture a named event for a user.

    Args:
        event       : Event name, e.g. 'user_logged_in'
        distinct_id : Unique identifier for the user (username)
        properties  : Optional dict of extra metadata to attach
    """
    try:
        props = properties or {}
        props.setdefault("app", "bank_management_system")
        props.setdefault("timestamp_ist", datetime.now().isoformat())
        _client.capture(distinct_id=distinct_id, event=event, properties=props)
        print("[PostHog OK] event='{}' user='{}'".format(event, distinct_id))
    except Exception as e:
        print("[PostHog ERR] Failed to send event '{}' for user '{}': {}".format(event, distinct_id, e))


def identify(distinct_id: str, user_properties: dict = None):
    """
    Associate a user with their properties in PostHog.
    Uses 'set' to attach person properties to the distinct_id.
    """
    try:
        _client.set(distinct_id=distinct_id, properties=user_properties or {})
        print("[PostHog OK] identified user='{}'".format(distinct_id))
    except Exception as e:
        print("[PostHog ERR] Failed to identify user '{}': {}".format(distinct_id, e))
