# GenAI Fund Outreach Prototype

React JavaScript + FastAPI prototype for finding AI and robotics builders on X, reviewing evidence, scoring candidate fit, drafting personalized DMs, and tracking approved test outreach.

## What It Does

- Creates outreach campaigns from a segment and optional X seed accounts.
- Finds candidates through X recent search or by inspecting configured seed accounts.
- Filters candidates using profile/post evidence, role relevance, and segment keywords.
- Scores qualified candidates with the selected LLM provider and shows evidence confidence separately.
- Drafts DMs from saved evidence for human review and approval.
- Sends only after approval and an explicit test-recipient confirmation.
- Tracks sent messages and syncs replies.

The prototype never sends a DM during discovery. Do not test-send to people who have not agreed to receive a test message.

## Evaluator Prerequisites

Have these ready before starting the 15-minute setup:

- A Supabase project URL and server-side secret/service-role key.
- An X Developer App with OAuth 2.0 credentials, the required scopes, access to search/timeline/DM endpoints, and API credits. OAuth credentials alone do not provide endpoint access or credits; X API calls are pay-per-usage.
- Either an Azure AI Foundry deployment and key, or an OpenAI API key/model.

Without existing accounts, credentials, and X access/credits, the app can start locally, but live discovery, AI scoring, or DM testing cannot be completed within 15 minutes. Evaluators should use their own authorized accounts and keys, not the repository owner's credentials.

## 15-Minute Setup

The under-15-minute setup assumes the evaluator already has working Supabase, X Developer App credentials/access, and one LLM API credential. Creating those external accounts, obtaining X endpoint access, or buying X credits is outside the setup time.

### Prerequisites

- Python 3.11 or later
- Node.js 20.19+ or 22.12+
- Supabase project URL and a server-side secret/service-role key
- X OAuth 2.0 client ID and client secret, with API access/credits for the endpoints being tested
- Either an Azure AI Foundry deployment or an OpenAI API key

### 1. Configure Environment

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
```

Set these values in `.env`:

| Variable | Value |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY` | Server-side Supabase key; never put this in React/Vite variables |
| `X_CLIENT_ID` | X Developer App OAuth 2.0 client ID |
| `X_CLIENT_SECRET` | X Developer App client secret |
| `LLM_PROVIDER` | `foundry` or `openai` |

For `LLM_PROVIDER=foundry`, also set `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_API_KEY`, and `AZURE_OPENAI_DEPLOYMENT_NAME`. The base URL ends with `/openai/v1/`, not `/responses`.

For `LLM_PROVIDER=openai`, set `OPENAI_API_KEY` and `OPENAI_MODEL`. `OPENAI_BASE_URL` defaults to `https://api.openai.com/v1`.

Leave `X_ACCESS_TOKEN` and `X_REFRESH_TOKEN` blank. The app obtains and stores OAuth tokens after the user connects X. For local development, the token encryption key is derived from the Supabase server key; deployments should set a dedicated `X_TOKEN_ENCRYPTION_KEY`.

### 2. Configure X OAuth

In the X Developer Portal, enable OAuth 2.0 Authorization Code with PKCE and add this exact callback URL:

```text
http://127.0.0.1:8004/api/v1/integrations/x/callback
```

Grant these scopes:

```text
users.read tweet.read dm.read dm.write offline.access
```

The OAuth scopes do not by themselves guarantee endpoint access. The X Developer Project must have access/credits for search, user timeline, and DM endpoints used by the prototype.

### 3. Apply Database Migrations

In the Supabase SQL Editor, run these files in order:

1. `supabase/migrations/202611130001_create_outreach_schema.sql`
2. `supabase/migrations/202611140001_add_x_integration.sql`
3. `supabase/migrations/202611140002_add_candidate_fit_assessment.sql`
4. `supabase/migrations/202611160001_add_x_account_age.sql`
5. `supabase/migrations/202611160002_add_campaign_candidate_archive.sql`

The migrations enable RLS and restrict application data access to the backend service key. React does not use a Supabase service-role key.

### 4. Start Locally

Open two PowerShell terminals.

