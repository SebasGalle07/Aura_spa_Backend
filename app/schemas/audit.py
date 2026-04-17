from datetime import datetime
from typing import Literal

from app.schemas.common import BaseSchema


CancellationStatus = Literal["pending", "reviewed", "approved", "rejected"]


class AuditLogOut(BaseSchema):
    id: int
    actor_user_id: int | None = None
    actor_role: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    old_value: dict | None = None
    new_value: dict | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


class AccountCancellationRequestCreate(BaseSchema):
    reason: str


class AccountCancellationRequestUpdate(BaseSchema):
    status: CancellationStatus
    admin_response: str | None = None


class AccountCancellationRequestOut(BaseSchema):
    id: int
    user_id: int
    status: CancellationStatus
    reason: str
    admin_response: str | None = None
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChatbotMessageRequest(BaseSchema):
    message: str
    conversation_id: int | None = None


class ChatbotMessageResponse(BaseSchema):
    conversation_id: int
    response: str
