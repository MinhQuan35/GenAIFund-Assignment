from uuid import UUID

from fastapi import APIRouter, status

from src.schemas.campaigns import CampaignCreate, CampaignSummary
from src.schemas.candidates import CandidateCreate, CandidateWorkspaceItem, CampaignWorkspace
from src.schemas.x_integration import DiscoveryRequest, DiscoveryResponse
from src.services.campaigns import add_candidate, campaign_workspace, clear_campaign_candidates, create_campaign, list_campaigns, list_people, remove_candidate
from src.services.candidate_scoring import score_candidate
from src.services.x_discovery import discover_candidates

router = APIRouter()


@router.get("", response_model=list[CampaignSummary])
def get_campaigns() -> list[dict]:
    return list_campaigns()


@router.get("/people", tags=["people"])
def get_people() -> list[dict]:
    return list_people()


@router.post("", response_model=CampaignSummary, status_code=status.HTTP_201_CREATED)
def post_campaign(payload: CampaignCreate) -> dict:
    return create_campaign(payload)


@router.get("/{campaign_id}", response_model=CampaignWorkspace)
def get_campaign(campaign_id: UUID) -> dict:
    return campaign_workspace(campaign_id)


@router.post("/{campaign_id}/candidates", response_model=CandidateWorkspaceItem, status_code=status.HTTP_201_CREATED)
def post_candidate(campaign_id: UUID, payload: CandidateCreate) -> dict:
    return add_candidate(campaign_id, payload)


@router.post("/{campaign_id}/candidates/{candidate_id}/score", response_model=CandidateWorkspaceItem)
def post_candidate_score(campaign_id: UUID, candidate_id: UUID) -> dict:
    score_candidate(campaign_id, candidate_id)
    workspace = campaign_workspace(campaign_id)
    return next(candidate for candidate in workspace["candidates"] if candidate["id"] == str(candidate_id))


@router.delete("/{campaign_id}/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(campaign_id: UUID, candidate_id: UUID) -> None:
    remove_candidate(campaign_id, candidate_id)


@router.delete("/{campaign_id}/candidates")
def delete_unsent_candidates(campaign_id: UUID) -> dict:
    return clear_campaign_candidates(campaign_id)


@router.post("/{campaign_id}/discover", response_model=DiscoveryResponse)
def discover(campaign_id: UUID, payload: DiscoveryRequest) -> dict:
    return discover_candidates(campaign_id, payload)
