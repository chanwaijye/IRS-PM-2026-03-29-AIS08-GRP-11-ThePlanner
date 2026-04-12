"""monitor.py — Agent 3: Execution Monitor for ThePlanner.

Responsibilities
----------------
1. Poll the agent hub for plan execution status.
2. Receive per-step execution events (via GET /execution_log or polling).
3. Update the scene Knowledge Graph after each successful action.
4. Detect failures and trigger /replan automatically.
5. Emit a structured event log for observability.

Two runtime modes (MOCK_MONITOR env var):
  MOCK_MONITOR=1  Drives a synthetic plan through the mock executor locally.
  MOCK_MONITOR=0  Connects to a live hub at HUB_URL.

Usage
-----
  # Watch a specific plan (live hub):
  python3 monitor.py --plan-id <uuid>

  # Self-contained demo (no hub required):
  MOCK_MONITOR=1 python3 monitor.py

Architecture
------------
  agent_hub
      │  GET /status/{id}        (polling loop)
      │  GET /plan/{id}          (fetch actions on start)
      │  POST /world_state       (KG update after each step)
      │  POST /replan            (on failure)
      ▼
  Monitor
      │  apply_action()          (update local KG per step)
      │  _on_failure()           (trigger replan)
      └─ event log (stdout + rotating file)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import requests

# Local KG (for local state tracking; not strictly required for hub-only mode)
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "llm_agent", "src"))
from knowledge_graph import SceneKnowledgeGraph, build_default_scene

# ── Config ─────────────────────────────────────────────────────────────────────

HUB_URL         = os.environ.get("HUB_URL",       "http://localhost:8000")
POLL_INTERVAL   = float(os.environ.get("POLL_INTERVAL",  "1.0"))   # seconds
REPLAN_ON_FAIL  = os.environ.get("REPLAN_ON_FAIL", "1") == "1"
MAX_REPLAN      = int(os.environ.get("MAX_REPLAN", "3"))
MOCK_MONITOR    = os.environ.get("MOCK_MONITOR",   "0") == "1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("monitor")


# ── Data types ─────────────────────────────────────────────────────────────────

class PlanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class ExecutionEvent:
    ts:       str
    plan_id:  str
    event:    str           # status_change | step_done | step_failed | replan
    detail:   dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"ts": self.ts, "plan_id": self.plan_id,
                "event": self.event, "detail": self.detail}


# ── Monitor ────────────────────────────────────────────────────────────────────

class Monitor:
    """Watches one plan and manages the KG + replan loop.

    Args:
        plan_id:    Hub plan ID to watch.
        hub_url:    Base URL of the agent hub.
        kg:         Initial scene knowledge graph (used for local KG updates).
        on_event:   Optional callback(ExecutionEvent) for each monitor event.
    """

    def __init__(
        self,
        plan_id:  str,
        hub_url:  str = HUB_URL,
        kg:       SceneKnowledgeGraph | None = None,
        on_event: Any = None,
    ) -> None:
        self.plan_id     = plan_id
        self.hub_url     = hub_url.rstrip("/")
        self.kg          = kg or build_default_scene()
        self.on_event    = on_event
        self._status     = PlanStatus.PENDING
        self._actions:   list[dict] = []
        self._completed: set[int]   = set()
        self._replan_count = 0
        self._running    = False
        self._events:    list[ExecutionEvent] = []

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self, poll_interval: float = POLL_INTERVAL) -> None:
        """Block and poll until the plan reaches a terminal state."""
        log.info("Monitor started for plan %s", self.plan_id[:8])
        self._running = True
        self._fetch_plan()

        while self._running:
            try:
                self._tick()
            except KeyboardInterrupt:
                log.info("Monitor interrupted.")
                break
            except Exception as exc:
                log.warning("Poll error: %s", exc)

            time.sleep(poll_interval)

    def stop(self) -> None:
        self._running = False

    def events(self) -> list[dict]:
        return [e.to_dict() for e in self._events]

    # ── Internal ───────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        status_data = self._get(f"/status/{self.plan_id}")
        new_status  = PlanStatus(status_data.get("status", "pending"))

        if new_status != self._status:
            self._on_status_change(new_status)

        if new_status in (PlanStatus.SUCCESS, PlanStatus.FAILURE):
            self._running = False

    def _on_status_change(self, new_status: PlanStatus) -> None:
        prev = self._status
        self._status = new_status
        log.info("Plan %s: %s → %s", self.plan_id[:8], prev.value, new_status.value)

        ev = self._emit("status_change", {"from": prev.value, "to": new_status.value})

        if new_status == PlanStatus.RUNNING:
            self._on_running()
        elif new_status == PlanStatus.SUCCESS:
            self._on_success()
        elif new_status == PlanStatus.FAILURE:
            self._on_failure()

    def _on_running(self) -> None:
        log.info("Execution in progress — tracking %d actions", len(self._actions))

    def _on_success(self) -> None:
        log.info("Plan %s completed successfully.", self.plan_id[:8])
        # Apply all remaining actions to KG to ensure final state is consistent
        for action in self._actions:
            step = action.get("step", 0)
            if step not in self._completed:
                self._apply_action_to_kg(action.get("name", ""))
                self._completed.add(step)
        self._push_world_state()
        self._emit("step_done", {"step": "all", "final": True})
        self._running = False

    def _on_failure(self) -> None:
        log.warning("Plan %s failed.", self.plan_id[:8])
        self._emit("step_failed", {"plan_id": self.plan_id})

        if REPLAN_ON_FAIL and self._replan_count < MAX_REPLAN:
            self._trigger_replan()
        else:
            if self._replan_count >= MAX_REPLAN:
                log.error("Max replan attempts (%d) reached. Giving up.", MAX_REPLAN)
            self._running = False

    def _trigger_replan(self) -> None:
        self._replan_count += 1
        log.info("Triggering replan (attempt %d/%d)…", self._replan_count, MAX_REPLAN)
        try:
            resp = self._post("/replan", {"plan_id": self.plan_id})
            new_id = resp.get("plan_id")
            if not new_id:
                log.error("Replan returned no plan_id.")
                self._running = False
                return

            # Execute the new plan
            self._post(f"/execute/{new_id}", {})
            log.info("Replanned → %s, executing.", new_id[:8])
            self._emit("replan", {
                "attempt": self._replan_count,
                "old_plan_id": self.plan_id,
                "new_plan_id": new_id,
            })

            # Switch watch target to new plan
            self.plan_id = new_id
            self._status = PlanStatus.PENDING
            self._completed.clear()
            self._fetch_plan()
            self._running = True

        except Exception as exc:
            log.error("Replan failed: %s", exc)
            self._running = False

    # ── KG management ──────────────────────────────────────────────────────────

    def _apply_action_to_kg(self, action_name: str) -> None:
        """Update local KG after a completed action."""
        try:
            self.kg.apply_action(action_name)
            log.debug("KG updated: %s", action_name)
        except Exception as exc:
            log.debug("KG update skipped (%s): %s", action_name, exc)

    def _push_world_state(self) -> None:
        """Push current KG state to hub /world_state."""
        try:
            ctx = self.kg.to_scene_context()
            self._post("/world_state", {
                "robot":     ctx["robot"],
                "objects":   ctx["objects"],
                "locations": ctx["locations"],
            })
            log.info("World state pushed to hub (%d objects).", len(ctx["objects"]))
        except Exception as exc:
            log.warning("Failed to push world state: %s", exc)

    # ── Hub helpers ────────────────────────────────────────────────────────────

    def _fetch_plan(self) -> None:
        try:
            data = self._get(f"/plan/{self.plan_id}")
            self._actions = data.get("actions", [])
            log.info("Fetched plan: %d actions", len(self._actions))
        except Exception as exc:
            log.warning("Could not fetch plan: %s", exc)

    def _get(self, path: str) -> dict:
        r = requests.get(f"{self.hub_url}{path}", timeout=5)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        r = requests.post(f"{self.hub_url}{path}", json=body, timeout=5)
        r.raise_for_status()
        return r.json()

    # ── Event log ──────────────────────────────────────────────────────────────

    def _emit(self, event: str, detail: dict) -> ExecutionEvent:
        ev = ExecutionEvent(
            ts=datetime.now(timezone.utc).isoformat(),
            plan_id=self.plan_id,
            event=event,
            detail=detail,
        )
        self._events.append(ev)
        if self.on_event:
            self.on_event(ev)
        return ev


# ── Mock driver (self-contained demo) ─────────────────────────────────────────

class MockMonitor:
    """Drives a full plan locally without a running hub.

    Useful for demos and CI.  Simulates:
      pending → running → (optional failure + replan) → success
    """

    def __init__(self, fail_at_step: int = -1, replan: bool = True) -> None:
        self._fail_at = fail_at_step
        self._replan  = replan
        self._kg      = build_default_scene()

    def run(self) -> list[dict]:
        """Return the event log after a simulated run."""
        import uuid
        from unittest.mock import MagicMock

        plan_id  = str(uuid.uuid4())
        events:  list[dict] = []

        def record(ev: ExecutionEvent) -> None:
            events.append(ev.to_dict())
            print(f"  [{ev.event}] {ev.detail}")

        MOCK_ACTIONS = [
            {"step": 0, "name": "pick(franka,red_cube,zone_a)",  "cost": 1.0},
            {"step": 1, "name": "move_to(franka,zone_a,zone_c)", "cost": 1.0},
            {"step": 2, "name": "place(franka,red_cube,zone_c)", "cost": 1.0},
        ]

        m = Monitor(plan_id=plan_id, hub_url="http://mock", kg=self._kg,
                    on_event=record)
        m._actions = MOCK_ACTIONS
        m._running = True

        # Simulate status transitions
        print(f"\n[mock] Plan {plan_id[:8]}… — {len(MOCK_ACTIONS)} actions")

        m._on_status_change(PlanStatus.RUNNING)

        for action in MOCK_ACTIONS:
            step = action["step"]
            if step == self._fail_at:
                print(f"  [mock] step {step} FAILED")
                m._apply_action_to_kg(action["name"])  # partial apply
                # Suppress real HTTP call
                m._post   = MagicMock(return_value={"plan_id": str(uuid.uuid4()), "steps": 3, "cost": 3.0})
                m._get    = MagicMock(return_value={"plan_id": plan_id, "actions": MOCK_ACTIONS, "status": "failure"})
                m._on_status_change(PlanStatus.FAILURE)
                return events
            else:
                print(f"  [mock] step {step}: {action['name']} ✓")
                m._apply_action_to_kg(action["name"])
                m._completed.add(step)

        # Suppress real HTTP push
        m._push_world_state = MagicMock()
        m._on_status_change(PlanStatus.SUCCESS)
        return events


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ThePlanner Monitor Agent")
    parser.add_argument("--plan-id",       help="Plan ID to watch")
    parser.add_argument("--hub-url",       default=HUB_URL)
    parser.add_argument("--poll-interval", type=float, default=POLL_INTERVAL)
    parser.add_argument("--no-replan",     action="store_true")
    parser.add_argument("--log-file",      help="Append JSON events to file")
    args = parser.parse_args()

    if MOCK_MONITOR:
        print("=== Mock Monitor Demo ===")
        driver = MockMonitor(fail_at_step=-1)
        events = driver.run()
        print(f"\n{len(events)} events recorded.")
        if args.log_file:
            _write_log(args.log_file, events)
        return

    if not args.plan_id:
        parser.error("--plan-id is required (or set MOCK_MONITOR=1 for demo)")

    if args.no_replan:
        os.environ["REPLAN_ON_FAIL"] = "0"

    event_log: list[dict] = []

    def record(ev: ExecutionEvent) -> None:
        event_log.append(ev.to_dict())

    monitor = Monitor(
        plan_id=args.plan_id,
        hub_url=args.hub_url,
        on_event=record,
    )
    monitor.start(poll_interval=args.poll_interval)

    log.info("Final status: %s", monitor._status.value)
    log.info("Events recorded: %d", len(event_log))

    if args.log_file:
        _write_log(args.log_file, event_log)
        log.info("Events written to %s", args.log_file)


def _write_log(path: str, events: list[dict]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


if __name__ == "__main__":
    main()
