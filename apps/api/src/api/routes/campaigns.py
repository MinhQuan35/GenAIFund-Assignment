from uuid import UUID

from fastapi import APIRouter, status

from src.schemas.campaigns import CampaignCreate, CampaignSummary
from src.schemas.candidates import CandidateCreate, CandidateWorkspaceItem, CampaignWorkspace
from src.services.campaigns import add_candidate, campaign_workspace, create_campaign, list_campaigns

router = APIRouter()


@router.get("", response_model=list[CampaignSummary])
def get_campaigns() -> list[dict]:
    return list_campaigns()


@router.post("", response_model=CampaignSummary, status_code=status.HTTP_201_CREATED)
def post_campaign(payload: CampaignCreate) -> dict:
    return create_campaign(payload)


@router.get("/{campaign_id}", response_model=CampaignWorkspace)
def get_campaign(campaign_id: UUID) -> dict:
    return campaign_workspace(campaign_id)


@router.post("/{campaign_id}/candidates", response_model=CandidateWorkspaceItem, status_code=status.HTTP_201_CREATED)
def post_candidate(campaign_id: UUID, payload: CandidateCreate) -> dict:
    return add_candidate(campaign_id, payload)
