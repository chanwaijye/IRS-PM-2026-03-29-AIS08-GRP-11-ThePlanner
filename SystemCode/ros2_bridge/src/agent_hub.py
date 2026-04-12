"""agent_hub.py — FastAPI Integration Hub for ThePlanner.

Orchestrates the multi-agent pipeline:
  Agent 1 (LLM): NL goal → PDDL problem   [nl_to_pddl.py]
  Agent 2 (Planner): PDDL → JSON plan     [planner_node binary]
  Agent 3 (Monitor): world-state updates  [this hub stores state]
  Agent 4 (Isaac Sim): executes plan      [isaac_executor.py]

Endpoints:
  POST /goal                NL goal in → plan_id out
  GET  /plan/{id}           JSON action sequence
  POST /execute/{id}        Dispatch plan to Agent 4 (Isaac Sim executor)
  POST /execute_status      Step feedback from Agent 4
  POST /world_state         perception update
  GET  /status/{id}         running / success / failure
  POST /replan              trigger replanning with new world state

Mock I/O mode: set MOCK_PLANNER=1 env var to skip real planner binary.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Local agent modules (adjust sys.path if running standalone)
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "llm_agent", "src"))
from nl_to_pddl import nl_to_pddl_problem
from knowledge_graph import SceneKnowledgeGraph, build_default_scene

# ── Config ────────────────────────────────────────────────────────────────

PLANNER_BIN = os.environ.get(
    "PLANNER_BIN",
    os.path.join(os.path.dirname(__file__), "../../../planner/build/planner_node"),
)
DOMAIN_FILE = os.environ.get(
    "DOMAIN_FILE",
    os.path.join(os.path.dirname(__file__), "../../../planner/domain/tabletop.pddl"),
)
MOCK_PLANNER = os.environ.get("MOCK_PLANNER", "0") == "1"
MOCK_ISAAC   = os.environ.get("MOCK_ISAAC",   "1") == "1"

# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(title="ThePlanner Agent Hub", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory state store ─────────────────────────────────────────────────

class PlanStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    SUCCESS  = "success"
    FAILURE  = "failure"

class PlanRecord:
    def __init__(self, plan_id: str, goal: str, plan: list[dict]) -> None:
        self.plan_id   = plan_id
        self.goal      = goal
        self.plan      = plan          # list of {step, name, cost}
        self.status    = PlanStatus.PENDING
        self.created   = datetime.utcnow().isoformat()
        self.updated   = self.created
        self.world_state: dict[str, Any] = {}

_store: dict[str, PlanRecord] = {}

# Current scene knowledge graph (updated on /world_state)
_kg: SceneKnowledgeGraph = build_default_scene()

# ── Request / Response models ─────────────────────────────────────────────

class GoalRequest(BaseModel):
    goal: str
    scene_context: dict[str, Any] | None = None

class GoalResponse(BaseModel):
    plan_id: str
    steps: int
    cost: float

class WorldStateUpdate(BaseModel):
    objects: list[dict[str, Any]]   # scene_context['objects'] format
    robot: str = "franka"
    locations: list[str] = ["zone_a", "zone_b", "zone_c"]

class ReplanRequest(BaseModel):
    plan_id: str
    new_goal: str | None = None

class ExecuteStatusUpdate(BaseModel):
    plan_id: str
    status:  str                        # running | success | failure
    step:    int | None = None
    action:  str | None = None
    success: bool | None = None
    message: str = ""

# ── Internal helpers ──────────────────────────────────────────────────────

def _run_planner(pddl_problem: str) -> list[dict[str, Any]]:
    """Write problem to temp file, call planner_node, parse JSON output."""
    if MOCK_PLANNER:
        return [
            {"step": 0, "name": "pick(franka,red_cube,zone_a)",  "cost": 1.0},
            {"step": 1, "name": "move_to(franka,zone_a,zone_c)", "cost": 1.0},
            {"step": 2, "name": "place(franka,red_cube,zone_c)", "cost": 1.0},
        ]

    with tempfile.NamedTemporaryFile(suffix=".pddl", mode="w",
                                     delete=False) as f:
        f.write(pddl_problem)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [PLANNER_BIN, DOMAIN_FILE, tmp_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"planner_node exited {result.returncode}: "
                               f"{result.stderr.strip()}")
        data = json.loads(result.stdout)
        return data.get("actions", [])
    finally:
        os.unlink(tmp_path)


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.post("/goal", response_model=GoalResponse)
def post_goal(req: GoalRequest) -> GoalResponse:
    """Accept a natural-language goal, generate PDDL, run planner."""
    scene = req.scene_context or _kg.to_scene_context()

    pddl = nl_to_pddl_problem(req.goal, scene)

    try:
        actions = _run_planner(pddl)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    plan_id = str(uuid.uuid4())
    record = PlanRecord(plan_id, req.goal, actions)
    record.world_state = scene
    _store[plan_id] = record

    total_cost = sum(a.get("cost", 1.0) for a in actions)
    return GoalResponse(plan_id=plan_id, steps=len(actions), cost=total_cost)


@app.get("/plan/{plan_id}")
def get_plan(plan_id: str) -> dict[str, Any]:
    """Return the full JSON action sequence for a plan."""
    record = _store.get(plan_id)
    if not record:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {
        "plan_id":  plan_id,
        "goal":     record.goal,
        "status":   record.status,
        "created":  record.created,
        "actions":  record.plan,
    }


@app.post("/world_state")
def post_world_state(update: WorldStateUpdate) -> dict[str, str]:
    """Update the scene knowledge graph from a perception update."""
    global _kg
    ctx = {
        "robot":     update.robot,
        "objects":   update.objects,
        "locations": update.locations,
    }
    _kg = SceneKnowledgeGraph.from_scene_context(ctx)
    return {"status": "ok", "nodes": str(_kg)}


@app.get("/status/{plan_id}")
def get_status(plan_id: str) -> dict[str, str]:
    """Return current execution status of a plan."""
    record = _store.get(plan_id)
    if not record:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan_id": plan_id, "status": record.status.value,
            "updated": record.updated}


@app.post("/execute/{plan_id}")
def post_execute(plan_id: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Dispatch a plan to Agent 4 (Isaac Sim executor) in a background thread."""
    record = _store.get(plan_id)
    if not record:
        raise HTTPException(status_code=404, detail="Plan not found")
    if record.status not in (PlanStatus.PENDING, PlanStatus.FAILURE):
        raise HTTPException(
            status_code=409,
            detail=f"Plan already in status '{record.status.value}'"
        )

    record.status  = PlanStatus.RUNNING
    record.updated = datetime.utcnow().isoformat()

    def _run() -> None:
        from isaac_executor import IsaacExecutor
        executor = IsaacExecutor(plan_id=plan_id, mock=MOCK_ISAAC)
        executor.run_plan(record.plan)

    background_tasks.add_task(_run)
    return {"plan_id": plan_id, "status": "running"}


