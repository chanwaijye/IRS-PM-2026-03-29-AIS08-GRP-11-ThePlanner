# web_ui — ThePlanner Control Panel

Single-page control panel for ThePlanner agent hub. No build step — pure HTML/CSS/JS.

## Features

- Submit natural-language goals → triggers full pipeline (LLM → planner → Isaac Sim)
- Live status polling per plan (pending → running → success/failure)
- Action sequence viewer with per-step status
- One-click **Execute** (re-run) and **Replan** buttons on failed plans
- Optional scene context JSON for custom environments
- Hub online/offline indicator

## Quick Start

```bash
# 1. Start the agent hub (from ros2_bridge/)
MOCK_PLANNER=1 MOCK_ISAAC=1 uvicorn agent_hub:app --reload --port 8000

# 2. Serve the UI (from web_ui/)
python3 -m http.server 3000

# 3. Open http://localhost:3000
```

## Connecting to a non-default hub URL

Set `window.HUB_URL` before the page loads, or edit the `HUB` constant in `index.html`:

```html
<script>window.HUB_URL = "http://192.168.1.100:8000";</script>
```

## CORS

The hub must allow the UI origin. Start uvicorn with:

```bash
MOCK_PLANNER=1 MOCK_ISAAC=1 uvicorn agent_hub:app \
  --reload --port 8000 \
  --header "Access-Control-Allow-Origin:*"
```

Or add FastAPI CORS middleware to `agent_hub.py` for production use.
