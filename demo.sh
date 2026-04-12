#!/usr/bin/env bash
# demo.sh — ThePlanner end-to-end demo
#
# Modes (set via env var or flag):
#   MOCK=1   (default) No Isaac Sim, no Ollama needed. Everything simulated.
#   MOCK=0             Real Ollama (llama3:8b) + real planner + Isaac Sim GUI.
#                      Requires ~/.local/share/ov/pkg/isaac-sim-5.1.0/python.sh
#                      Override Isaac Sim path: ISAAC_PY=/path/to/python.sh
#
# Usage:
#   ./demo.sh                                  # mock demo, default goal
#   ./demo.sh "Stack the blue cylinder on the red cube"
#   MOCK=0 ./demo.sh "Move the green sphere to zone B"
#   ./demo.sh --fail                           # inject failure at step 1 → replan
#   ./demo.sh --build                          # (re)build C++ planner first

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[0;33m'
BLU='\033[0;34m'; CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'

info()    { echo -e "${BLU}[info]${RST}  $*"; }
success() { echo -e "${GRN}[ok]${RST}    $*"; }
warn()    { echo -e "${YLW}[warn]${RST}  $*"; }
error()   { echo -e "${RED}[error]${RST} $*" >&2; }
step()    { echo -e "\n${BLD}${CYN}━━ $* ${RST}"; }

# ── Defaults ──────────────────────────────────────────────────────────────────
MOCK="${MOCK:-1}"
FAIL_STEP="${FAIL_STEP:--1}"      # -1 = no injection
GOAL=""
HUB_PORT=8000
HUB_URL="http://localhost:${HUB_PORT}"
BUILD=0

# Parse flags and optional goal argument
for arg in "$@"; do
  case "$arg" in
    --fail)  FAIL_STEP=1 ;;
    --build) BUILD=1 ;;
    --help)
      echo "Usage: ./demo.sh [goal] [--fail] [--build]"
      echo "  goal     natural-language goal (default: Move the red cube to zone C)"
      echo "  --fail   inject failure at step 1 to demo replan loop"
      echo "  --build  rebuild C++ planner before running"
      exit 0 ;;
    --*) ;;   # ignore unknown flags
    *)   GOAL="$arg" ;;
  esac
done
GOAL="${GOAL:-Move the red cube to zone C}"

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
HUB_SRC="${REPO_ROOT}/SystemCode/ros2_bridge/src"
MONITOR_SRC="${REPO_ROOT}/SystemCode/monitor"
PLANNER_DIR="${REPO_ROOT}/SystemCode/planner"
PLANNER_BIN="${PLANNER_DIR}/build/planner_node"

# PIDs to clean up
HUB_PID=""
UI_PID=""

cleanup() {
  echo ""
  info "Shutting down…"
  [[ -n "$HUB_PID" ]] && kill "$HUB_PID" 2>/dev/null && info "Hub stopped."
  [[ -n "$UI_PID"  ]] && kill "$UI_PID"  2>/dev/null && info "UI server stopped."
  exit 0
}
trap cleanup INT TERM EXIT

# ── Header ────────────────────────────────────────────────────────────────────
echo -e "${BLD}"
echo "╔══════════════════════════════════════════╗"
echo "║        ThePlanner — End-to-End Demo      ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${RST}"
echo -e "  Goal  : ${BLD}${GOAL}${RST}"
echo -e "  Mode  : $([ "$MOCK" = "1" ] && echo "${GRN}Mock (no GPU/Ollama needed)${RST}" || echo "${YLW}Real Ollama + planner + Isaac Sim GUI${RST}")"
echo -e "  Fail  : $([ "$FAIL_STEP" != "-1" ] && echo "${YLW}inject at step ${FAIL_STEP} → replan demo${RST}" || echo "none")"
echo ""

# ── Step 0: Build planner (optional) ─────────────────────────────────────────
if [[ "$BUILD" = "1" || ! -f "$PLANNER_BIN" ]]; then
  step "Building C++ planner"
  cmake -B "${PLANNER_DIR}/build" -S "${PLANNER_DIR}" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -Wno-dev --log-level=WARNING
  cmake --build "${PLANNER_DIR}/build" --target planner_node
  success "planner_node built → ${PLANNER_BIN}"
fi

# ── Step 1: Start hub ─────────────────────────────────────────────────────────
step "Starting Agent Hub (port ${HUB_PORT})"

