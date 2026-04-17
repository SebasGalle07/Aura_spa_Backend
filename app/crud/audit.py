from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.audit import (
    AccountCancellationRequest,
    AuditLog,
    ChatbotConversation,
    ChatbotMessage,
)
from app.models.user import User


def create_audit_log(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    actor: User | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    commit: bool = True,
) -> AuditLog:
    log = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
    return log


def list_audit_logs(db: Session, limit: int = 100, offset: int = 0) -> list[AuditLog]:
    safe_limit = min(max(limit, 1), 500)
    safe_offset = max(offset, 0)
    return list(
        db.scalars(
            select(AuditLog)
            .order_by(desc(AuditLog.created_at))
            .offset(safe_offset)
            .limit(safe_limit)
        ).all()
    )


def create_account_cancellation_request(
    db: Session,
    *,
    user_id: int,
    reason: str,
    status: str = "pending",
    reviewed_at=None,
) -> AccountCancellationRequest:
    request = AccountCancellationRequest(
        user_id=user_id,
        reason=reason.strip(),
        status=status,
        reviewed_at=reviewed_at,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def get_open_account_cancellation_request(db: Session, user_id: int) -> AccountCancellationRequest | None:
    return db.scalar(
        select(AccountCancellationRequest)
        .where(
            AccountCancellationRequest.user_id == user_id,
            AccountCancellationRequest.status.in_(["pending", "reviewed", "approved"]),
        )
        .order_by(desc(AccountCancellationRequest.created_at))
        .limit(1)
    )


def list_account_cancellation_requests(db: Session) -> list[AccountCancellationRequest]:
    return list(
        db.scalars(
            select(AccountCancellationRequest).order_by(desc(AccountCancellationRequest.created_at))
        ).all()
    )


def get_account_cancellation_request(db: Session, request_id: int) -> AccountCancellationRequest | None:
    return db.get(AccountCancellationRequest, request_id)


def update_account_cancellation_request(
    db: Session,
    request: AccountCancellationRequest,
    *,
    status: str,
    admin_response: str | None,
    reviewed_by_user_id: int,
) -> AccountCancellationRequest:
    request.status = status
    request.admin_response = admin_response
    request.reviewed_by_user_id = reviewed_by_user_id
    request.reviewed_at = utc_now()
    request.updated_at = utc_now()
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def get_or_create_chatbot_conversation(
    db: Session,
    *,
    conversation_id: int | None,
    user_id: int | None,
) -> ChatbotConversation:
    if conversation_id:
        existing = db.get(ChatbotConversation, conversation_id)
        if existing:
            if existing.user_id and existing.user_id != user_id:
                existing = None
            elif user_id and existing.user_id is None:
                existing.user_id = user_id
                existing.updated_at = utc_now()
                db.add(existing)
                db.commit()
                db.refresh(existing)
        if existing:
            return existing
    conversation = ChatbotConversation(user_id=user_id, status="open")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_chatbot_messages(db: Session, conversation_id: int, limit: int = 12) -> list[ChatbotMessage]:
    safe_limit = min(max(limit, 1), 50)
    rows = list(
        db.scalars(
            select(ChatbotMessage)
            .where(ChatbotMessage.conversation_id == conversation_id)
            .order_by(desc(ChatbotMessage.created_at))
            .limit(safe_limit)
        ).all()
    )
    return list(reversed(rows))


def add_chatbot_message(
    db: Session,
    *,
    conversation_id: int,
    sender: str,
    message: str,
    commit: bool = True,
) -> ChatbotMessage:
    row = ChatbotMessage(conversation_id=conversation_id, sender=sender, message=message)
    db.add(row)
    conversation = db.get(ChatbotConversation, conversation_id)
    if conversation:
        conversation.updated_at = utc_now()
        db.add(conversation)
    if commit:
        db.commit()
        db.refresh(row)
    return row
