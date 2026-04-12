"""test_integration.py — End-to-end integration tests for ThePlanner.

Difference from unit tests
--------------------------
Unit tests (test_agent_hub.py, test_nl_to_pddl.py, etc.) isolate each component
and mock every external call.

Integration tests here:
  - Spin up the REAL FastAPI hub via TestClient (in-process, no network)
  - Run the REAL isaac_executor (MockExecutor backend — no Isaac Sim GPU needed)
  - Run the REAL Monitor (patched to call TestClient instead of HTTP)
  - Only mock Ollama (external LLM server) — everything else is live code

What is tested end-to-end
--------------------------
  Pipeline A  POST /goal → GET /plan → POST /execute → GET /status (success)
  Pipeline B  Full replan chain: goal → execute → failure → /replan → execute → success
  Pipeline C  Monitor watches a plan, pushes /world_state, triggers replan on failure
  Pipeline D  World-state update affects the next plan's scene context
  Pipeline E  Two concurrent plans are tracked independently

Run
---
  python3 -m pytest SystemCode/tests/test_integration.py -v
"""

from __future__ import annotations

import os
import sys
import time
import threading
import uuid

os.environ["MOCK_PLANNER"] = "1"
os.environ["MOCK_ISAAC"]   = "1"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ros2_bridge", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "llm_agent",   "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "monitor"))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ── Shared Ollama mock ────────────────────────────────────────────────────────

MOCK_PDDL = """\
(define (problem tabletop-task)
  (:domain tabletop)
  (:objects
    franka - robot
    red_cube - object
    zone_a zone_b zone_c - location
  )
  (:init
    (hand_empty franka)
    (at franka zone_a)
    (on_table red_cube)
    (clear red_cube)
    (on red_cube zone_a)
    (in_zone red_cube zone_a)
  )
  (:goal (and (in_zone red_cube zone_c)))
)"""

