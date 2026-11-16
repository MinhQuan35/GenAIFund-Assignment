import re
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException

from src.integrations.x_api import api_request
from src.schemas.candidates import CandidateCreate, EvidenceCreate
from src.schemas.x_integration import DiscoveryRequest
from src.services.campaigns import _campaign_or_404, add_candidate
from src.services.candidate_quality import assess_candidate_quality, campaign_criteria
from src.services.storage import database_client, database_operation

STOP_WORDS = {
    "a", "an", "and", "as", "at", "based", "by", "for", "from", "in", "into",
    "is", "of", "on", "or", "the", "that", "this", "to", "with", "across",
    "people", "builders", "working",
}
MIN_RELEVANT_POSTS = 2
TIMELINE_POSTS_TO_CHECK = 10


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


def _search_query(segment: str, custom_query: str | None) -> tuple[str, dict]:
    criteria = campaign_criteria(segment)
    criteria["segment"] = segment
    if not criteria["domains"]:
        raise HTTPException(status_code=422, detail="Target segment must name an AI or robotics domain, such as AI, robotics, or machine learning.")
    if custom_query:
        query = custom_query.strip()
    else:
        domain_group = "(" + " OR ".join(f'"{term}"' for term in criteria["domains"]) + ")"
        query = f"{domain_group} -is:retweet"
    if not query or len(query) > 512:
        raise HTTPException(status_code=422, detail="Provide a valid X recent-search query.")
    return query, criteria


def _evidence_for(user: dict, posts: list[dict]) -> list[EvidenceCreate]:
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
        for post in posts[:5]
        if post.get("id") and post.get("text")
    )
    return evidence


def _relevant_posts(segment: str, posts: list[dict]) -> list[dict]:
    terms = campaign_criteria(segment)["domains"]
    relevant = []
    for post in posts:
        text = post.get("text", "")
        if any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text, re.IGNORECASE) for term in terms):
            relevant.append(post)
    return relevant


def _merge_posts(*post_groups: list[dict]) -> list[dict]:
    merged = {}
    for group in post_groups:
        for post in group:
            if post.get("id"):
                merged[post["id"]] = post
    return list(merged.values())


def _candidate_quality(user: dict, evidence: list[EvidenceCreate], criteria: dict) -> dict:
    evidence_rows = [item.model_dump() for item in evidence]
    return assess_candidate_quality(
        user,
        evidence_rows,
        segment=criteria["segment"],
        require_region=criteria["requires_region"],
    )


