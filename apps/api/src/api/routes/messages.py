from uuid import UUID

from fastapi import APIRouter

from src.schemas.candidates import CandidateWorkspaceItem
from src.schemas.messages import MessageEdit, MessageReview, MessageDraftResponse
from src.services.messages import draft_message, edit_message, review_message

router = APIRouter()


@router.post("/campaigns/{campaign_id}/candidates/{candidate_id}/draft", response_model=MessageDraftResponse)
def post_draft(campaign_id: UUID, candidate_id: UUID) -> dict:
    return draft_message(campaign_id, candidate_id)


@router.patch("/messages/{message_id}", response_model=MessageDraftResponse)
def patch_message(message_id: UUID, payload: MessageEdit) -> dict:
    return edit_message(message_id, payload)


@router.post("/messages/{message_id}/review", response_model=MessageDraftResponse)
def post_review(message_id: UUID, payload: MessageReview) -> dict:
    return review_message(message_id, payload)
