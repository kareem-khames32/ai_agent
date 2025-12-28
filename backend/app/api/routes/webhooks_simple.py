"""
Webhooks API Routes
Configure webhook endpoints for event notifications
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, HttpUrl

from app.storage.webhooks_store import webhooks_store, WebhookEvent

router = APIRouter()


# === Request/Response Models ===

class WebhookCreate(BaseModel):
    """Create webhook request"""
    url: str
    events: Optional[List[str]] = None  # Default: all events
    secret: Optional[str] = None  # Auto-generated if not provided


class WebhookUpdate(BaseModel):
    """Update webhook request"""
    url: Optional[str] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    """Webhook response"""
    id: str
    url: str
    events: List[str]
    secret: Optional[str] = None  # Only returned on creation
    is_active: bool
    created_at: str


class WebhookTestRequest(BaseModel):
    """Test webhook request"""
    event: Optional[str] = "test.ping"


# === API Endpoints ===

@router.get("")
async def list_webhooks():
    """
    List all configured webhooks

    Returns webhooks without secrets.
    """
    return webhooks_store.list()


@router.post("", status_code=201)
async def create_webhook(data: WebhookCreate):
    """
    Create a new webhook endpoint

    Configure a URL to receive event notifications.
    The signing secret is only returned once during creation.

    Available events:
    - call.started: When a call begins
    - call.ended: When a call completes
    - call.failed: When a call fails
    - transcript.ready: When transcript is available
    - assistant.created: When an assistant is created
    - assistant.updated: When an assistant is updated
    - assistant.deleted: When an assistant is deleted
    """
    # Validate events if provided
    if data.events:
        invalid = [e for e in data.events if e not in WebhookEvent.ALL]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid events: {invalid}. Valid events: {WebhookEvent.ALL}"
            )

    webhook = webhooks_store.create(
        url=data.url,
        events=data.events,
        secret=data.secret
    )

    return webhook


@router.get("/events")
async def list_webhook_events():
    """
    List all available webhook events

    Returns all event types that can be subscribed to.
    """
    return {
        "events": WebhookEvent.ALL,
        "descriptions": {
            "call.started": "Fired when a call begins",
            "call.ended": "Fired when a call completes successfully",
            "call.failed": "Fired when a call fails or errors",
            "transcript.ready": "Fired when call transcript is available",
            "assistant.created": "Fired when a new assistant is created",
            "assistant.updated": "Fired when an assistant is modified",
            "assistant.deleted": "Fired when an assistant is deleted",
        }
    }


@router.get("/{webhook_id}")
async def get_webhook(webhook_id: str):
    """
    Get webhook details

    Returns webhook configuration including the signing secret.
    """
    webhook = webhooks_store.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return webhook


@router.patch("/{webhook_id}")
async def update_webhook(webhook_id: str, data: WebhookUpdate):
    """
    Update webhook configuration

    Modify URL, events, or active status.
    """
    update_data = data.model_dump(exclude_none=True)

    # Validate events if provided
    if "events" in update_data and update_data["events"]:
        invalid = [e for e in update_data["events"] if e not in WebhookEvent.ALL]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid events: {invalid}"
            )

    webhook = webhooks_store.update(webhook_id, update_data)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return webhook


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: str):
    """
    Delete a webhook

    This action cannot be undone.
    """
    if not webhooks_store.delete(webhook_id):
        raise HTTPException(status_code=404, detail="Webhook not found")


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: str, data: WebhookTestRequest = None):
    """
    Send a test event to the webhook

    Sends a test payload to verify the webhook is working.
    """
    from app.storage.webhooks_store import webhook_delivery

    webhook = webhooks_store.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Send test event
    event = data.event if data else "test.ping"
    test_data = {
        "message": "This is a test webhook delivery",
        "webhook_id": webhook_id,
    }

    results = await webhook_delivery.send(event, test_data)

    # If no results, webhook might not be subscribed to this event
    if not results:
        # Force delivery for test
        result = await webhook_delivery._deliver(
            await webhook_delivery._get_client(),
            webhook,
            event,
            test_data,
            None
        )
        return result

    return results[0] if results else {"status": "no_delivery"}