MOCK_PLANNER_VAL="$( [ "$MOCK" = "1" ] && echo "1" || echo "0" )"
MOCK_ISAAC_VAL="$(   [ "$MOCK" = "1" ] && echo "1" || echo "0" )"

ISAAC_PY="${ISAAC_PY:-${HOME}/.local/share/ov/pkg/isaac-sim-5.1.0/python.sh}"

export MOCK_PLANNER="$MOCK_PLANNER_VAL"
export MOCK_ISAAC="$MOCK_ISAAC_VAL"
export MOCK_FAIL_STEP="$FAIL_STEP"
export PLANNER_BIN
export DOMAIN_FILE="${PLANNER_DIR}/domain/tabletop.pddl"

# Add llm_agent to path so hub can import nl_to_pddl
export PYTHONPATH="${REPO_ROOT}/SystemCode/llm_agent/src:${PYTHONPATH:-}"

# Kill any stale process on the port first
if lsof -ti tcp:"${HUB_PORT}" >/dev/null 2>&1; then
  warn "Port ${HUB_PORT} in use — stopping existing process."
  lsof -ti tcp:"${HUB_PORT}" | xargs kill -9 2>/dev/null || true
  sleep 0.5
fi

uvicorn agent_hub:app \
  --host 127.0.0.1 --port "${HUB_PORT}" \
  --app-dir "${HUB_SRC}" \
  --log-level warning &
HUB_PID=$!

# Wait for hub to be ready
for i in $(seq 1 20); do
  sleep 0.5
  if curl -sf "${HUB_URL}/docs" >/dev/null 2>&1; then
    success "Hub ready at ${HUB_URL}"
    break
  fi
  if [[ $i -eq 20 ]]; then
    error "Hub did not start within 10s. Check port ${HUB_PORT}."
    exit 1
  fi
done

# ── Step 2: Submit goal ───────────────────────────────────────────────────────
step "Submitting goal"
info "Goal: \"${GOAL}\""

GOAL_RESP=$(curl -sf -X POST "${HUB_URL}/goal" \
  -H "Content-Type: application/json" \
  -d "{\"goal\":\"${GOAL}\"}")

PLAN_ID=$(echo "$GOAL_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['plan_id'])")
STEPS=$(echo "$GOAL_RESP"   | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['steps'])")
COST=$(echo "$GOAL_RESP"    | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['cost'],1))")

success "Plan created: ${PLAN_ID:0:8}…"
info    "Steps: ${STEPS}  |  Cost: ${COST}"