def discover_candidates(campaign_id: UUID, payload: DiscoveryRequest) -> dict:
    client = database_client()
    campaign = _campaign_or_404(client, campaign_id)
    query, criteria = _search_query(campaign["segment"], payload.query)

    posts_per_page = min(100, max(10, payload.target_users * 3))
    max_pages = 5
    timeline_profile_limit = min(4, max(1, payload.target_users))
    timeline_profiles_checked = 0
    users: dict[str, dict] = {}
    posts_by_user: dict[str, list[dict]] = {}
    seeds = database_operation(
        lambda: client.table("campaign_seeds")
        .select("username")
        .eq("campaign_id", str(campaign_id))
        .order("username")
        .limit(10)
        .execute()
        .data
    )
    pages_read = 0

    saved = 0
    excluded = 0
    excluded_reasons: dict[str, int] = {}
    discovered_user_ids: set[str] = set()

    for seed in seeds:
        if saved >= payload.target_users or timeline_profiles_checked >= timeline_profile_limit:
            break
        username = seed["username"]
        try:
            lookup = api_request(
                "GET",
                f"/users/by/username/{username}",
                params={"user.fields": "name,username,description,location,verified,created_at"},
            )
        except HTTPException as error:
            if error.status_code != 403:
                raise
            excluded += 1
            reason = "X project/access tier does not allow seed profile lookup"
            excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
            continue
        user = lookup.get("data", {})
        if not user.get("id") or not user.get("username"):
            continue
        if user["id"] in discovered_user_ids:
            continue
        timeline_profiles_checked += 1
        try:
            timeline = api_request(
                "GET",
                f"/users/{user['id']}/tweets",
                params={"max_results": TIMELINE_POSTS_TO_CHECK, "tweet.fields": "created_at,lang", "exclude": "retweets,replies"},
            )
        except HTTPException as error:
            if error.status_code != 403:
                raise
            excluded += 1
            reason = "X project/access tier does not allow reading seed-account timelines"
            excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
            continue
        posts = _relevant_posts(campaign["segment"], timeline.get("data", []))
        if len(posts) < MIN_RELEVANT_POSTS:
            excluded += 1
            reason = f"Fewer than {MIN_RELEVANT_POSTS} posts match the segment keywords"
            excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
            continue
        evidence = _evidence_for(user, posts)
        quality = _candidate_quality(user, evidence, criteria) if evidence else {"eligible": False, "missing": ["No usable profile or post evidence"]}
        if not quality["eligible"]:
            excluded += 1
            for reason in quality["missing"]:
                excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
            continue
        score, reason = _score_candidate(campaign["segment"], user, posts)
        add_candidate(campaign_id, CandidateCreate(
            username=user["username"], x_user_id=user["id"],
            x_account_created_at=datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")) if user.get("created_at") else None,
            display_name=user.get("name"), bio=user.get("description"), location=user.get("location"),
            fit_reason=reason, fit_score=score, evidence=evidence[:6],
        ))
        saved += 1
        discovered_user_ids.add(user["id"])

    if saved < payload.target_users:
        next_token = None
        for _ in range(max_pages):
            params = {
                "query": query,
                "max_results": posts_per_page,
                "tweet.fields": "author_id,created_at,lang,public_metrics",
                "expansions": "author_id",
                "user.fields": "name,username,description,location,verified,profile_image_url,created_at",
            }
            if next_token:
                params["next_token"] = next_token
            result = api_request("GET", "/tweets/search/recent", params=params)
            pages_read += 1
            for user in result.get("includes", {}).get("users", []):
                users[user["id"]] = user
            for post in result.get("data", []):
                author_id = post.get("author_id")
                if author_id and author_id in users:
                    posts_by_user.setdefault(author_id, []).append(post)
            next_token = result.get("meta", {}).get("next_token")
            if len(posts_by_user) >= payload.target_users * 2 or not next_token:
                break

    for author_id, posts in posts_by_user.items():
        if saved >= payload.target_users:
            break
        if author_id in discovered_user_ids:
            continue
        user = users[author_id]
        if not user.get("username"):
            excluded += 1
            excluded_reasons["X profile did not include a username"] = excluded_reasons.get("X profile did not include a username", 0) + 1
            continue
        relevant_posts = _relevant_posts(campaign["segment"], posts)
        if len(relevant_posts) < MIN_RELEVANT_POSTS:
            if timeline_profiles_checked >= timeline_profile_limit:
                excluded += 1
                reason = "Timeline verification limit reached for this run"
                excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
                continue
            timeline_profiles_checked += 1
            try:
                timeline = api_request(
                    "GET",
                    f"/users/{author_id}/tweets",
                    params={
                        "max_results": TIMELINE_POSTS_TO_CHECK,
                        "tweet.fields": "created_at,lang",
                        "exclude": "retweets,replies",
                    },
                )
            except HTTPException as error:
                if error.status_code != 403:
                    raise
                excluded += 1
                reason = "X project/access tier does not allow reading this user's post timeline"
                excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
                continue
            timeline_posts = _relevant_posts(campaign["segment"], timeline.get("data", []))
            relevant_posts = _merge_posts(relevant_posts, timeline_posts)
        if len(relevant_posts) < MIN_RELEVANT_POSTS:
            excluded += 1
            reason = f"Fewer than {MIN_RELEVANT_POSTS} posts match the segment keywords"
            excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
            continue
        evidence = _evidence_for(user, relevant_posts)
        quality = _candidate_quality(user, evidence, criteria) if evidence else {"eligible": False, "missing": ["No usable profile or post evidence"]}
        if not quality["eligible"]:
            excluded += 1
            for reason in quality["missing"]:
                excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
            continue
        score, reason = _score_candidate(campaign["segment"], user, posts)
        candidate = CandidateCreate(
            username=user["username"],
            x_user_id=author_id,
            x_account_created_at=datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")) if user.get("created_at") else None,
            display_name=user.get("name"),
            bio=user.get("description"),
            location=user.get("location"),
            fit_reason=reason,
            fit_score=score,
            evidence=evidence,
        )
        add_candidate(campaign_id, candidate)
        saved += 1
        discovered_user_ids.add(author_id)

    return {
        "requested": payload.target_users,
        "candidates_found": saved,
        "saved": saved,
        "excluded": excluded,
        "excluded_reasons": excluded_reasons,
        "pages_read": pages_read,
        "timeline_profiles_checked": timeline_profiles_checked,
        "timeline_profile_limit": timeline_profile_limit,
        "query": query,
        "message": "Review each profile and evidence before generating outreach.",
    }


