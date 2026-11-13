# GenAI Fund Outreach

Prototype workspace for discovering relevant AI and robotics builders and preparing reviewed outreach.

## Applications

- `apps/web`: React JavaScript frontend powered by Vite.
- `apps/api`: FastAPI backend.
- Supabase, X, and Azure AI Foundry integrations will be added in later steps.

## Run locally

### Backend

```powershell
cd apps/api
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. OpenAPI docs are at `http://localhost:8000/docs`.

### Frontend

In a second terminal:

```powershell
cd apps/web
npm install
npm run dev
```

Vite serves the app at `http://localhost:5173` and proxies `/api` requests to FastAPI on port 8000.

The backend reads the root `.env` file. Start from `.env.example` when configuring a new checkout. Keep secrets in `.env`; never expose server keys through `VITE_` variables.
