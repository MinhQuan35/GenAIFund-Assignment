# GenAI Fund Outreach

Prototype workspace for discovering relevant AI and robotics builders and preparing reviewed outreach.

## Applications

- `apps/web`: React JavaScript frontend powered by Vite.
- `apps/api`: FastAPI backend.
- Supabase health checks and Azure AI Foundry inference checks are wired; X integration will be added later.

## Run locally

### Backend

```powershell
cd apps/api
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8004
```

The API is available at `http://localhost:8004`. OpenAPI docs are at `http://localhost:8004/docs`.

### Frontend

In a second terminal:

```powershell
cd apps/web
npm install
npm run dev
```

Vite serves the app at `http://localhost:5173` and proxies `/api` requests to FastAPI on port 8004.

`GET /api/v1/health` checks Supabase connectivity and reports whether Foundry is configured. `POST /api/v1/integrations/foundry/check` sends a short model request and may incur a small usage charge.

## X setup

In the X Developer Portal, enable OAuth 2.0 Authorization Code with PKCE and register this exact local callback URL: `http://127.0.0.1:8004/api/v1/integrations/x/callback`. Grant `users.read`, `tweet.read`, `dm.read`, `dm.write`, and `offline.access`. Set `X_CLIENT_ID` and `X_CLIENT_SECRET`, restart FastAPI, then use **Connect X** in the app. OAuth access and refresh tokens are encrypted before they are stored in Supabase. For a deployed environment, set a dedicated `X_TOKEN_ENCRYPTION_KEY` and register the deployed callback URL.

The campaign **Find on X** action accepts a target of 1–100 candidates, searches posts from the last seven days, and follows up to five result pages. Each saved candidate must have at least five authored posts containing domain keywords from the segment, and profile/evidence supporting a relevant builder, founder, researcher, or related role. Account age is not a filter. If the segment names a region, the profile location or bio must confirm that region; location-only matches are excluded. When needed, discovery reads up to 20 posts per author and checks at most `min(10, max(2, target × 2))` timelines per run to bound X read charges. X plan/endpoint access and rate limits apply. Discovery also checks up to ten seed accounts against the same post-count and fit criteria. A no-AI quality gate shows relevant-post count before enabling **Score with AI**. **Score with AI** sends the saved profile and evidence to Foundry for one candidate at a time. If no post evidence is saved, it tries to fetch up to five recent public posts from X. Fit score uses role/domain/region; evidence confidence is reported separately. Each click uses a billable Foundry request and may incur X read charges when fetching posts. **Clear candidates** removes unsent candidates and drafts while preserving candidates with sent/pending DMs and their outreach history. DM sending is available only after a draft is approved and the operator confirms the recipient is a controlled test account or has agreed to the test. A send with an uncertain network outcome remains locked in `send_pending` to avoid a duplicate. **Sync replies** reads DM events for tracked sent conversations.

## Database migration

Apply the SQL files in `supabase/migrations/` in filename order before using campaign endpoints. They create the campaign, candidate, evidence, scoring, and message tables with RLS enabled. The backend uses the server-side Supabase key; browser keys are not used for these writes.

The backend reads the root `.env` file. Start from `.env.example` when configuring a new checkout. Keep secrets in `.env`; never expose server keys through `VITE_` variables.
