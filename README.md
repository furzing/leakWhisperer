# LeakWhisperer

FastAPI backend that ingests smart meter audio, runs Whisper Tiny leak inference, maintains 1000 virtual meters in-memory, and streams real-time alarms over REST + WebSockets. The `frontend/` folder is a placeholder for the React dashboard your teammate will wire up.

## Repo layout
- `backend/` - FastAPI app (`backend/main.py`), utilities, mock meter generator, deployment artifacts
- `frontend/` - empty shell for the UI
- `render.yaml` - infrastructure-as-code definition for Render

## Local backend setup
1. `cd backend`
2. `python -m venv .venv && .\.venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
5. (Optional) run `python backend/mock_generator.py` from another shell to stream fake leaks into the API

## Deploying to Render (free plan friendly)
Render automatically picks up `render.yaml`, so deployment is self-service and works on the free tier:

1. Push this repo to GitHub or GitLab.
2. In Render, create **New +** -> **Blueprint** and point it to the repo.
3. On the first deploy Render provisions the `leakwhisperer-backend` web service defined in `render.yaml`:
   - Installs Python 3.11 and `backend/requirements.txt`
   - Sets `HF_HOME`/`TRANSFORMERS_CACHE` to `/opt/render/project/src/hf-cache` (inside the container) so Whisper weights reuse the same directory between restarts
   - Starts the API via `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Exposes health check `GET /`
4. Subsequent pushes to the default branch trigger auto-deploys; toggle `autoDeploy` off in Render UI if you want to control rollouts manually.

> Free instances do not support persistent disks, so the Whisper cache is ephemeral. Render will re-download the model on each fresh deploy, but restarts of the same instance reuse the cached weights.

### Environment and performance tips
- Stick with the `free` plan in `render.yaml`; upgrade later if you need more RAM/CPU for faster Whisper inference.
- Keep the default region (`frankfurt`) or change it to whatever region is closest to your target users.
- If you need to bypass loading Whisper (for a demo without CPU headroom) temporarily set `PIPELINE_MODEL_ID` in `backend/main.py` to a lighter model ID and redeploy.

## Frontend integration checklist
Your teammate only needs the deployed base URL (for example `https://leakwhisperer-backend.onrender.com`). The important API surfaces are:
- `GET /` - sanity/health
- `GET /meters` - list of all 1000 simulated meters
- `GET /meter/{meter_id}` - detail view
- `GET /stats` - summary numbers for dashboards
- `POST /upload-audio` - send meter audio payloads (used by the mock generator or real sensors)
- `WebSocket /ws/leaks` - subscribe to push notifications when a meter flips to `status = "leak"`

Because CORS is open (`allow_origins=["*"]`), the frontend can call Render directly. Surface the WebSocket URL as `wss://<render-app>.onrender.com/ws/leaks` in the UI.
