import re

DOMAIN_TERMS = (
    "artificial intelligence", "machine learning", "computer vision", "large language model",
    "embodied ai", "deep learning", "robotics", "robot", "llm", "inference", "ai",
)
ROLE_TERMS = (
    "co-founder", "cofounder", "founder", "researcher", "research scientist", "engineer",
    "developer", "builder", "building", "builds", "scientist", "professor", "cto", "technical lead",
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


def assess_candidate_quality(candidate: dict, evidence: list[dict]) -> dict:
    profile_text = " ".join(
        value for value in (candidate.get("bio"), candidate.get("location")) if value
    )
    evidence_text = " ".join(item.get("excerpt", "") for item in evidence)
    all_text = f"{profile_text} {evidence_text}"
    domain_matches = _matches(all_text, DOMAIN_TERMS)
    role_matches = _matches(all_text, ROLE_TERMS)
    region_matches = _matches(f"{candidate.get('location') or ''} {evidence_text}", REGION_TERMS)
    post_evidence = [item for item in evidence if item.get("source_type") == "post"]
    has_supporting_sources = len(evidence) >= 2 or any(len(item.get("excerpt", "")) >= 50 for item in post_evidence)

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
        missing.append("Add another source or a substantial public post as evidence.")
    if not region_matches:
        missing.append("Southeast Asia location is not established by the saved data.")

    eligible = bool(domain_matches and role_matches and has_supporting_sources and score >= 70)
    return {
        "score": score,
        "eligible": eligible,
        "signals": {
            "domain": domain_matches,
            "role": role_matches,
            "region": region_matches,
            "source_count": len(evidence),
            "post_count": len(post_evidence),
        },
        "missing": missing,
    }
