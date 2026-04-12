"""Tests for monitor.py — Agent 3."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "llm_agent", "src"))

import pytest
from unittest.mock import MagicMock, patch, call
from knowledge_graph import build_default_scene
from monitor import Monitor, PlanStatus, ExecutionEvent, MockMonitor


PLAN_ID = "aaaaaaaa-0000-0000-0000-000000000001"

MOCK_ACTIONS = [
    {"step": 0, "name": "pick(franka,red_cube,zone_a)",  "cost": 1.0},
    {"step": 1, "name": "move_to(franka,zone_a,zone_c)", "cost": 1.0},
    {"step": 2, "name": "place(franka,red_cube,zone_c)", "cost": 1.0},
]


def make_monitor(**kwargs) -> Monitor:
    m = Monitor(plan_id=PLAN_ID, hub_url="http://mock", **kwargs)
    m._actions = list(MOCK_ACTIONS)
    m._get  = MagicMock(return_value={"status": "pending", "actions": MOCK_ACTIONS})
    m._post = MagicMock(return_value={"status": "ok"})
    return m


# ── ExecutionEvent ─────────────────────────────────────────────────────────────

class TestExecutionEvent:
    def test_to_dict_keys(self):
        ev = ExecutionEvent(ts="t", plan_id="p", event="e", detail={"k": "v"})
        d  = ev.to_dict()
        assert set(d.keys()) == {"ts", "plan_id", "event", "detail"}

    def test_detail_preserved(self):
        ev = ExecutionEvent(ts="t", plan_id="p", event="e", detail={"x": 1})
        assert ev.to_dict()["detail"]["x"] == 1


# ── Monitor._emit ──────────────────────────────────────────────────────────────

class TestEmit:
    def test_event_appended(self):
        m = make_monitor()
        m._emit("test_event", {"a": 1})
        assert len(m._events) == 1
        assert m._events[0].event == "test_event"

    def test_on_event_callback_called(self):
        cb = MagicMock()
        m  = make_monitor(on_event=cb)
        m._emit("test_event", {})
        cb.assert_called_once()

    def test_multiple_events(self):
        m = make_monitor()
        m._emit("e1", {})
        m._emit("e2", {})
        assert len(m._events) == 2

    def test_events_method_returns_dicts(self):
        m = make_monitor()
        m._emit("e1", {"k": "v"})
        evs = m.events()
        assert isinstance(evs[0], dict)
        assert evs[0]["event"] == "e1"


# ── Status transitions ─────────────────────────────────────────────────────────

class TestStatusTransitions:
    def test_initial_status_pending(self):
        m = make_monitor()
        assert m._status == PlanStatus.PENDING

    def test_running_transition(self):
        m = make_monitor()
        m._on_status_change(PlanStatus.RUNNING)
        assert m._status == PlanStatus.RUNNING

    def test_success_stops_monitor(self):
        m = make_monitor()
        m._push_world_state = MagicMock()
        m._running = True
        m._on_status_change(PlanStatus.SUCCESS)
        assert not m._running

    def test_failure_stops_monitor_when_replan_disabled(self):
        with patch("monitor.REPLAN_ON_FAIL", False):
            m = make_monitor()
            m._running = True
            m._on_status_change(PlanStatus.FAILURE)
            assert not m._running

    def test_status_change_emits_event(self):
        m = make_monitor()
        m._push_world_state = MagicMock()
        m._on_status_change(PlanStatus.SUCCESS)
        events = [e.event for e in m._events]
        assert "status_change" in events

    def test_status_change_event_has_from_to(self):
        m = make_monitor()
        m._push_world_state = MagicMock()
        m._on_status_change(PlanStatus.RUNNING)
        ev = next(e for e in m._events if e.event == "status_change")
        assert ev.detail["from"] == "pending"
        assert ev.detail["to"]   == "running"


# ── KG updates ────────────────────────────────────────────────────────────────

class TestKgUpdates:
    def test_pick_removes_location(self):
        kg = build_default_scene()
        m  = make_monitor(kg=kg)
        m._apply_action_to_kg("pick(franka,red_cube,zone_a)")
        assert kg.get_location_of("red_cube") is None

    def test_place_sets_location(self):
        kg = build_default_scene()
        m  = make_monitor(kg=kg)
        m._apply_action_to_kg("pick(franka,red_cube,zone_a)")
        m._apply_action_to_kg("place(franka,red_cube,zone_c)")
        assert kg.get_location_of("red_cube") == "zone_c"

    def test_invalid_action_doesnt_raise(self):
        m = make_monitor()
        m._apply_action_to_kg("teleport(franka,mars)")   # unknown action, no crash

    def test_push_world_state_calls_hub(self):
        m = make_monitor()
        m._push_world_state()
        m._post.assert_called()
        call_path = m._post.call_args[0][0]
        assert "/world_state" in call_path

    def test_push_world_state_includes_objects(self):
        m = make_monitor()
        m._push_world_state()
        body = m._post.call_args[0][1]
        assert "objects" in body
        assert "locations" in body
        assert "robot" in body


# ── Failure + replan ──────────────────────────────────────────────────────────

class TestReplan:
    def _make_replan_monitor(self) -> Monitor:
        m = make_monitor()
        m._running = True
        new_plan_resp = {"plan_id": "bbbbbbbb-0000-0000-0000-000000000002",
                         "steps": 3, "cost": 3.0}
        m._post = MagicMock(return_value=new_plan_resp)
        m._get  = MagicMock(return_value={
            "status": "pending",
            "actions": MOCK_ACTIONS,
        })
        return m

    def test_replan_increments_counter(self):
        with patch("monitor.REPLAN_ON_FAIL", True), patch("monitor.MAX_REPLAN", 3):
            m = self._make_replan_monitor()
            m._on_failure()
            assert m._replan_count == 1

    def test_replan_changes_plan_id(self):
        with patch("monitor.REPLAN_ON_FAIL", True), patch("monitor.MAX_REPLAN", 3):
            m = self._make_replan_monitor()
            old_id = m.plan_id
            m._on_failure()
            assert m.plan_id != old_id

    def test_replan_restarts_running(self):
        with patch("monitor.REPLAN_ON_FAIL", True), patch("monitor.MAX_REPLAN", 3):
            m = self._make_replan_monitor()
            m._on_failure()
            assert m._running

    def test_max_replan_stops_monitor(self):
        with patch("monitor.REPLAN_ON_FAIL", True), patch("monitor.MAX_REPLAN", 1):
            m = self._make_replan_monitor()
            m._replan_count = 1   # already at max
            m._on_failure()
            assert not m._running

    def test_replan_emits_event(self):
        with patch("monitor.REPLAN_ON_FAIL", True), patch("monitor.MAX_REPLAN", 3):
            m = self._make_replan_monitor()
            m._on_failure()
            events = [e.event for e in m._events]
            assert "replan" in events

    def test_replan_event_has_old_and_new_id(self):
        with patch("monitor.REPLAN_ON_FAIL", True), patch("monitor.MAX_REPLAN", 3):
            m  = self._make_replan_monitor()
            old_id = m.plan_id
            m._on_failure()
            ev = next(e for e in m._events if e.event == "replan")
            assert ev.detail["old_plan_id"] == old_id
            assert "new_plan_id" in ev.detail

    def test_no_replan_when_disabled(self):
        with patch("monitor.REPLAN_ON_FAIL", False):
            m = make_monitor()
            m._running = True
            m._on_failure()
            assert m._replan_count == 0
            assert not m._running


# ── _tick ──────────────────────────────────────────────────────────────────────

class TestTick:
    def test_tick_detects_running(self):
        m = make_monitor()
        m._get = MagicMock(return_value={"status": "running"})
        m._tick()
        assert m._status == PlanStatus.RUNNING

    def test_tick_detects_success(self):
        m = make_monitor()
        m._push_world_state = MagicMock()
        m._get = MagicMock(return_value={"status": "success"})
        m._tick()
        assert m._status == PlanStatus.SUCCESS

    def test_tick_no_change_no_event(self):
        m = make_monitor()
        m._status = PlanStatus.RUNNING
        m._get    = MagicMock(return_value={"status": "running"})
        m._tick()
        assert len(m._events) == 0   # no change → no event


# ── MockMonitor ────────────────────────────────────────────────────────────────

class TestMockMonitor:
    def test_success_run_returns_events(self):
        driver = MockMonitor(fail_at_step=-1)
        events = driver.run()
        assert len(events) > 0

    def test_success_run_has_success_event(self):
        driver = MockMonitor(fail_at_step=-1)
        events = driver.run()
        types  = [e["event"] for e in events]
        assert "status_change" in types

    def test_success_run_kg_updated(self):
        driver = MockMonitor(fail_at_step=-1)
        driver.run()
        # red_cube should have moved to zone_c after pick+move+place
        assert driver._kg.get_location_of("red_cube") == "zone_c"

    def test_failure_injection_returns_events(self):
        driver = MockMonitor(fail_at_step=1)
        events = driver.run()
        assert any(e["event"] == "step_failed" for e in events)

    def test_failure_injection_early_exit(self):
        driver = MockMonitor(fail_at_step=0)
        events = driver.run()
        # Should stop at step 0, not reach step 2
        assert any(e["event"] == "step_failed" for e in events)
