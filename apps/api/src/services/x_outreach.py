from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException

from src.integrations.x_api import api_request, current_user_id
from src.services.storage import database_client, database_operation


def send_approved_message(message_id: UUID, recipient_confirmed: bool) -> dict:
    if not recipient_confirmed:
        raise HTTPException(status_code=400, detail="Confirm the recipient is your test account or has agreed to the test.")
    client = database_client()
    rows = database_operation(
        lambda: client.table("message_drafts")
        .select("id,campaign_id,candidate_id,content,status")
        .eq("id", str(message_id))
        .eq("status", "approved")
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Only an approved message can be sent.")
    message = rows[0]
    candidate_rows = database_operation(
        lambda: client.table("candidates")
        .select("id,username,x_user_id")
        .eq("id", message["candidate_id"])
        .limit(1)
        .execute()
        .data
    )
    if not candidate_rows:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    candidate = candidate_rows[0]
    own_user_id = current_user_id()
    if candidate.get("x_user_id") == own_user_id:
        raise HTTPException(status_code=400, detail="Cannot send an outreach DM to the connected account itself.")
    recipient_id = candidate.get("x_user_id")
    if not recipient_id:
        profile = api_request("GET", f"/users/by/username/{candidate['username']}", params={"user.fields": "username"}).get("data", {})
        recipient_id = profile.get("id")
        if not recipient_id:
            raise HTTPException(status_code=404, detail="Candidate account could not be resolved on X.")
        database_operation(lambda: client.table("candidates").update({"x_user_id": recipient_id}).eq("id", candidate["id"]).execute())

    claimed = database_operation(
        lambda: client.table("message_drafts")
        .update({"status": "send_pending", "send_error": None})
        .eq("id", str(message_id))
        .eq("status", "approved")
        .execute()
        .data
    )
    if not claimed:
        raise HTTPException(status_code=409, detail="This message is already being sent or has changed state.")

    try:
        result = api_request(
            "POST",
            f"/dm_conversations/with/{recipient_id}/messages",
            json={"text": message["content"]},
        )
    except HTTPException as error:
        if error.status_code in (400, 401, 403, 429):
            database_operation(
                lambda: client.table("message_drafts")
                .update({"status": "approved", "send_error": error.detail})
                .eq("id", str(message_id))
                .eq("status", "send_pending")
                .execute()
            )
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Send result is uncertain; message is held in send_pending to prevent duplicate delivery.") from None

    data = result.get("data", {})
    updated = database_operation(
        lambda: client.table("message_drafts")
        .update({
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "external_message_id": data.get("dm_event_id"),
            "send_error": None,
        })
        .eq("id", str(message_id))
        .eq("status", "send_pending")
        .execute()
        .data
    )
    if not updated:
        raise HTTPException(status_code=502, detail="X accepted the DM, but the local sent status could not be saved.")
    return updated[0]


def sync_replies() -> dict:
    client = database_client()
    own_user_id = current_user_id()
    messages = database_operation(
        lambda: client.table("message_drafts")
        .select("id,candidate_id,sent_at")
        .eq("status", "sent")
        .not_.is_("sent_at", "null")
        .execute()
        .data
    )
    if not messages:
        return {"checked": 0, "replies_found": 0}
    candidate_ids = list({message["candidate_id"] for message in messages})
    candidates = database_operation(
        lambda: client.table("candidates")
        .select("id,x_user_id,username")
        .in_("id", candidate_ids)
        .execute()
        .data
    )
    candidate_by_id = {candidate["id"]: candidate for candidate in candidates}
    found = 0
    for message in messages:
        candidate = candidate_by_id.get(message["candidate_id"])
        if not candidate:
            continue
        participant_id = candidate.get("x_user_id")
        if not participant_id:
            continue
        events = api_request(
            "GET",
            f"/dm_conversations/with/{participant_id}/dm_events",
            params={"max_results": 100, "dm_event.fields": "created_at,event_type,sender_id,text"},
        ).get("data", [])
        sent_at = datetime.fromisoformat(message["sent_at"].replace("Z", "+00:00"))
        for event in events:
            occurred_at = event.get("created_at")
            if not event.get("id") or not occurred_at or event.get("sender_id") == own_user_id:
                continue
            parsed_time = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
            if parsed_time < sent_at:
                continue
            saved = database_operation(
                lambda event=event, occurred_at=occurred_at: client.table("message_interactions")
                .upsert(
                    {
                        "message_id": message["id"],
                        "external_event_id": event["id"],
                        "event_type": event.get("event_type", "MessageCreate"),
                        "sender_x_user_id": event.get("sender_id"),
                        "text": event.get("text"),
                        "occurred_at": occurred_at,
                    },
                    on_conflict="external_event_id",
                    ignore_duplicates=True,
                )
                .execute()
                .data
            )
            if saved:
                found += 1
            database_operation(
                lambda: client.table("message_drafts")
                .update({"status": "replied"})
                .eq("id", message["id"])
                .eq("status", "sent")
                .execute()
            )
    return {"checked": len(messages), "replies_found": found}
