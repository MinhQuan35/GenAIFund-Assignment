from uuid import UUID

from fastapi import HTTPException

from src.schemas.campaigns import CampaignCreate
from src.schemas.candidates import CandidateCreate
from src.services.candidate_quality import assess_candidate_quality, campaign_criteria
from src.services.storage import database_client, database_operation


def _campaign_or_404(client, campaign_id: UUID) -> dict:
    rows = database_operation(
        lambda: client.table("campaigns")
        .select("id,name,segment,status,created_at")
        .eq("id", str(campaign_id))
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return rows[0]


def list_campaigns() -> list[dict]:
    client = database_client()
    campaigns = database_operation(
        lambda: client.table("campaigns")
        .select("id,name,segment,status,created_at")
        .order("created_at", desc=True)
        .execute()
        .data
    )
    if not campaigns:
        return []

    ids = [campaign["id"] for campaign in campaigns]
    seeds = database_operation(
        lambda: client.table("campaign_seeds")
        .select("campaign_id,username")
        .in_("campaign_id", ids)
        .execute()
        .data
    )
    seeds_by_campaign: dict[str, list[str]] = {campaign_id: [] for campaign_id in ids}
    for seed in seeds:
        seeds_by_campaign[seed["campaign_id"]].append(seed["username"])
    return [{**campaign, "seed_accounts": seeds_by_campaign[campaign["id"]]} for campaign in campaigns]


def create_campaign(payload: CampaignCreate) -> dict:
    client = database_client()
    campaign_rows = database_operation(
        lambda: client.table("campaigns")
        .insert({"name": payload.name, "segment": payload.segment})
        .execute()
        .data
    )
    if not campaign_rows:
        raise HTTPException(status_code=502, detail="Campaign could not be created.")
    campaign = campaign_rows[0]

    try:
        if payload.seed_accounts:
            client.table("campaign_seeds").insert(
                [{"campaign_id": campaign["id"], "username": name} for name in payload.seed_accounts]
            ).execute()
    except Exception:
        try:
            client.table("campaigns").delete().eq("id", campaign["id"]).execute()
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Campaign seeds could not be saved.") from None

    return {**campaign, "seed_accounts": payload.seed_accounts}


def campaign_workspace(campaign_id: UUID) -> dict:
    client = database_client()
    campaign = _campaign_or_404(client, campaign_id)
    seeds = database_operation(
        lambda: client.table("campaign_seeds")
        .select("username")
        .eq("campaign_id", str(campaign_id))
        .order("username")
        .execute()
        .data
    )
    links = database_operation(
        lambda: client.table("campaign_candidates")
        .select("candidate_id,fit_score,fit_reason,fit_assessment,status")
        .eq("campaign_id", str(campaign_id))
        .order("created_at", desc=True)
        .execute()
        .data
    )
    if not links:
        return {**campaign, "seed_accounts": [seed["username"] for seed in seeds], "candidates": []}

    candidate_ids = [link["candidate_id"] for link in links]
    candidates = database_operation(
        lambda: client.table("candidates")
        .select("id,username,x_account_created_at,display_name,bio,location,profile_url")
        .in_("id", candidate_ids)
        .execute()
        .data
    )
    evidence = database_operation(
        lambda: client.table("candidate_evidence")
        .select("id,candidate_id,source_url,source_type,excerpt,captured_at")
        .eq("campaign_id", str(campaign_id))
        .in_("candidate_id", candidate_ids)
        .order("created_at")
        .execute()
        .data
    )
    drafts = database_operation(
        lambda: client.table("message_drafts")
        .select("id,campaign_id,candidate_id,content,status,created_at")
        .eq("campaign_id", str(campaign_id))
        .in_("candidate_id", candidate_ids)
        .order("created_at", desc=True)
        .execute()
        .data
    )

    link_by_id = {link["candidate_id"]: link for link in links}
    candidate_by_id = {candidate["id"]: candidate for candidate in candidates}
    evidence_by_candidate: dict[str, list[dict]] = {candidate_id: [] for candidate_id in candidate_ids}
    for item in evidence:
        evidence_by_candidate[item["candidate_id"]].append(item)
    draft_by_candidate = {}
    for draft in drafts:
        draft_by_candidate.setdefault(draft["candidate_id"], draft)

    workspace_candidates = []
    require_region = campaign_criteria(campaign["segment"])["requires_region"]
    for candidate_id in candidate_ids:
        profile = candidate_by_id.get(candidate_id)
        if profile is None:
            continue
        link = link_by_id[candidate_id]
        workspace_candidates.append(
            {
                **profile,
                **link,
                "evidence": evidence_by_candidate[candidate_id],
                "qualification": assess_candidate_quality(
                    profile,
                    evidence_by_candidate[candidate_id],
                    segment=campaign["segment"],
                    require_region=require_region,
                ),
                "message": draft_by_candidate.get(candidate_id),
            }
        )
    return {
        **campaign,
        "seed_accounts": [seed["username"] for seed in seeds],
        "candidates": workspace_candidates,
    }


def add_candidate(campaign_id: UUID, payload: CandidateCreate) -> dict:
    client = database_client()
    _campaign_or_404(client, campaign_id)
    username = payload.username
    profile_url = str(payload.profile_url) if payload.profile_url else f"https://x.com/{username}"
    profile_data = {
        "username": username,
        "x_user_id": payload.x_user_id,
        "x_account_created_at": payload.x_account_created_at.isoformat() if payload.x_account_created_at else None,
        "display_name": payload.display_name,
        "bio": payload.bio,
        "location": payload.location,
        "profile_url": profile_url,
    }

    existing = database_operation(
        lambda: client.table("candidates")
        .select("id")
        .eq("username_normalized", username)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        candidate_id = existing[0]["id"]
        database_operation(
            lambda: client.table("candidates").update(profile_data).eq("id", candidate_id).execute()
        )
    else:
        rows = database_operation(lambda: client.table("candidates").insert(profile_data).execute().data)
        if not rows:
            raise HTTPException(status_code=502, detail="Candidate could not be saved.")
        candidate_id = rows[0]["id"]

    association = database_operation(
        lambda: client.table("campaign_candidates")
        .select("candidate_id")
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", candidate_id)
        .limit(1)
        .execute()
        .data
    )
    association_data = {
        "campaign_id": str(campaign_id),
        "candidate_id": candidate_id,
        "fit_reason": payload.fit_reason,
        "fit_score": payload.fit_score,
    }
    if association:
        database_operation(
            lambda: client.table("campaign_candidates")
            .update({"fit_reason": payload.fit_reason, "fit_score": payload.fit_score})
            .eq("campaign_id", str(campaign_id))
            .eq("candidate_id", candidate_id)
            .execute()
        )
    else:
        database_operation(lambda: client.table("campaign_candidates").insert(association_data).execute())

    evidence_data = [
        {
            "campaign_id": str(campaign_id),
            "candidate_id": candidate_id,
            "source_url": str(item.source_url),
            "source_type": item.source_type,
            "excerpt": item.excerpt,
        }
        for item in payload.evidence
    ]
    database_operation(
        lambda: client.table("candidate_evidence")
        .upsert(
            evidence_data,
            on_conflict="campaign_id,candidate_id,source_url",
            ignore_duplicates=True,
        )
        .execute()
    )
    workspace = campaign_workspace(campaign_id)
    return next(candidate for candidate in workspace["candidates"] if candidate["id"] == candidate_id)


def remove_candidate(campaign_id: UUID, candidate_id: UUID) -> None:
    client = database_client()
    _campaign_or_404(client, campaign_id)
    association = database_operation(
        lambda: client.table("campaign_candidates")
        .select("candidate_id")
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", str(candidate_id))
        .limit(1)
        .execute()
        .data
    )
    if not association:
        raise HTTPException(status_code=404, detail="Candidate is not part of this campaign.")

    messages = database_operation(
        lambda: client.table("message_drafts")
        .select("id,status,external_message_id")
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", str(candidate_id))
        .in_("status", ["send_pending", "sent", "replied"])
        .limit(1)
        .execute()
        .data
    )
    if messages or any(message.get("external_message_id") for message in messages):
        raise HTTPException(status_code=409, detail="This candidate has a sent or pending DM and cannot be removed to preserve its outreach history.")

    database_operation(
        lambda: client.table("campaign_candidates")
        .delete()
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", str(candidate_id))
        .execute()
    )

    remaining_links = database_operation(
        lambda: client.table("campaign_candidates")
        .select("candidate_id")
        .eq("candidate_id", str(candidate_id))
        .limit(1)
        .execute()
        .data
    )
    if not remaining_links:
        database_operation(
            lambda: client.table("candidates")
            .delete()
            .eq("id", str(candidate_id))
            .execute()
        )


def clear_campaign_candidates(campaign_id: UUID) -> dict:
    client = database_client()
    _campaign_or_404(client, campaign_id)
    links = database_operation(
        lambda: client.table("campaign_candidates")
        .select("candidate_id")
        .eq("campaign_id", str(campaign_id))
        .execute()
        .data
    )
    removed = 0
    preserved = 0
    for link in links:
        candidate_id = link["candidate_id"]
        sent_messages = database_operation(
            lambda candidate_id=candidate_id: client.table("message_drafts")
            .select("id")
            .eq("campaign_id", str(campaign_id))
            .eq("candidate_id", candidate_id)
            .in_("status", ["send_pending", "sent", "replied"])
            .limit(1)
            .execute()
            .data
        )
        if sent_messages:
            preserved += 1
            continue
        database_operation(
            lambda candidate_id=candidate_id: client.table("campaign_candidates")
            .delete()
            .eq("campaign_id", str(campaign_id))
            .eq("candidate_id", candidate_id)
            .execute()
        )
        remaining_links = database_operation(
            lambda candidate_id=candidate_id: client.table("campaign_candidates")
            .select("candidate_id")
            .eq("candidate_id", candidate_id)
            .limit(1)
            .execute()
            .data
        )
        if not remaining_links:
            database_operation(
                lambda candidate_id=candidate_id: client.table("candidates")
                .delete()
                .eq("id", candidate_id)
                .execute()
            )
        removed += 1
    return {"removed": removed, "preserved": preserved}


def list_people() -> list[dict]:
    client = database_client()
    candidates = database_operation(
        lambda: client.table("candidates")
        .select("id,username,x_account_created_at,display_name,bio,location,profile_url")
        .order("username")
        .execute()
        .data
    )
    if not candidates:
        return []
    candidate_ids = [candidate["id"] for candidate in candidates]
    links = database_operation(
        lambda: client.table("campaign_candidates")
        .select("campaign_id,candidate_id,fit_score,fit_reason,fit_assessment,status")
        .in_("candidate_id", candidate_ids)
        .execute()
        .data
    )
    evidence = database_operation(
        lambda: client.table("candidate_evidence")
        .select("id,campaign_id,candidate_id,source_url,source_type,excerpt,captured_at")
        .in_("candidate_id", candidate_ids)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    campaigns = database_operation(
        lambda: client.table("campaigns")
        .select("id,name")
        .in_("id", list({link["campaign_id"] for link in links}))
        .execute()
        .data
    ) if links else []
    campaign_names = {campaign["id"]: campaign["name"] for campaign in campaigns}
    links_by_candidate: dict[str, list[dict]] = {candidate_id: [] for candidate_id in candidate_ids}
    evidence_by_candidate: dict[str, list[dict]] = {candidate_id: [] for candidate_id in candidate_ids}
    for link in links:
        links_by_candidate[link["candidate_id"]].append(
            {**link, "campaign_name": campaign_names.get(link["campaign_id"], "Campaign")}
        )
    for item in evidence:
        evidence_by_candidate[item["candidate_id"]].append(item)
    return [
        {
            **candidate,
            "campaigns": links_by_candidate[candidate["id"]],
            "evidence": evidence_by_candidate[candidate["id"]],
        }
        for candidate in candidates
    ]