@app.post("/execute_status")
def post_execute_status(update: ExecuteStatusUpdate) -> dict[str, str]:
    """Receive per-step feedback from Agent 4 and update plan status."""
    record = _store.get(update.plan_id)
    if not record:
        return {"status": "unknown_plan"}

    if update.status == "success":
        record.status = PlanStatus.SUCCESS
    elif update.status == "failure":
        record.status = PlanStatus.FAILURE
    elif update.status == "running":
        record.status = PlanStatus.RUNNING

    record.updated = datetime.utcnow().isoformat()

    # Log execution step into world_state for monitor visibility
    if update.step is not None:
        record.world_state[f"step_{update.step}"] = {
            "action":  update.action,
            "success": update.success,
            "message": update.message,
        }

    return {"status": "ok"}


@app.post("/replan")
def post_replan(req: ReplanRequest) -> GoalResponse:
    """Trigger replanning; optionally change the goal."""
    old = _store.get(req.plan_id)
    if not old:
        raise HTTPException(status_code=404, detail="Original plan not found")

    new_goal = req.new_goal or old.goal
    scene = _kg.to_scene_context()
    return post_goal(GoalRequest(goal=new_goal, scene_context=scene))


# ── Dev entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent_hub:app", host="0.0.0.0", port=8000, reload=True)
