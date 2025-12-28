"""
Webhooks Storage and Delivery
Handles webhook configuration and event delivery
"""
import json
import uuid
import hmac
import hashlib
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List

import httpx

from .sqlite_db import db


class WebhookEvent:
    """Webhook event types"""
    CALL_STARTED = "call.started"
    CALL_ENDED = "call.ended"
    CALL_FAILED = "call.failed"
    TRANSCRIPT_READY = "transcript.ready"
    ASSISTANT_CREATED = "assistant.created"
    ASSISTANT_UPDATED = "assistant.updated"
    ASSISTANT_DELETED = "assistant.deleted"

    ALL = [
        CALL_STARTED, CALL_ENDED, CALL_FAILED,
        TRANSCRIPT_READY,
        ASSISTANT_CREATED, ASSISTANT_UPDATED, ASSISTANT_DELETED
    ]


class WebhooksStore:
    """Webhook storage and delivery"""

    def create(self, url: str, events: List[str] = None, secret: str = None) -> Dict:
        """
        Create a new webhook

        Args:
            url: Webhook endpoint URL
            events: List of events to subscribe to (default: all)
            secret: Signing secret (auto-generated if not provided)

        Returns:
            Created webhook config
        """
        webhook_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        if not secret:
            import secrets as s
            secret = s.token_urlsafe(32)

        if not events:
            events = WebhookEvent.ALL

        db.execute("""
            INSERT INTO webhooks (id, url, events, secret, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
        """, (webhook_id, url, json.dumps(events), secret, now, now))

        return self.get(webhook_id)

    def get(self, webhook_id: str) -> Optional[Dict]:
        """Get webhook by ID"""
        row = db.fetch_one("SELECT * FROM webhooks WHERE id = ?", (webhook_id,))
        if not row:
            return None

        return {
            "id": row["id"],
            "url": row["url"],
            "events": json.loads(row["events"] or "[]"),
            "secret": row["secret"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list(self) -> List[Dict]:
        """List all webhooks"""
        rows = db.fetch_all("SELECT * FROM webhooks ORDER BY created_at DESC")
        return [
            {
                "id": row["id"],
                "url": row["url"],
                "events": json.loads(row["events"] or "[]"),
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def update(self, webhook_id: str, data: Dict) -> Optional[Dict]:
        """Update webhook configuration"""
        existing = self.get(webhook_id)
        if not existing:
            return None

        updates = []
        params = []

        if "url" in data:
            updates.append("url = ?")
            params.append(data["url"])

        if "events" in data:
            updates.append("events = ?")
            params.append(json.dumps(data["events"]))

        if "is_active" in data:
            updates.append("is_active = ?")
            params.append(1 if data["is_active"] else 0)

        if not updates:
            return existing

        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(webhook_id)

        query = f"UPDATE webhooks SET {', '.join(updates)} WHERE id = ?"
        db.execute(query, tuple(params))

        return self.get(webhook_id)

    def delete(self, webhook_id: str) -> bool:
        """Delete a webhook"""
        existing = self.get(webhook_id)
        if not existing:
            return False

        db.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
        return True

    def get_active_for_event(self, event: str) -> List[Dict]:
        """Get all active webhooks subscribed to an event"""
        webhooks = self.list()
        return [
            w for w in webhooks
            if w["is_active"] and event in w.get("events", [])
        ]

    def sign_payload(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for payload"""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()


class WebhookDelivery:
    """Handles webhook event delivery"""

    def __init__(self):
        self.store = WebhooksStore()
        self._client = None

    async def _get_client(self):
        """Get or create HTTP client"""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def send(
        self,
        event: str,
        data: Dict[str, Any],
        call_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Send webhook event to all subscribed endpoints

        Args:
            event: Event type (e.g., "call.ended")
            data: Event payload data
            call_id: Optional call ID for correlation

        Returns:
            List of delivery results
        """
        webhooks = self.store.get_active_for_event(event)

        if not webhooks:
            return []

        results = []
        client = await self._get_client()

        for webhook in webhooks:
            result = await self._deliver(client, webhook, event, data, call_id)
            results.append(result)

        return results

    async def _deliver(
        self,
        client: httpx.AsyncClient,
        webhook: Dict,
        event: str,
        data: Dict,
        call_id: Optional[str]
    ) -> Dict:
        """Deliver webhook to single endpoint"""
        # Build payload
        payload = {
            "id": str(uuid.uuid4()),
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }

        if call_id:
            payload["call_id"] = call_id

        payload_str = json.dumps(payload)

        # Get full webhook with secret
        full_webhook = self.store.get(webhook["id"])
        secret = full_webhook["secret"] if full_webhook else ""

        # Sign payload
        signature = self.store.sign_payload(payload_str, secret)

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Event": event,
            "X-Webhook-Id": payload["id"],
        }

        try:
            response = await client.post(
                webhook["url"],
                content=payload_str,
                headers=headers
            )

            return {
                "webhook_id": webhook["id"],
                "url": webhook["url"],
                "status": "success" if response.status_code < 400 else "failed",
                "status_code": response.status_code,
                "event": event,
            }

        except Exception as e:
            return {
                "webhook_id": webhook["id"],
                "url": webhook["url"],
                "status": "error",
                "error": str(e),
                "event": event,
            }

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None


# Global instances
webhooks_store = WebhooksStore()
webhook_delivery = WebhookDelivery()


# Convenience function for sending events
async def send_webhook_event(event: str, data: Dict, call_id: str = None):
    """Send webhook event (fire and forget)"""
    try:
        asyncio.create_task(webhook_delivery.send(event, data, call_id))
    except Exception:
        pass  # Webhooks should never block main flow