Terminal 1, API:

```powershell
cd apps/api
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8004
```

Terminal 2, web app:

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`, then go to Overview and select **Connect X**. API documentation is at `http://127.0.0.1:8004/docs`.

If port 5173 is already in use, stop the other Vite process or change the Vite port and proxy in `apps/web/vite.config.js`.

## Docker Setup

Docker runs the built React app and FastAPI together in one container on port 8004. Configure `.env` and apply the Supabase migrations first.

```powershell
Copy-Item .env.example .env
# Fill .env with the credentials described above.
docker compose up --build
```

Open `http://127.0.0.1:8004`. Set `APP_PUBLIC_URL` to the URL the evaluator opens; for local Docker it is `http://127.0.0.1:8004`. For local Docker, register `http://127.0.0.1:8004/api/v1/integrations/x/callback` in X. If hosting elsewhere, set both `APP_PUBLIC_URL` and `X_REDIRECT_URI` to the deployed HTTPS URLs and register that exact callback in X.

Stop the container with Ctrl+C. The container receives credentials at runtime from `.env`; secrets are not copied into the image. Never commit `.env`.

This is a single-user evaluator setup with no application login. Run it locally or behind access controls; do not expose the container publicly with a Supabase server key in its environment.

## Demo Workflow

1. Connect X from Overview.
2. Create a campaign with a clear segment. Optionally provide seed usernames at creation time.
3. Set **Target users** and click **Find on X**.
4. Review the candidates and their evidence. Candidates need at least two matching posts plus role/domain evidence; account age is not a filter.
5. Click **Score with AI** on a qualified candidate. This makes one billable LLM request.
6. Click **Generate DM**, edit/review it in Conversations, and approve it.
7. Send only to an account you control or a person who agreed to the test. Confirm the recipient in the app.
8. Click **Sync replies** to check for a response.

### Seed Search Behavior

When a campaign has seed accounts, **Find on X** checks the configured seed accounts first and skips broad Recent Search for that run. Each seed is checked against the same profile/role and relevant-post criteria; location contributes to fit when present but is not a hard requirement if the profile omits it. If no seed is configured, discovery uses X Recent Search from the last seven days.

Discovery reads up to 10 timeline posts per checked account and checks at most `min(4, target users)` timelines per run. Recent Search itself returns at least 10 posts per request. X charges per resource returned, so the target-user count is not a strict cost cap; monitor the X Developer Console balance before each live search.

## Test Accounts Used

The demo flow used sender `@HunhQun305` and test recipient `@huynhquan5w`. The recipient accepted the message request and replied during the test. These accounts are for evaluating the workflow, not outreach prospects. Only use them for another test if they remain under your control; otherwise substitute accounts you control or recipients who have agreed to participate.

## Service Checks

- `GET /api/v1/health`: checks Supabase connectivity and reports the selected LLM provider configuration.
- `POST /api/v1/integrations/llm/check`: sends a short, billable model request.
- `GET /api/v1/integrations/x/status`: checks the connected X account.

The **Check model** button makes a billable LLM request. Do not use it just to inspect configuration if minimizing usage is important.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Supabase reports unavailable | Verify `SUPABASE_URL` and the server-side key; confirm migrations ran in order |
| X OAuth fails | Confirm Client ID/Secret, scopes, and the exact callback URL in the X Developer Portal |
| X returns 402 | Check project credits/balance in X Developer Console |
| X returns 403 | Check endpoint access for the X project and the OAuth scopes; scopes alone do not enable every endpoint |
| No candidates found | Read the exclusion reasons; broaden the segment or add a relevant seed account. A seed must meet the same evidence criteria |
| LLM call fails | Check `LLM_PROVIDER` and only the credentials for that provider |

## Security and Costs

- Keep all credentials in `.env`; `.env` is gitignored.
- Supabase server keys and X client secret are used only by FastAPI.
- X reads/searches, DM writes, and model requests may incur usage charges. X pricing is per returned resource and can change; check the current balance and rates in the provider console before demos.
- Do not send unsolicited test outreach. The operator approval step is required before a DM can be sent.
