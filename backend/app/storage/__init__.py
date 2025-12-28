"""
Simple Local Storage Module
Works with SQLite and JSON files - no PostgreSQL needed
"""
from .sqlite_db import db
from .assistants_store import assistants_store
from .auth_store import auth_store
from .webhooks_store import webhooks_store, webhook_delivery, send_webhook_event, WebhookEvent

__all__ = [
    "db",
    "assistants_store",
    "auth_store",
    "webhooks_store",
    "webhook_delivery",
    "send_webhook_event",
    "WebhookEvent",
]
