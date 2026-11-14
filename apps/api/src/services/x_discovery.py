import re
from uuid import UUID

from fastapi import HTTPException

from src.integrations.x_api import api_request
from src.schemas.candidates import CandidateCreate, EvidenceCreate
from src.schemas.x_integration import DiscoveryRequest
from src.services.campaigns import _campaign_or_404, add_candidate
from src.services.storage import database_client, database_operation

STOP_WORDS = {"the", "and", "for", "with", "from", "into", "people", "builders", "working", "based", "that", "this", "across"}


def _segment_terms(segment: str) -> list[str]:
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9+#.]{2,}", segment)]
    return list(dict.fromkeys(term for term in terms if term not in STOP_WORDS))[:8]


def _score_candidate(segment: str, user: dict, posts: list[dict]) -> tuple[int, str]:
    terms = _segment_terms(segment)
    haystack = " ".join([user.get("description", ""), user.get("location", ""), *(post.get("text", "") for post in posts)]).lower()
    matched = [term for term in terms if term in haystack]
    score = min(96, round(40 + 56 * len(matched) / max(len(terms), 1))) if matched else 25
    if user.get("verified"):
        score = min(score, 90)
    if matched:
        reason = "Public profile or recent posts mention: " + ", ".join(matched) + "."
    else:
        reason = "Discovered through the campaign search; review the linked source before outreach."
    return score, reason


def discover_candidates(campaign_id: UUID, payload: DiscoveryRequest) -> dict:
    client = database_client()
    campaign = _campaign_or_404(client, campaign_id)
    terms = _segment_terms(campaign["segment"])
    if not payload.query and not terms:
        raise HTTPException(status_code=422, detail="Campaign segment needs searchable keywords or provide a custom query.")
    query = payload.query.strip() if payload.query else ("(" + " OR ".join(f'"{term}"' for term in terms) + ") -is:retweet")
    if not query or len(query) > 512:
        raise HTTPException(status_code=422, detail="Provide a valid X recent-search query.")

    result = api_request(
        "GET",
        "/tweets/search/recent",
        params={
            "query": query,
            "max_results": payload.max_results,
            "tweet.fields": "author_id,created_at,lang,public_metrics",
            "expansions": "author_id",
            "user.fields": "name,username,description,location,verified,profile_image_url",
        },
    )
    users = {user["id"]: user for user in result.get("includes", {}).get("users", [])}
    posts_by_user: dict[str, list[dict]] = {}
    for post in result.get("data", []):
        author_id = post.get("author_id")
        if author_id and author_id in users:
            posts_by_user.setdefault(author_id, []).append(post)

    saved = 0
    for author_id, posts in posts_by_user.items():
        user = users[author_id]
        if not user.get("username"):
            continue
        score, reason = _score_candidate(campaign["segment"], user, posts)
        evidence = []
        if user.get("description"):
            evidence.append(EvidenceCreate(
                source_url=f"https://x.com/{user['username']}",
                source_type="profile",
                excerpt=user["description"][:3000],
            ))
        for post in posts[:5]:
            evidence.append(EvidenceCreate(
                source_url=f"https://x.com/{user['username']}/status/{post['id']}",
                source_type="post",
                excerpt=post.get("text", "")[:3000],
            ))
        if not evidence:
            continue
        candidate = CandidateCreate(
            username=user["username"],
            x_user_id=author_id,
            display_name=user.get("name"),
            bio=user.get("description"),
            location=user.get("location"),
            fit_reason=reason,
            fit_score=score,
            evidence=evidence,
        )
        add_candidate(campaign_id, candidate)
        saved += 1

    seeds = database_operation(
        lambda: client.table("campaign_seeds")
        .select("username")
        .eq("campaign_id", str(campaign_id))
        .order("username")
        .limit(10)
        .execute()
        .data
    )
    for seed in seeds:
        username = seed["username"]
        lookup = api_request("GET", f"/users/by/username/{username}", params={"user.fields": "name,username,description,location,verified"})
        user = lookup.get("data", {})
        if not user.get("id") or not user.get("username"):
            continue
        timeline = api_request(
            "GET",
            f"/users/{user['id']}/tweets",
            params={"max_results": 5, "tweet.fields": "created_at,lang", "exclude": "retweets,replies"},
        )
        posts = timeline.get("data", [])
        evidence = []
        if user.get("description"):
            evidence.append(EvidenceCreate(
                source_url=f"https://x.com/{user['username']}",
                source_type="profile",
                excerpt=user["description"][:3000],
            ))
        evidence.extend(
            EvidenceCreate(
                source_url=f"https://x.com/{user['username']}/status/{post['id']}",
                source_type="post",
                excerpt=post.get("text", "")[:3000],
            )
            for post in posts
            if post.get("text")
        )
        if not evidence:
            continue
        score, reason = _score_candidate(campaign["segment"], user, posts)
        add_candidate(campaign_id, CandidateCreate(
            username=user["username"], x_user_id=user["id"], display_name=user.get("name"),
            bio=user.get("description"), location=user.get("location"), fit_reason=reason,
            fit_score=score, evidence=evidence[:6],
        ))
        saved += 1

    return {
        "candidates_found": len(posts_by_user) + len(seeds),
        "saved": saved,
        "query": query,
        "message": "Review each profile and evidence before generating outreach.",
    }
