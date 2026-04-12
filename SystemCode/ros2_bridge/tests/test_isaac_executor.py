"""Tests for isaac_executor.py — Agent 4 mock execution and action parsing."""

import os
import sys

os.environ["MOCK_ISAAC"] = "1"
os.environ["MOCK_PLANNER"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "llm_agent", "src"))

import pytest
from unittest.mock import patch

from isaac_executor import (
    ParsedAction,
    ActionType,
    MockExecutor,
    IsaacExecutor,
    StepResult,
)


# ── ParsedAction ──────────────────────────────────────────────────────────────

class TestParsedAction:
    def test_parse_pick(self):
        a = ParsedAction.parse("pick(franka,red_cube,zone_a)")
        assert a.atype == ActionType.PICK
        assert a.robot == "franka"
        assert a.obj   == "red_cube"
        assert a.loc   == "zone_a"

    def test_parse_place(self):
        a = ParsedAction.parse("place(franka,red_cube,zone_c)")
        assert a.atype == ActionType.PLACE
        assert a.obj   == "red_cube"
        assert a.loc   == "zone_c"

    def test_parse_move_to(self):
        a = ParsedAction.parse("move_to(franka,zone_a,zone_c)")
        assert a.atype    == ActionType.MOVE_TO
        assert a.from_loc == "zone_a"
        assert a.loc      == "zone_c"

    def test_parse_stack(self):
        a = ParsedAction.parse("stack(franka,red_cube,blue_cylinder,zone_b)")
        assert a.atype      == ActionType.STACK
        assert a.obj        == "red_cube"
        assert a.obj_bottom == "blue_cylinder"
        assert a.loc        == "zone_b"

    def test_parse_unstack(self):
        a = ParsedAction.parse("unstack(franka,red_cube,blue_cylinder,zone_b)")
        assert a.atype      == ActionType.UNSTACK
        assert a.obj        == "red_cube"
        assert a.obj_bottom == "blue_cylinder"

    def test_parse_unknown(self):
        a = ParsedAction.parse("teleport(franka,zone_x)")
        assert a.atype == ActionType.UNKNOWN

    def test_parse_malformed(self):
        a = ParsedAction.parse("not_an_action")
        assert a.atype == ActionType.UNKNOWN

    def test_raw_preserved(self):
        raw = "pick(franka,red_cube,zone_a)"
        a = ParsedAction.parse(raw)
        assert a.raw == raw


# ── MockExecutor ──────────────────────────────────────────────────────────────

class TestMockExecutor:
    def test_pick_succeeds(self):
        ex = MockExecutor(fail_at_step=-1, step_delay=0)
        a  = ParsedAction.parse("pick(franka,red_cube,zone_a)")
        r  = ex.execute_step(0, a)
        assert r.success
        assert r.step == 0

    def test_place_succeeds(self):
        ex = MockExecutor(fail_at_step=-1, step_delay=0)
        a  = ParsedAction.parse("place(franka,red_cube,zone_c)")
        r  = ex.execute_step(1, a)
        assert r.success

    def test_move_to_succeeds(self):
        ex = MockExecutor(fail_at_step=-1, step_delay=0)
        a  = ParsedAction.parse("move_to(franka,zone_a,zone_c)")
        r  = ex.execute_step(0, a)
        assert r.success

    def test_stack_succeeds(self):
        ex = MockExecutor(fail_at_step=-1, step_delay=0)
        a  = ParsedAction.parse("stack(franka,red_cube,blue_cylinder,zone_b)")
        r  = ex.execute_step(2, a)
        assert r.success

    def test_unstack_succeeds(self):
        ex = MockExecutor(fail_at_step=-1, step_delay=0)
        a  = ParsedAction.parse("unstack(franka,red_cube,blue_cylinder,zone_b)")
        r  = ex.execute_step(0, a)
        assert r.success

    def test_failure_injection(self):
        ex = MockExecutor(fail_at_step=1, step_delay=0)
        a  = ParsedAction.parse("pick(franka,red_cube,zone_a)")
        r0 = ex.execute_step(0, a)
        r1 = ex.execute_step(1, a)
        assert r0.success
        assert not r1.success
        assert "Injected" in r1.message

    def test_message_contains_action_info(self):
        ex = MockExecutor(fail_at_step=-1, step_delay=0)
        a  = ParsedAction.parse("pick(franka,red_cube,zone_a)")
        r  = ex.execute_step(0, a)
        assert "red_cube" in r.message or "Grasped" in r.message


# ── IsaacExecutor (mock backend) ──────────────────────────────────────────────

SAMPLE_PLAN = [
    {"step": 0, "name": "pick(franka,red_cube,zone_a)",  "cost": 1.0},
    {"step": 1, "name": "move_to(franka,zone_a,zone_c)", "cost": 1.0},
    {"step": 2, "name": "place(franka,red_cube,zone_c)", "cost": 1.0},
]


class TestIsaacExecutor:
    def test_run_plan_success(self):
        executor = IsaacExecutor(
            plan_id="test-plan-1",
            mock=True,
        )
        # Suppress HTTP calls to hub
        with patch.object(executor, "_set_status"), \
             patch.object(executor, "_report_step"):
            ok = executor.run_plan(SAMPLE_PLAN)
        assert ok

    def test_run_plan_failure_injection(self):
        executor = IsaacExecutor(plan_id="test-plan-2", mock=True)
        executor._backend = MockExecutor(fail_at_step=1, step_delay=0)
        with patch.object(executor, "_set_status"), \
             patch.object(executor, "_report_step"):
            ok = executor.run_plan(SAMPLE_PLAN)
        assert not ok

    def test_on_step_callback_called(self):
        results: list[StepResult] = []
        executor = IsaacExecutor(
            plan_id="test-plan-3",
            mock=True,
            on_step=results.append,
        )
        with patch.object(executor, "_set_status"), \
             patch.object(executor, "_report_step"):
            executor.run_plan(SAMPLE_PLAN)
        assert len(results) == len(SAMPLE_PLAN)

    def test_all_steps_reported(self):
        reported: list[StepResult] = []
        executor = IsaacExecutor(plan_id="test-plan-4", mock=True)
        with patch.object(executor, "_set_status"), \
             patch.object(executor, "_report_step",
                          side_effect=lambda r: reported.append(r)):
            executor.run_plan(SAMPLE_PLAN)
        assert len(reported) == len(SAMPLE_PLAN)

    def test_status_set_running_then_success(self):
        statuses: list[str] = []
        executor = IsaacExecutor(plan_id="test-plan-5", mock=True)
        with patch.object(executor, "_set_status",
                          side_effect=lambda s: statuses.append(s)), \
             patch.object(executor, "_report_step"):
            executor.run_plan(SAMPLE_PLAN)
        assert statuses[0]  == "running"
        assert statuses[-1] == "success"

    def test_status_set_failure_on_error(self):
        statuses: list[str] = []
        executor = IsaacExecutor(plan_id="test-plan-6", mock=True)
        executor._backend = MockExecutor(fail_at_step=0, step_delay=0)
        with patch.object(executor, "_set_status",
                          side_effect=lambda s: statuses.append(s)), \
             patch.object(executor, "_report_step"):
            executor.run_plan(SAMPLE_PLAN)
        assert "failure" in statuses

    def test_empty_plan_succeeds(self):
        executor = IsaacExecutor(plan_id="test-plan-7", mock=True)
        with patch.object(executor, "_set_status"), \
             patch.object(executor, "_report_step"):
            ok = executor.run_plan([])
        assert ok
