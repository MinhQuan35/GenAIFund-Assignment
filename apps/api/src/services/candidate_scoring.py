import json
from uuid import UUID

from fastapi import HTTPException

from src.integrations.foundry import FoundryIntegrationError, generate_text
from src.services.campaigns import _campaign_or_404
from src.services.storage import database_client, database_operation

DIMENSIONS = {
    "role_relevance": 0.30,
    "domain_relevance": 0.35,
    "region_relevance": 0.15,
    "evidence_quality": 0.20,
}


def _parse_assessment(raw: str) -> dict:
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        result = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="Foundry returned an invalid candidate assessment.") from None

    dimensions = result.get("dimensions")
    if not isinstance(dimensions, dict):
        raise HTTPException(status_code=502, detail="Foundry assessment is missing score dimensions.")
    normalized = {}
    for name in DIMENSIONS:
        value = dimensions.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
            raise HTTPException(status_code=502, detail=f"Foundry returned an invalid {name} score.")
        normalized[name] = value
    reason = result.get("fit_reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise HTTPException(status_code=502, detail="Foundry returned an invalid fit explanation.")
    score = round(sum(normalized[name] * weight for name, weight in DIMENSIONS.items()))
    return {"fit_score": score, "fit_reason": reason.strip(), "dimensions": normalized}


def score_candidate(campaign_id: UUID, candidate_id: UUID) -> dict:
    client = database_client()
    campaign = _campaign_or_404(client, campaign_id)
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

    profiles = database_operation(
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
    if not profiles or not evidence:
        raise HTTPException(status_code=422, detail="Add source evidence before requesting an AI score.")

    profile = profiles[0]
    evidence_for_prompt = [
        {"type": item["source_type"], "url": item["source_url"], "excerpt": item["excerpt"]}
        for item in evidence[:10]
    ]
    prompt = f"""Assess this X prospect for the campaign using only the supplied profile and evidence.
Do not infer facts that are not supported. If a dimension is unknown, score it low rather than guessing.
Return only valid JSON with this shape:
{{"dimensions":{{"role_relevance":0,"domain_relevance":0,"region_relevance":0,"evidence_quality":0}},"fit_reason":"one concise evidence-grounded explanation"}}

Use integer scores from 0 to 100. Score role relevance (builder, founder, researcher, or relevant operator),
AI/robotics domain relevance, Southeast Asia relevance, and how specific/reliable the supplied evidence is.
The application calculates the weighted total: role 30%, domain 35%, region 15%, evidence 20%.

Campaign segment: {campaign['segment']}
Candidate: @{profile['username']}
Display name: {profile.get('display_name') or 'unknown'}
Bio: {profile.get('bio') or 'not provided'}
Location: {profile.get('location') or 'not provided'}
Evidence: {json.dumps(evidence_for_prompt, ensure_ascii=True)}
"""
    try:
        assessment = _parse_assessment(generate_text(prompt, max_output_tokens=220))
    except FoundryIntegrationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None

    database_operation(
        lambda: client.table("campaign_candidates")
        .update({
            "fit_score": assessment["fit_score"],
            "fit_reason": assessment["fit_reason"],
            "fit_assessment": {"method": "foundry_gpt4o", **assessment["dimensions"]},
        })
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", str(candidate_id))
        .execute()
    )
    workspace = database_operation(
        lambda: client.table("campaign_candidates")
        .select("fit_score,fit_reason,fit_assessment")
        .eq("campaign_id", str(campaign_id))
        .eq("candidate_id", str(candidate_id))
        .limit(1)
        .execute()
        .data
    )
    return workspace[0]