# ── Step 3: Show action sequence ──────────────────────────────────────────────
step "Action Sequence"
curl -sf "${HUB_URL}/plan/${PLAN_ID}" | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for a in data['actions']:
    print(f\"  [{a['step']}] {a['name']}  (cost {a.get('cost',1.0):.1f})\")
"

# ── Step 4: Execute plan ──────────────────────────────────────────────────────

if [[ "$MOCK" = "1" ]]; then
  step "Executing Plan (Agent 4 — mock)"

  set +e
  python3 - <<PYEOF
import sys, os, json, requests
sys.path.insert(0, "${HUB_SRC}")
sys.path.insert(0, "${REPO_ROOT}/SystemCode/llm_agent/src")

from isaac_executor import IsaacExecutor, MockExecutor

actions = requests.get("${HUB_URL}/plan/${PLAN_ID}").json()["actions"]

def _set_status(status):
    requests.post("${HUB_URL}/execute_status",
                  json={"plan_id": "${PLAN_ID}", "status": status})

def _report_step(result):
    colour = "\033[0;32m✓\033[0m" if result.success else "\033[0;31m✗\033[0m"
    print(f"  {colour}  step {result.step}: {result.action}")
    if not result.success:
        print(f"     \033[0;31m↳ {result.message}\033[0m")
    requests.post("${HUB_URL}/execute_status", json={
        "plan_id": "${PLAN_ID}", "status": "running",
        "step": result.step, "action": result.action,
        "success": result.success, "message": result.message,
    })

executor = IsaacExecutor(plan_id="${PLAN_ID}", mock=True)
executor._set_status  = _set_status
executor._report_step = _report_step
executor._backend     = MockExecutor(fail_at_step=${FAIL_STEP}, step_delay=0.15)

ok = executor.run_plan(actions)
sys.exit(0 if ok else 1)
PYEOF
  EXEC_EXIT=$?
  set -e

else
  step "Executing Plan (Agent 4 — Isaac Sim 5.1 GUI)"

  # Verify Isaac Sim python.sh exists
  if [[ ! -x "$ISAAC_PY" ]]; then
    error "Isaac Sim not found at ${ISAAC_PY}"
    error "Set ISAAC_PY=/path/to/isaac-sim-X.Y.Z/python.sh or use MOCK=1"
    exit 1
  fi

  # Build the actions JSON payload from the hub
  ACTIONS_JSON=$(curl -sf "${HUB_URL}/plan/${PLAN_ID}" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({'plan_id':d['plan_id'],'actions':d['actions']}))")

  info "Launching Isaac Sim — viewport will open shortly…"
  info "isaac.py: ${ISAAC_PY}"

  set +e
  MOCK_ISAAC=0 \
  HUB_URL="${HUB_URL}" \
  PYTHONPATH="${REPO_ROOT}/SystemCode/llm_agent/src:${PYTHONPATH:-}" \
  "${ISAAC_PY}" "${HUB_SRC}/isaac_executor.py" "${ACTIONS_JSON}"
  EXEC_EXIT=$?
  set -e
fi

# ── Step 5: Monitor watches and replans if needed ─────────────────────────────
step "Monitor (Agent 3)"

python3 - <<PYEOF
import sys, os, json, requests, time
sys.path.insert(0, "${MONITOR_SRC}")
sys.path.insert(0, "${REPO_ROOT}/SystemCode/llm_agent/src")

from monitor import Monitor, PlanStatus
from knowledge_graph import build_default_scene

plan_id = "${PLAN_ID}"

def _get(path):
    r = requests.get("${HUB_URL}" + path, timeout=5)
    r.raise_for_status()
    return r.json()

def _post(path, body):
    r = requests.post("${HUB_URL}" + path, json=body, timeout=5)
    r.raise_for_status()
    return r.json()

events = []
def on_event(ev):
    events.append(ev)
    if ev.event == "status_change":
        f = ev.detail['from'].upper()
        t = ev.detail['to'].upper()
        colour = "\033[0;32m" if t == "SUCCESS" else "\033[0;31m" if t == "FAILURE" else "\033[0;33m"
        print(f"  {colour}{f} → {t}\033[0m")
    elif ev.event == "replan":
        print(f"  \033[0;33m↺ Replanning (attempt {ev.detail['attempt']})…\033[0m")

m = Monitor(plan_id=plan_id, hub_url="${HUB_URL}",
            kg=build_default_scene(), on_event=on_event)
m._get    = _get
m._post   = _post
m._actions = requests.get("${HUB_URL}/plan/${PLAN_ID}").json()["actions"]

# Single tick — status already set by executor above
m._tick()

if m._status == PlanStatus.SUCCESS:
    # Read world state from hub (authoritative post-execution state)
    ws = requests.get("${HUB_URL}/plan/${PLAN_ID}").json()
    print(f"\n  \033[0;32mFinal plan status from hub:\033[0m")
    for a in ws.get("actions", []):
        print(f"    [{a['step']}] {a['name']}")
    print(f"\n  Events recorded: {len(events)}")
PYEOF

# ── Step 6: Final status ──────────────────────────────────────────────────────
step "Final Status"

STATUS=$(curl -sf "${HUB_URL}/status/${PLAN_ID}" | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")

case "$STATUS" in
  success) echo -e "  ${GRN}${BLD}✓ Plan succeeded${RST}" ;;
  failure) echo -e "  ${RED}${BLD}✗ Plan failed${RST}" ;;
  *)       echo -e "  ${YLW}${BLD}? Status: ${STATUS}${RST}" ;;
esac

echo ""
echo -e "  Plan ID : ${PLAN_ID}"
echo -e "  Hub API : ${HUB_URL}/docs"
echo ""

# ── Step 7: Offer to open Web UI ─────────────────────────────────────────────
UI_DIR="${REPO_ROOT}/SystemCode/web_ui"
if [[ -f "${UI_DIR}/index.html" ]]; then
  step "Web UI"
  python3 -m http.server 3000 --directory "${UI_DIR}" \
    >/dev/null 2>&1 &
  UI_PID=$!
  success "Web UI running at http://localhost:3000"
  info    "Hub stays alive — press Ctrl+C to quit."
  wait "$HUB_PID"
fi
