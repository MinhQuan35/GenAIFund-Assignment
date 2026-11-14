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
uvicorn src.main:app --reload --port 8001
```

The API is available at `http://localhost:8001`. OpenAPI docs are at `http://localhost:8001/docs`.

### Frontend

In a second terminal:

```powershell
cd apps/web
npm install
npm run dev
```

Vite serves the app at `http://localhost:5173` and proxies `/api` requests to FastAPI on port 8001.

`GET /api/v1/health` checks Supabase connectivity and reports whether Foundry is configured. `POST /api/v1/integrations/foundry/check` sends a short model request and may incur a small usage charge.

## X setup

In the X Developer Portal, enable OAuth 2.0 Authorization Code with PKCE and register this exact local callback URL: `http://127.0.0.1:8001/api/v1/integrations/x/callback`. Grant `users.read`, `tweet.read`, `dm.read`, `dm.write`, and `offline.access`. Set `X_CLIENT_ID` and `X_CLIENT_SECRET`, restart FastAPI, then use **Connect X** in the app. OAuth access and refresh tokens are encrypted before they are stored in Supabase. For a deployed environment, set a dedicated `X_TOKEN_ENCRYPTION_KEY` and register the deployed callback URL.

The campaign **Find on X** action uses recent search over the last seven days and reads a small number of public posts from up to ten seed accounts. X plan/endpoint access and rate limits still apply. DM sending is available only after a draft is approved and the operator confirms the recipient is a controlled test account or has agreed to the test. A send with an uncertain network outcome remains locked in `send_pending` to avoid a duplicate. **Sync replies** reads DM events for tracked sent conversations.

## Database migration

Apply `supabase/migrations/202611130001_create_outreach_schema.sql` in the Supabase SQL editor before using campaign endpoints. It creates the campaign, candidate, evidence, and message tables with RLS enabled. The backend uses the server-side Supabase key; browser keys are not used for these writes.

The backend reads the root `.env` file. Start from `.env.example` when configuring a new checkout. Keep secrets in `.env`; never expose server keys through `VITE_` variables.
