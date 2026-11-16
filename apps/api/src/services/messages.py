from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException

from src.integrations.foundry import FoundryIntegrationError, generate_text
from src.schemas.messages import MessageEdit, MessageReview
from src.services.campaigns import _campaign_or_404
from src.services.storage import database_client, database_operation


def _candidate_context(client, campaign_id: UUID, candidate_id: UUID) -> dict:
    link_rows = database_operation(
        lambda: client.table("campaign_candidates")
        .select("candidate_id,fit_score,fit_reason")
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", str(candidate_id))
        .limit(1)
        .execute()
        .data
    )
    if not link_rows:
        raise HTTPException(status_code=404, detail="Candidate is not part of this campaign.")
    candidate_rows = database_operation(
        lambda: client.table("candidates")
        .select("username,display_name,bio,location,profile_url")
        .eq("id", str(candidate_id))
        .limit(1)
        .execute()
        .data
    )
    evidence = database_operation(
        lambda: client.table("candidate_evidence")
        .select("source_url,source_type,excerpt")
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", str(candidate_id))
        .order("created_at")
        .execute()
        .data
    )
    if not candidate_rows or not evidence:
        raise HTTPException(status_code=422, detail="Add at least one evidence item before drafting a message.")
    return {"candidate": candidate_rows[0], "fit": link_rows[0], "evidence": evidence}


def draft_message(campaign_id: UUID, candidate_id: UUID) -> dict:
    client = database_client()
    _campaign_or_404(client, campaign_id)
    context = _candidate_context(client, campaign_id, candidate_id)
    candidate = context["candidate"]
    fit = context["fit"]
    evidence = context["evidence"]
    post_evidence = [item for item in evidence if item["source_type"] == "post"]
    if not post_evidence:
        raise HTTPException(status_code=422, detail="Add a public post as evidence before generating a personalized DM.")
    post_to_reference = post_evidence[-1]
    existing = database_operation(
        lambda: client.table("message_drafts")
        .select("id,content")
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", str(candidate_id))
        .in_("status", ["draft", "rejected"])
        .limit(1)
        .execute()
        .data
    )
    previous_draft = existing[0] if existing else None
    evidence_text = "\n".join(
        f"- {item['source_type']}: {item['excerpt']} ({item['source_url']})" for item in evidence
    )
    prompt = f"""Write one concise, warm first-contact X DM for GenAI Fund.
Use only the evidence below. Do not claim familiarity, mutual connections, or facts not provided.
Do not mention scores or that this was generated. Keep it under 500 characters.
The message must specifically refer to one concrete idea or detail from the selected recent post below.
Do not write a generic profile-based opener without referencing that post. Paraphrase faithfully; do not invent reactions or details.
Include one light invitation to a conversation. Return only the message text.
If a previous unsent draft is supplied, write a meaningfully different version: choose a different evidence point or conversational angle and avoid reusing its distinctive wording.

Candidate: @{candidate['username']} ({candidate.get('display_name') or 'unknown name'})
Bio: {candidate.get('bio') or 'not provided'}
Location: {candidate.get('location') or 'not provided'}
Fit reason: {fit['fit_reason']}
Selected recent post to reference: {post_to_reference['excerpt']} ({post_to_reference['source_url']})
Previous unsent draft: {previous_draft['content'] if previous_draft else 'none'}
Evidence:
{evidence_text}
"""
    try:
        content = generate_text(prompt, max_output_tokens=180)
    except FoundryIntegrationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None
    if existing:
        rows = database_operation(
            lambda: client.table("message_drafts")
            .update({"content": content, "status": "draft", "approved_at": None})
            .eq("id", previous_draft["id"])
            .execute()
            .data
        )
    else:
        rows = database_operation(
            lambda: client.table("message_drafts")
            .insert({
                "campaign_id": str(campaign_id),
                "candidate_id": str(candidate_id),
                "content": content,
                "status": "draft",
            })
            .execute()
            .data
        )
    if not rows:
        raise HTTPException(status_code=502, detail="Message draft could not be saved.")
    database_operation(
        lambda: client.table("campaign_candidates")
        .update({"status": "drafted"})
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", str(candidate_id))
        .execute()
    )
    return rows[0]


def edit_message(message_id: UUID, payload: MessageEdit) -> dict:
    client = database_client()
    rows = database_operation(
        lambda: client.table("message_drafts")
        .update({"content": payload.content, "status": "draft", "approved_at": None})
        .eq("id", str(message_id))
        .in_("status", ["draft", "rejected"])
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Editable message draft not found.")
    return rows[0]


def review_message(message_id: UUID, payload: MessageReview) -> dict:
    client = database_client()
    if payload.action == "approve":
        update = {"status": "approved", "approved_at": datetime.now(timezone.utc).isoformat()}
    else:
        update = {"status": "rejected", "approved_at": None}
    rows = database_operation(
        lambda: client.table("message_drafts")
        .update(update)
        .eq("id", str(message_id))
        .eq("status", "draft")
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Only draft messages can be reviewed.")
    message = rows[0]
    if payload.action == "approve":
        database_operation(
            lambda: client.table("campaign_candidates")
            .update({"status": "approved"})
            .eq("campaign_id", message["campaign_id"])
            .eq("candidate_id", message["candidate_id"])
            .execute()
        )
    return message


def list_conversations() -> list[dict]:
    client = database_client()
    messages = database_operation(
        lambda: client.table("message_drafts")
        .select("id,campaign_id,candidate_id,content,status,approved_at,sent_at,created_at")
        .order("created_at", desc=True)
        .execute()
        .data
    )
    if not messages:
        return []
    message_ids = [message["id"] for message in messages]
    interactions = database_operation(
        lambda: client.table("message_interactions")
        .select("id,message_id,event_type,sender_x_user_id,text,occurred_at")
        .in_("message_id", message_ids)
        .order("occurred_at")
        .execute()
        .data
    )
    candidate_ids = list({message["candidate_id"] for message in messages})
    campaign_ids = list({message["campaign_id"] for message in messages})
    candidates = database_operation(
        lambda: client.table("candidates")
        .select("id,username,display_name,profile_url")
        .in_("id", candidate_ids)
        .execute()
        .data
    )
    campaigns = database_operation(
        lambda: client.table("campaigns")
        .select("id,name")
        .in_("id", campaign_ids)
        .execute()
        .data
    )
    candidate_by_id = {candidate["id"]: candidate for candidate in candidates}
    campaign_by_id = {campaign["id"]: campaign["name"] for campaign in campaigns}
    interactions_by_message: dict[str, list[dict]] = {message_id: [] for message_id in message_ids}
    for interaction in interactions:
        interactions_by_message[interaction["message_id"]].append(interaction)
    return [
        {
            **message,
            "candidate": candidate_by_id.get(message["candidate_id"]),
            "campaign_name": campaign_by_id.get(message["campaign_id"], "Campaign"),
            "interactions": interactions_by_message[message["id"]],
        }
        for message in messages
    ]
