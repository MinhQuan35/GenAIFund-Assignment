import re
from datetime import datetime, timezone

DOMAIN_TERMS = (
    "artificial intelligence", "machine learning", "computer vision", "large language model",
    "embodied ai", "deep learning", "robotics", "robot", "llm", "inference", "ai",
)
ROLE_TERMS = (
    "co-founder", "cofounder", "founder", "founders", "researcher", "researchers", "research scientist",
    "research", "engineer", "engineers", "engineering", "developer", "developers", "builder", "builders",
    "build", "building", "builds", "scientist", "scientists", "professor", "cto", "technical lead",
)
REGION_TERMS = (
    "southeast asia", "singapore", "vietnam", "indonesia", "thailand", "malaysia",
    "philippines", "cambodia", "laos", "myanmar", "brunei", "timor-leste",
    "jakarta", "hanoi", "ho chi minh", "bangkok", "manila", "kuala lumpur",
)


def _matches(text: str, terms: tuple[str, ...]) -> list[str]:
    normalized = text.casefold()
    return [
        term for term in terms
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized)
    ]


ROLE_QUERY_GROUPS = {
    "builder": ("builder", "builders", "build", "building", "builds"),
    "founder": ("founder", "founders", "cofounder", "co-founder"),
    "researcher": ("researcher", "researchers", "research", "scientist", "scientists"),
    "engineer": ("engineer", "engineers", "engineering"),
    "developer": ("developer", "developers", "developing"),
    "operator": ("operator", "operators", "cto", "technical lead"),
}


def campaign_criteria(segment: str) -> dict:
    normalized = segment.casefold()
    domains = _matches(segment, DOMAIN_TERMS)
    roles = [
        group for group, terms in ROLE_QUERY_GROUPS.items()
        if _matches(normalized, terms)
    ]
    if not roles:
        roles = ["builder", "founder", "researcher", "engineer", "developer", "operator"]
    regions = _matches(segment, REGION_TERMS)
    return {"domains": domains, "roles": roles, "requires_region": bool(regions), "regions": regions}


def _role_query_terms(groups: list[str]) -> list[str]:
    return list(dict.fromkeys(term for group in groups for term in ROLE_QUERY_GROUPS[group]))


def assess_candidate_quality(
    candidate: dict,
    evidence: list[dict],
    *,
    segment: str = "AI robotics",
    require_region: bool = False,
) -> dict:
    profile_text = " ".join(
        value for value in (candidate.get("bio"), candidate.get("location")) if value
    )
    evidence_text = " ".join(item.get("excerpt", "") for item in evidence)
    all_text = f"{profile_text} {evidence_text}"
    domain_matches = _matches(all_text, DOMAIN_TERMS)
    role_matches = _matches(all_text, ROLE_TERMS)
    region_matches = _matches(f"{candidate.get('location') or ''} {candidate.get('bio') or ''}", REGION_TERMS)
    domain_keywords = campaign_criteria(segment)["domains"] or list(DOMAIN_TERMS)
    post_evidence = [
        item for item in evidence
        if item.get("source_type") == "post"
        and _matches(item.get("excerpt", ""), tuple(domain_keywords))
    ]
    has_supporting_sources = len(post_evidence) >= 5
    created_at = candidate.get("x_account_created_at")
    try:
        account_age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(created_at.replace("Z", "+00:00"))).days if created_at else None
    except (TypeError, ValueError):
        account_age_days = None
    account_old_enough = account_age_days is not None and account_age_days >= 365

    score = (
        (30 if domain_matches else 0)
        + (30 if role_matches else 0)
        + (25 if has_supporting_sources else (10 if evidence else 0))
        + (15 if region_matches else 0)
    )
    missing = []
    if not domain_matches:
        missing.append("No clear AI/robotics signal in the profile or evidence.")
    if not role_matches:
        missing.append("No clear builder, founder, or researcher role signal.")
    if not has_supporting_sources:
        missing.append(f"Need at least 5 public posts containing campaign keywords; found {len(post_evidence)}.")
    if not account_old_enough:
        missing.append("X account must be at least 1 year old; creation date is missing or account is newer.")
    if require_region and not region_matches:
        missing.append("Southeast Asia location is not established by the saved data.")

    eligible = bool(
        domain_matches
        and role_matches
        and has_supporting_sources
        and account_old_enough
        and (region_matches or not require_region)
        and score >= 70
    )
    return {
        "score": score,
        "eligible": eligible,
        "signals": {
            "domain": domain_matches,
            "role": role_matches,
            "region": region_matches,
            "source_count": len(evidence),
            "post_count": len(post_evidence),
            "account_age_days": account_age_days,
            "account_old_enough": account_old_enough,
            "region_required": require_region,
        },
        "missing": missing,
    }
