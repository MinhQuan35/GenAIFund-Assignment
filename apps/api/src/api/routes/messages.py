from uuid import UUID

from fastapi import APIRouter

from src.schemas.messages import MessageEdit, MessageReview, MessageDraftResponse
from src.schemas.x_integration import SendMessageRequest
from src.services.messages import draft_message, edit_message, list_conversations, review_message
from src.services.x_outreach import send_approved_message, sync_replies

router = APIRouter()


@router.get("/conversations")
def get_conversations() -> list[dict]:
    return list_conversations()


@router.post("/conversations/sync")
def post_sync_replies() -> dict:
    return sync_replies()


@router.post("/campaigns/{campaign_id}/candidates/{candidate_id}/draft", response_model=MessageDraftResponse)
def post_draft(campaign_id: UUID, candidate_id: UUID) -> dict:
    return draft_message(campaign_id, candidate_id)


@router.patch("/messages/{message_id}", response_model=MessageDraftResponse)
def patch_message(message_id: UUID, payload: MessageEdit) -> dict:
    return edit_message(message_id, payload)


@router.post("/messages/{message_id}/review", response_model=MessageDraftResponse)
def post_review(message_id: UUID, payload: MessageReview) -> dict:
    return review_message(message_id, payload)


@router.post("/messages/{message_id}/send", response_model=MessageDraftResponse)
def post_send(message_id: UUID, payload: SendMessageRequest) -> dict:
    return send_approved_message(message_id, payload.recipient_confirmed)
