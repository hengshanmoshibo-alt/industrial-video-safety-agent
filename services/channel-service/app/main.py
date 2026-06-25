import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from aicoding_shared.config import get_settings
from aicoding_shared.db import get_session
from aicoding_shared.models import Channel, ChannelType, User, UserRole
from aicoding_shared.security import require_roles
from aicoding_shared.service import create_service_app


class ChannelCreate(BaseModel):
    name: str
    type: ChannelType = ChannelType.web
    config: dict = {}
    enabled: bool = True


class WebhookPayload(BaseModel):
    visitor_name: str = "模拟访客"
    content: str
    external_id: str = ""


app = create_service_app("channel-service")


@app.get("/channels")
def list_channels(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor])), session: Session = Depends(get_session)):
    return session.exec(select(Channel).where(Channel.tenant_id == user.tenant_id).order_by(Channel.id)).all()


@app.post("/channels")
def create_channel(payload: ChannelCreate, user: User = Depends(require_roles([UserRole.admin])), session: Session = Depends(get_session)):
    channel = Channel(tenant_id=user.tenant_id, **payload.model_dump())
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


@app.post("/channels/{channel_id}/simulate-webhook")
async def simulate_webhook(channel_id: int, payload: WebhookPayload, user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor])), session: Session = Depends(get_session)):
    channel = session.get(Channel, channel_id)
    if channel is None or channel.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Channel not found")
    headers = {"X-Tenant-Id": str(user.tenant_id)}
    async with httpx.AsyncClient(timeout=30) as client:
        created = await client.post(
            f"{get_settings().conversation_service_url}/chat/sessions",
            headers=headers,
            json={
                "visitor_name": payload.visitor_name,
                "channel_id": channel.id,
                "external_id": payload.external_id or f"sim-{channel.type}-{channel.id}",
            },
        )
        created.raise_for_status()
        conversation = created.json()
        messages = await client.post(
            f"{get_settings().conversation_service_url}/chat/sessions/{conversation['id']}/messages",
            headers=headers,
            json={"content": payload.content},
        )
        messages.raise_for_status()
    return {
        "channel": channel.type,
        "external_id": payload.external_id or f"sim-{channel.type}-{channel.id}",
        "conversation": conversation,
        "messages": messages.json(),
        "adapter": "webhook-simulation",
    }
