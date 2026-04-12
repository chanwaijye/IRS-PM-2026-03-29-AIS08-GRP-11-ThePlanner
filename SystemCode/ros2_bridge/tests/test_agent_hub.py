"""Integration tests for agent_hub.py FastAPI endpoints.

Runs with MOCK_PLANNER=1 so no planner binary is required.
LLM calls are also mocked to avoid needing Ollama.
"""

import os
import sys

# Force mock planner before importing app
os.environ["MOCK_PLANNER"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "llm_agent", "src"))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Patch LLM before importing agent_hub so Ollama is never called
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

with patch("nl_to_pddl.requests.post") as _mock_post:
    _mock_resp = MagicMock()
    _mock_resp.raise_for_status.return_value = None
    _mock_resp.json.return_value = {"response": MOCK_PDDL}
    _mock_post.return_value = _mock_resp
    from agent_hub import app, _store, PlanStatus

client = TestClient(app)

SIMPLE_SCENE = {
    "robot": "franka",
    "objects": [{"name": "red_cube", "type": "object", "at": "zone_a"}],
    "locations": ["zone_a", "zone_b", "zone_c"],
}


# ── Helper ────────────────────────────────────────────────────────────────────

def post_goal(goal="Move red cube to zone C", scene=None):
    payload = {"goal": goal}
    if scene is not None:
        payload["scene_context"] = scene
    with patch("nl_to_pddl.requests.post") as mp:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"response": MOCK_PDDL}
        mp.return_value = mock_resp
        return client.post("/goal", json=payload)


# ── POST /goal ────────────────────────────────────────────────────────────────

class TestPostGoal:
    def test_returns_200(self):
        r = post_goal()
        assert r.status_code == 200

    def test_response_has_plan_id(self):
        r = post_goal()
        assert "plan_id" in r.json()

    def test_response_has_steps(self):
        r = post_goal()
        data = r.json()
        assert "steps" in data
        assert data["steps"] > 0

    def test_response_has_cost(self):
        r = post_goal()
        assert "cost" in r.json()

    def test_with_explicit_scene(self):
        r = post_goal(scene=SIMPLE_SCENE)
        assert r.status_code == 200

    def test_plan_id_is_uuid(self):
        import uuid
        r = post_goal()
        plan_id = r.json()["plan_id"]
        uuid.UUID(plan_id)  # raises if not valid UUID

    def test_different_goals_get_different_plan_ids(self):
        r1 = post_goal("Move red cube to zone B")
        r2 = post_goal("Move red cube to zone C")
        assert r1.json()["plan_id"] != r2.json()["plan_id"]


# ── GET /plan/{id} ────────────────────────────────────────────────────────────

class TestGetPlan:
    def test_retrieve_plan_by_id(self):
        r = post_goal()
        plan_id = r.json()["plan_id"]
        r2 = client.get(f"/plan/{plan_id}")
        assert r2.status_code == 200

    def test_plan_response_has_actions(self):
        r = post_goal()
        plan_id = r.json()["plan_id"]
        r2 = client.get(f"/plan/{plan_id}")
        data = r2.json()
        assert "actions" in data
        assert isinstance(data["actions"], list)

    def test_plan_response_has_goal(self):
        r = post_goal("Move red cube to zone C")
        plan_id = r.json()["plan_id"]
        r2 = client.get(f"/plan/{plan_id}")
        assert r2.json()["goal"] == "Move red cube to zone C"

    def test_plan_response_has_status(self):
        r = post_goal()
        plan_id = r.json()["plan_id"]
        r2 = client.get(f"/plan/{plan_id}")
        assert "status" in r2.json()

    def test_unknown_plan_id_returns_404(self):
        r = client.get("/plan/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_actions_have_name_and_step(self):
        r = post_goal()
        plan_id = r.json()["plan_id"]
        r2 = client.get(f"/plan/{plan_id}")
        actions = r2.json()["actions"]
        assert len(actions) > 0
        for action in actions:
            assert "name" in action
            assert "step" in action


# ── GET /status/{id} ─────────────────────────────────────────────────────────

class TestGetStatus:
    def test_returns_200(self):
        r = post_goal()
        plan_id = r.json()["plan_id"]
        r2 = client.get(f"/status/{plan_id}")
        assert r2.status_code == 200

    def test_status_field_present(self):
        r = post_goal()
        plan_id = r.json()["plan_id"]
        r2 = client.get(f"/status/{plan_id}")
        assert "status" in r2.json()

    def test_initial_status_is_pending(self):
        r = post_goal()
        plan_id = r.json()["plan_id"]
        r2 = client.get(f"/status/{plan_id}")
        assert r2.json()["status"] == PlanStatus.PENDING.value

    def test_unknown_id_returns_404(self):
        r = client.get("/status/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ── POST /world_state ─────────────────────────────────────────────────────────

class TestPostWorldState:
    def test_returns_200(self):
        payload = {
            "robot": "franka",
            "objects": [{"name": "red_cube", "at": "zone_b"}],
            "locations": ["zone_a", "zone_b", "zone_c"],
        }
        r = client.post("/world_state", json=payload)
        assert r.status_code == 200

    def test_returns_ok_status(self):
        payload = {
            "robot": "franka",
            "objects": [{"name": "red_cube", "at": "zone_b"}],
            "locations": ["zone_a", "zone_b", "zone_c"],
        }
        r = client.post("/world_state", json=payload)
        assert r.json()["status"] == "ok"

    def test_world_state_affects_subsequent_goal(self):
        # Update world to move cube to zone_b
        client.post("/world_state", json={
            "robot": "franka",
            "objects": [{"name": "red_cube", "at": "zone_b"}],
            "locations": ["zone_a", "zone_b", "zone_c"],
        })
        # Next /goal call uses updated KG (no explicit scene)
        r = post_goal("Move red cube to zone C")
        assert r.status_code == 200


# ── POST /replan ──────────────────────────────────────────────────────────────

class TestPostReplan:
    def test_replan_returns_new_plan_id(self):
        r1 = post_goal()
        old_id = r1.json()["plan_id"]
        with patch("nl_to_pddl.requests.post") as mp:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"response": MOCK_PDDL}
            mp.return_value = mock_resp
            r2 = client.post("/replan", json={"plan_id": old_id})
        assert r2.status_code == 200
        assert r2.json()["plan_id"] != old_id

    def test_replan_with_new_goal(self):
        r1 = post_goal()
        old_id = r1.json()["plan_id"]
        with patch("nl_to_pddl.requests.post") as mp:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"response": MOCK_PDDL}
            mp.return_value = mock_resp
            r2 = client.post("/replan", json={
                "plan_id": old_id,
                "new_goal": "Stack blue cylinder on red cube"
            })
        assert r2.status_code == 200

    def test_replan_unknown_id_returns_404(self):
        r = client.post("/replan", json={
            "plan_id": "00000000-0000-0000-0000-000000000000"
        })
        assert r.status_code == 404
