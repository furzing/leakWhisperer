# LeakWhisperer

FastAPI backend that ingests smart meter audio, uses the free HuggingFace Inference API (Whisper Tiny) for speech-to-text, maintains 1000 virtual meters in-memory, auto-simulates their hourly uploads, and streams real-time alarms over REST + WebSockets. The `frontend/` folder is a placeholder for the React dashboard your teammate will wire up.

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

## Environment variables
- `HF_API_TOKEN` - **recommended**. Use a free HuggingFace token so calls to `openai/whisper-tiny` are authorized. Set locally via `$env:HF_API_TOKEN="hf_xxx"` or add it as a secret in Render after the blueprint is created.
- `HF_API_URL` - override the default HuggingFace model endpoint if you deploy your own Space/Inference Endpoint.
- `HF_API_TIMEOUT` - seconds before the backend times out waiting for HuggingFace (default `45`).
- `SIMULATE_METERS` - `true` by default. Toggle the built-in virtual meter simulator off (set to `false`) if you plan to push data from a separate process.
- `SIM_BATCH_SIZE` - number of meters processed per simulator batch (default `3`).
- `SIM_SLEEP_SECONDS` - delay between simulator batches (default `2.5`).
- `SIM_LEAK_CHANCE` - probability that a simulated clip is a leak (default `0.015`, roughly 1.5%).

## Deploying to Render (free plan friendly)
Render automatically picks up `render.yaml`, so deployment is self-service and works on the free tier:

1. Push this repo to GitHub or GitLab.
2. In Render, create **New +** -> **Blueprint** and point it to the repo.
3. On the first deploy Render provisions the `leakwhisperer-backend` web service defined in `render.yaml`:
   - Installs Python 3.11 and `backend/requirements.txt`
   - Starts the API via `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Exposes health check `GET /`
   - After the initial build, add the `HF_API_TOKEN` env var in Render so HuggingFace accepts requests
4. Subsequent pushes to the default branch trigger auto-deploys; toggle `autoDeploy` off in Render UI if you want to control rollouts manually.

### Environment and performance tips
- Stick with the `free` plan in `render.yaml`; Whisper work now happens on HuggingFace's infrastructure so the dyno only handles lightweight logic.
- Keep the default region (`frankfurt`) or change it to whatever region is closest to your target users.
- Tune the simulator vars if you need faster/slower leak traffic. Smaller `SIM_BATCH_SIZE` or larger `SIM_SLEEP_SECONDS` reduces the number of HuggingFace calls per minute.
- If HuggingFace throttles you, slow the simulator, disable it and run `backend/mock_generator.py` locally, or point `HF_API_URL` to your own hosted Space.

## Frontend integration checklist
Your teammate only needs the deployed base URL (for example `https://leakwhisperer-backend.onrender.com`). The important API surfaces are:
- `GET /` - sanity/health
- `GET /meters` - list of all 1000 simulated meters
- `GET /meter/{meter_id}` - detail view
- `GET /stats` - summary numbers for dashboards
- `POST /upload-audio` - send meter audio payloads (used by the mock generator or real sensors)
- `WebSocket /ws/leaks` - subscribe to push notifications when a meter flips to `status = "leak"`

Because CORS is open (`allow_origins=["*"]`), the frontend can call Render directly. Surface the WebSocket URL as `wss://<render-app>.onrender.com/ws/leaks` in the UI.
