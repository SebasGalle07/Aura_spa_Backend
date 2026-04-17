from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import get_optional_user
from app.crud.audit import (
    add_chatbot_message,
    create_audit_log,
    get_chatbot_messages,
    get_or_create_chatbot_conversation,
)
from app.db.deps import get_db
from app.schemas.audit import ChatbotMessageRequest, ChatbotMessageResponse
from app.services.chatbot_service import build_contextual_response

router = APIRouter()


@router.post("/message", response_model=ChatbotMessageResponse)
def send_chatbot_message(
    payload: ChatbotMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    message = payload.message.strip()
    if len(message) < 2:
        raise HTTPException(status_code=422, detail="Escribe una pregunta valida")
    if len(message) > 800:
        raise HTTPException(status_code=422, detail="La pregunta es demasiado extensa")

    conversation = get_or_create_chatbot_conversation(
        db,
        conversation_id=payload.conversation_id,
        user_id=current_user.id if current_user else None,
    )
    history = get_chatbot_messages(db, conversation.id)
    add_chatbot_message(db, conversation_id=conversation.id, sender="user", message=message)
    response = build_contextual_response(db, message, history=history, user=current_user)
    add_chatbot_message(db, conversation_id=conversation.id, sender="bot", message=response)
    create_audit_log(
        db,
        action="chatbot_message",
        entity_type="chatbot_conversation",
        entity_id=conversation.id,
        actor=current_user,
        new_value={"message": message[:120]},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"conversation_id": conversation.id, "response": response}