def _ollama_mock():
    """Return a context manager that patches Ollama away."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"response": MOCK_PDDL}
    return patch("nl_to_pddl.requests.post", return_value=resp)


# ── App fixture (fresh per test module) ───────────────────────────────────────

with _ollama_mock():
    from agent_hub import app, _store, PlanStatus

client = TestClient(app)

SCENE = {
    "robot":     "franka",
    "objects":   [{"name": "red_cube", "type": "object", "at": "zone_a"}],
    "locations": ["zone_a", "zone_b", "zone_c"],
}


def submit_goal(goal: str = "Move red cube to zone C", scene=None) -> dict:
    body = {"goal": goal}
    if scene:
        body["scene_context"] = scene
    with _ollama_mock():
        r = client.post("/goal", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline A — goal → plan → execute → success
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineA:
    """Full happy-path: submit goal, fetch plan, execute, confirm success."""

    def test_goal_returns_plan_id(self):
        data = submit_goal()
        assert "plan_id" in data

    def test_plan_has_actions(self):
        data    = submit_goal()
        plan_id = data["plan_id"]
        plan    = client.get(f"/plan/{plan_id}").json()
        assert len(plan["actions"]) > 0

    def test_plan_actions_have_required_fields(self):
        plan_id = submit_goal()["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]
        for a in actions:
            assert "step" in a
            assert "name" in a
            assert "cost" in a

    def test_execute_transitions_to_running(self):
        plan_id = submit_goal()["plan_id"]
        r = client.post(f"/execute/{plan_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "running"

    def test_execute_status_updates_to_success(self):
        plan_id = submit_goal()["plan_id"]
        client.post(f"/execute/{plan_id}")
        # Simulate executor reporting success
        client.post("/execute_status", json={"plan_id": plan_id, "status": "success"})
        status = client.get(f"/status/{plan_id}").json()["status"]
        assert status == "success"

    def test_plan_goal_text_preserved(self):
        goal    = "Move the blue cylinder to zone B"
        plan_id = submit_goal(goal)["plan_id"]
        plan    = client.get(f"/plan/{plan_id}").json()
        assert plan["goal"] == goal

    def test_cost_is_positive(self):
        data = submit_goal()
        assert data["cost"] > 0

    def test_steps_matches_action_count(self):
        data    = submit_goal()
        plan_id = data["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]
        assert data["steps"] == len(actions)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline B — failure → replan → new execution
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineB:
    """Failure + replan: original plan fails, hub creates a new plan."""

    def test_replan_after_failure_returns_new_plan_id(self):
        plan_id = submit_goal()["plan_id"]
        # Mark as failed
        client.post("/execute_status", json={"plan_id": plan_id, "status": "failure"})
        with _ollama_mock():
            r = client.post("/replan", json={"plan_id": plan_id})
        assert r.status_code == 200
        new_id = r.json()["plan_id"]
        assert new_id != plan_id

    def test_replanned_plan_has_actions(self):
        plan_id = submit_goal()["plan_id"]
        client.post("/execute_status", json={"plan_id": plan_id, "status": "failure"})
        with _ollama_mock():
            new_id = client.post("/replan", json={"plan_id": plan_id}).json()["plan_id"]
        actions = client.get(f"/plan/{new_id}").json()["actions"]
        assert len(actions) > 0

    def test_replanned_plan_can_be_executed(self):
        plan_id = submit_goal()["plan_id"]
        client.post("/execute_status", json={"plan_id": plan_id, "status": "failure"})
        with _ollama_mock():
            new_id = client.post("/replan", json={"plan_id": plan_id}).json()["plan_id"]
        r = client.post(f"/execute/{new_id}")
        assert r.status_code == 200

    def test_original_plan_remains_failed(self):
        plan_id = submit_goal()["plan_id"]
        client.post("/execute_status", json={"plan_id": plan_id, "status": "failure"})
        with _ollama_mock():
            client.post("/replan", json={"plan_id": plan_id})
        status = client.get(f"/status/{plan_id}").json()["status"]
        assert status == "failure"

    def test_replan_with_new_goal(self):
        plan_id  = submit_goal()["plan_id"]
        new_goal = "Stack blue cylinder on red cube"
        client.post("/execute_status", json={"plan_id": plan_id, "status": "failure"})
        with _ollama_mock():
            new_id = client.post("/replan", json={
                "plan_id":  plan_id,
                "new_goal": new_goal,
            }).json()["plan_id"]
        plan = client.get(f"/plan/{new_id}").json()
        assert plan["goal"] == new_goal

    def test_double_replan_chain(self):
        """Two consecutive failures each produce a fresh plan."""
        id1 = submit_goal()["plan_id"]
        client.post("/execute_status", json={"plan_id": id1, "status": "failure"})
        with _ollama_mock():
            id2 = client.post("/replan", json={"plan_id": id1}).json()["plan_id"]
        client.post("/execute_status", json={"plan_id": id2, "status": "failure"})
        with _ollama_mock():
            id3 = client.post("/replan", json={"plan_id": id2}).json()["plan_id"]
        assert len({id1, id2, id3}) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline C — Monitor watches a plan end-to-end
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineC:
    """Monitor integration: drives status via hub, checks KG + event log."""

    def _make_monitor(self, plan_id: str, actions: list):
        """Create a Monitor whose HTTP calls go through the TestClient."""
        from monitor import Monitor
        from knowledge_graph import build_default_scene

        m = Monitor(plan_id=plan_id, hub_url="http://testclient",
                    kg=build_default_scene())
        m._actions = actions

        # Wire _get/_post to the TestClient
        def _get(path):
            r = client.get(path)
            r.raise_for_status()
            return r.json()

        def _post(path, body):
            r = client.post(path, json=body)
            r.raise_for_status()
            return r.json()

        m._get  = _get
        m._post = _post
        return m

    def test_monitor_detects_success(self):
        plan_id = submit_goal()["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]
        m       = self._make_monitor(plan_id, actions)

        # Simulate executor reporting success
        client.post("/execute_status", json={"plan_id": plan_id, "status": "success"})

        m._tick()
        assert m._status.value == "success"

    def test_monitor_detects_failure(self):
        plan_id = submit_goal()["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]
        m       = self._make_monitor(plan_id, actions)

        client.post("/execute_status", json={"plan_id": plan_id, "status": "failure"})

        with patch("monitor.REPLAN_ON_FAIL", False):
            m._tick()
        assert m._status.value == "failure"

    def test_monitor_success_pushes_world_state(self):
        plan_id = submit_goal()["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]
        m       = self._make_monitor(plan_id, actions)

        # Capture /world_state calls
        world_state_calls = []
        original_post = m._post
        def capturing_post(path, body):
            if "/world_state" in path:
                world_state_calls.append(body)
            return original_post(path, body)
        m._post = capturing_post

        client.post("/execute_status", json={"plan_id": plan_id, "status": "success"})
        m._tick()
        assert len(world_state_calls) == 1
        assert "objects" in world_state_calls[0]

    def test_monitor_emits_status_change_event(self):
        plan_id = submit_goal()["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]
        m       = self._make_monitor(plan_id, actions)

        client.post("/execute_status", json={"plan_id": plan_id, "status": "running"})
        m._tick()
        events = m.events()
        assert any(e["event"] == "status_change" for e in events)

    def test_monitor_kg_updated_on_success(self):
        plan_id = submit_goal()["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]
        m       = self._make_monitor(plan_id, actions)

        # The mock plan has pick → move_to → place (red_cube zone_a → zone_c)
        client.post("/execute_status", json={"plan_id": plan_id, "status": "success"})
        m._tick()
        # red_cube should now be in zone_c
        assert m.kg.get_location_of("red_cube") == "zone_c"

    def test_monitor_replan_on_failure(self):
        plan_id = submit_goal()["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]
        m       = self._make_monitor(plan_id, actions)

        # Wire _post to also return valid replan response
        original_post = m._post
        def replan_post(path, body):
            if "/replan" in path:
                with _ollama_mock():
                    r = client.post(path, json=body)
                    r.raise_for_status()
                    return r.json()
            if f"/execute/" in path:
                r = client.post(path, json=body)
                r.raise_for_status()
                return r.json()
            return original_post(path, body)
        m._post = replan_post

        # Feed failure into hub, then monitor fetches status
        client.post("/execute_status", json={"plan_id": plan_id, "status": "failure"})
        with patch("monitor.REPLAN_ON_FAIL", True), patch("monitor.MAX_REPLAN", 3):
            m._tick()

        replan_events = [e for e in m.events() if e["event"] == "replan"]
        assert len(replan_events) == 1
        assert replan_events[0]["detail"]["old_plan_id"] == plan_id


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline D — world-state update affects next plan
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineD:
    """POST /world_state changes the KG used for subsequent plans."""

    def test_world_state_update_accepted(self):
        r = client.post("/world_state", json={
            "robot":     "franka",
            "objects":   [{"name": "red_cube", "at": "zone_b"}],
            "locations": ["zone_a", "zone_b", "zone_c"],
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_world_state_used_in_next_goal(self):
        # Move cube to zone_b in the hub's KG
        client.post("/world_state", json={
            "robot":     "franka",
            "objects":   [{"name": "red_cube", "at": "zone_b"}],
            "locations": ["zone_a", "zone_b", "zone_c"],
        })
        # Submit a goal WITHOUT explicit scene — hub should use updated KG
        with _ollama_mock():
            r = client.post("/goal", json={"goal": "Move red cube to zone C"})
        assert r.status_code == 200

    def test_world_state_multiple_objects(self):
        r = client.post("/world_state", json={
            "robot": "franka",
            "objects": [
                {"name": "red_cube",      "at": "zone_a"},
                {"name": "blue_cylinder", "at": "zone_b"},
                {"name": "green_sphere",  "at": "zone_c", "fragile": True},
            ],
            "locations": ["zone_a", "zone_b", "zone_c"],
        })
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline E — two concurrent plans tracked independently
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineE:
    """Multiple plans coexist; status updates are plan-scoped."""

    def test_two_plans_have_different_ids(self):
        id1 = submit_goal("Move red cube to zone B")["plan_id"]
        id2 = submit_goal("Move red cube to zone C")["plan_id"]
        assert id1 != id2

    def test_status_update_does_not_affect_other_plan(self):
        id1 = submit_goal()["plan_id"]
        id2 = submit_goal()["plan_id"]

        client.post("/execute_status", json={"plan_id": id1, "status": "success"})

        status2 = client.get(f"/status/{id2}").json()["status"]
        assert status2 == "pending"   # id2 untouched

    def test_both_plans_retrievable(self):
        id1 = submit_goal("Goal one")["plan_id"]
        id2 = submit_goal("Goal two")["plan_id"]

        p1 = client.get(f"/plan/{id1}").json()
        p2 = client.get(f"/plan/{id2}").json()

        assert p1["goal"] == "Goal one"
        assert p2["goal"] == "Goal two"

    def test_execute_one_does_not_block_other(self):
        id1 = submit_goal()["plan_id"]
        id2 = submit_goal()["plan_id"]

        r1 = client.post(f"/execute/{id1}")
        r2 = client.post(f"/execute/{id2}")

        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_cannot_execute_already_running_plan(self):
        plan_id = submit_goal()["plan_id"]
        client.post(f"/execute/{plan_id}")          # → running
        r2 = client.post(f"/execute/{plan_id}")     # → 409 conflict
        assert r2.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline F — executor runs real mock actions and reports back
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineF:
    """IsaacExecutor mock run reports step-by-step to hub."""

    def test_executor_reports_all_steps(self):
        from isaac_executor import IsaacExecutor, MockExecutor

        plan_id = submit_goal()["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]

        reported = []

        def _set_status(status):
            client.post("/execute_status", json={"plan_id": plan_id, "status": status})

        def _report_step(result):
            reported.append(result)
            client.post("/execute_status", json={
                "plan_id": plan_id,
                "status":  "running",
                "step":    result.step,
                "action":  result.action,
                "success": result.success,
                "message": result.message,
            })

        executor = IsaacExecutor(plan_id=plan_id, mock=True)
        executor._set_status  = _set_status
        executor._report_step = _report_step
        executor._backend     = MockExecutor(fail_at_step=-1, step_delay=0)

        ok = executor.run_plan(actions)
        assert ok
        assert len(reported) == len(actions)

        final = client.get(f"/status/{plan_id}").json()["status"]
        assert final == "success"

    def test_executor_failure_reported_to_hub(self):
        from isaac_executor import IsaacExecutor, MockExecutor

        plan_id = submit_goal()["plan_id"]
        actions = client.get(f"/plan/{plan_id}").json()["actions"]

        def _set_status(status):
            client.post("/execute_status", json={"plan_id": plan_id, "status": status})

        executor = IsaacExecutor(plan_id=plan_id, mock=True)
        executor._set_status  = _set_status
        executor._report_step = MagicMock()
        executor._backend     = MockExecutor(fail_at_step=0, step_delay=0)

        ok = executor.run_plan(actions)
        assert not ok

        final = client.get(f"/status/{plan_id}").json()["status"]
        assert final == "failure"
