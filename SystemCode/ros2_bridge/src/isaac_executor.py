"""isaac_executor.py — Agent 4: Execute a JSON plan on Isaac Sim 5.1.

Two runtime modes controlled by the MOCK_ISAAC environment variable:

  MOCK_ISAAC=1  (default)
      Simulates execution locally — no Isaac Sim required.
      Each action sleeps for a configurable duration and reports success.
      Set MOCK_FAIL_STEP=N to inject a failure at step N (0-indexed).

  MOCK_ISAAC=0
      Calls the real Isaac Sim 5.1 Python API.
      Must be invoked through Isaac Sim's own python.sh interpreter:
          ~/.local/share/ov/pkg/isaac-sim-5.1.0/python.sh isaac_executor.py

Architecture
------------
                 agent_hub
                     │  POST /execute/{plan_id}
                     ▼
           IsaacExecutor.run_plan(actions)
                     │
          ┌──────────┴──────────┐
          │                     │
    mock mode               real mode
   (simulate)           omni.isaac.franka
                         Franka controller
                         RMPflow motion planner
                         World.step() loop
          │                     │
          └──────────┬──────────┘
                     │  step callback
                     ▼
           HTTP POST → /world_state  (KG update)
           HTTP POST → /status       (running/success/failure)

Supported actions (matching tabletop.pddl):
  pick(robot, obj, loc)
  place(robot, obj, loc)
  stack(robot, obj_top, obj_bottom, loc)
  unstack(robot, obj_top, obj_bottom, loc)
  move_to(robot, from_loc, to_loc)
"""

from __future__ import annotations

import os
import re
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import requests

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

MOCK_ISAAC    = os.environ.get("MOCK_ISAAC", "1") == "1"
MOCK_FAIL_STEP = int(os.environ.get("MOCK_FAIL_STEP", "-1"))   # -1 = no injection
MOCK_STEP_DELAY = float(os.environ.get("MOCK_STEP_DELAY", "0.05"))  # seconds per step

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8000")

# ── Tabletop zone positions (metres, Isaac Sim world frame) ───────────────────
# Franka FR3 base at origin, table surface at z=0.77 m.
# Zones laid out along the x-axis in front of the robot.

ZONE_POSITIONS: dict[str, tuple[float, float, float]] = {
    "zone_a": (-0.35, 0.0, 0.77),
    "zone_b": ( 0.00, 0.0, 0.77),
    "zone_c": ( 0.35, 0.0, 0.77),
}

# Pre-grasp hover height above table surface
HOVER_Z_OFFSET = 0.12   # metres above object centre

# Franka FR3 joint configurations (radians)
# Home: arm folded safe, gripper open
JOINT_HOME = [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]


# ── Action parsing ────────────────────────────────────────────────────────────

class ActionType(str, Enum):
    PICK     = "pick"
    PLACE    = "place"
    STACK    = "stack"
    UNSTACK  = "unstack"
    MOVE_TO  = "move_to"
    UNKNOWN  = "unknown"


@dataclass
class ParsedAction:
    raw:    str
    atype:  ActionType
    args:   list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: str) -> "ParsedAction":
        m = re.match(r"(\w+)\(([^)]*)\)", raw.strip())
        if not m:
            return cls(raw=raw, atype=ActionType.UNKNOWN)
        name = m.group(1).lower()
        args = [a.strip() for a in m.group(2).split(",")]
        try:
            atype = ActionType(name)
        except ValueError:
            atype = ActionType.UNKNOWN
        return cls(raw=raw, atype=atype, args=args)

    @property
    def robot(self) -> str:
        return self.args[0] if self.args else "franka"

    @property
    def obj(self) -> str:
        return self.args[1] if len(self.args) > 1 else ""

    @property
    def loc(self) -> str:
        """Primary location argument (varies by action type)."""
        if self.atype == ActionType.PICK:
            return self.args[2] if len(self.args) > 2 else ""
        if self.atype == ActionType.PLACE:
            return self.args[2] if len(self.args) > 2 else ""
        if self.atype in (ActionType.STACK, ActionType.UNSTACK):
            return self.args[3] if len(self.args) > 3 else ""
        if self.atype == ActionType.MOVE_TO:
            return self.args[2] if len(self.args) > 2 else ""
        return ""

    @property
    def from_loc(self) -> str:
        return self.args[1] if self.atype == ActionType.MOVE_TO and len(self.args) > 1 else ""

    @property
    def obj_bottom(self) -> str:
        return self.args[2] if self.atype in (ActionType.STACK, ActionType.UNSTACK) and len(self.args) > 2 else ""


# ── Execution result ──────────────────────────────────────────────────────────

@dataclass
class StepResult:
    step:    int
    action:  str
    success: bool
    message: str = ""


# ── Mock executor ─────────────────────────────────────────────────────────────

class MockExecutor:
    """Simulates plan execution without Isaac Sim.

    Useful for CI, unit tests, and demos without a GPU.
    """

    def __init__(
        self,
        fail_at_step: int = MOCK_FAIL_STEP,
        step_delay:   float = MOCK_STEP_DELAY,
    ) -> None:
        self._fail_at = fail_at_step
        self._delay   = step_delay

    def execute_step(self, step: int, action: ParsedAction) -> StepResult:
        time.sleep(self._delay)

        if step == self._fail_at:
            return StepResult(
                step=step,
                action=action.raw,
                success=False,
                message=f"Injected failure at step {step}",
            )

        msg = self._describe(action)
        log.debug("[mock] step %d — %s", step, msg)
        return StepResult(step=step, action=action.raw, success=True, message=msg)

    @staticmethod
    def _describe(a: ParsedAction) -> str:
        if a.atype == ActionType.PICK:
            return f"Grasped {a.obj} at {a.loc}"
        if a.atype == ActionType.PLACE:
            return f"Placed {a.obj} at {a.loc}"
        if a.atype == ActionType.STACK:
            return f"Stacked {a.obj} on {a.obj_bottom}"
        if a.atype == ActionType.UNSTACK:
            return f"Unstacked {a.obj} from {a.obj_bottom}"
        if a.atype == ActionType.MOVE_TO:
            return f"Moved robot from {a.from_loc} to {a.loc}"
        return f"Executed {a.raw}"


# ── Real Isaac Sim executor ───────────────────────────────────────────────────

class IsaacSimExecutor:
    """Executes actions using Isaac Sim 5.1 Python API.

    Must be run inside Isaac Sim's python.sh interpreter.
    Initialises a headless World with a Franka FR3 and tabletop scene.
    Uses RMPflow for collision-aware motion planning.
    """

    def __init__(self, render: bool = True) -> None:
        self._world    = None
        self._robot    = None
        self._rmpflow  = None
        self._art_ctrl = None
        self._objects: dict[str, Any] = {}
        self._render   = render   # True = update GUI viewport each step
        self._init_sim()

    def _init_sim(self) -> None:
        # ── Isaac Sim 5.1 API (isaacsim.* namespace) ──────────────────────────
        # SimulationApp MUST be created before any other omni.* imports.
        # It is created in __main__ (GUI mode) or here for headless use.
        try:
            import numpy as np
            from isaacsim.core.api.world import World
            from isaacsim.robot.manipulators.examples.franka import Franka
            from isaacsim.core.api.objects import DynamicCuboid
            import isaacsim.robot_motion.motion_generation as mg
        except ImportError as e:
            raise RuntimeError(
                "Isaac Sim 5.1 Python API not available. "
                "Launch with:\n"
                "  ~/.local/share/ov/pkg/isaac-sim-5.1.0/python.sh isaac_executor.py\n"
                f"or set MOCK_ISAAC=1 for the software simulation. Error: {e}"
            )

        self._np = np

        self._world = World(stage_units_in_meters=1.0)

        # Ground plane
        self._world.scene.add_default_ground_plane()

        # Franka FR3 at origin
        self._robot = self._world.scene.add(
            Franka(prim_path="/World/Franka", name="franka")
        )

        # Tabletop objects
        colours = {
            "red_cube":      np.array([0.8, 0.1, 0.1]),
            "blue_cylinder": np.array([0.1, 0.1, 0.8]),
            "green_sphere":  np.array([0.1, 0.7, 0.1]),
        }
        initial_positions = {
            "red_cube":      np.array(ZONE_POSITIONS["zone_a"]),
            "blue_cylinder": np.array(ZONE_POSITIONS["zone_b"]),
            "green_sphere":  np.array(ZONE_POSITIONS["zone_c"]),
        }
        for obj_name, colour in colours.items():
            obj = self._world.scene.add(
                DynamicCuboid(
                    prim_path=f"/World/{obj_name}",
                    name=obj_name,
                    position=initial_positions[obj_name],
                    scale=np.array([0.05, 0.05, 0.05]),
                    color=colour,
                )
            )
            self._objects[obj_name] = obj

        self._world.reset()

        # RMPflow — Isaac Sim 5.1: load config by robot name, no manual paths needed
        rmpflow_cfg = mg.interface_config_loader.load_supported_motion_policy_config(
            "Franka", "RMPflow"
        )
        self._rmpflow = mg.lula.motion_policies.RmpFlow(**rmpflow_cfg)
        self._art_ctrl = mg.ArticulationMotionPolicy(
            self._robot, self._rmpflow, self._world.get_physics_dt()
        )
        # Anchor the planner to the robot's current world pose
        robot_pos, robot_ori = self._robot.get_world_pose()
        self._rmpflow.set_robot_base_pose(robot_pos, robot_ori)

    def _step_to_target(
        self,
        position: "np.ndarray",
        orientation: "np.ndarray | None" = None,
        max_steps: int = 500,
        tol: float = 0.01,
    ) -> bool:
        """Step the simulation until EEF reaches target position."""
        import numpy as np

        if orientation is None:
            orientation = np.array([1.0, 0.0, 0.0, 0.0])  # w,x,y,z upright

        self._rmpflow.set_end_effector_target(position, orientation)

        for _ in range(max_steps):
            self._art_ctrl.apply_action(
                self._rmpflow.get_next_articulation_action()
            )
            self._world.step(render=self._render)

            ee_pos, _ = self._robot.end_effector.get_world_pose()
            if np.linalg.norm(ee_pos - position) < tol:
                return True

        return False  # tol not reached within max_steps

    def _open_gripper(self, steps: int = 50) -> None:
        for _ in range(steps):
            self._robot.gripper.apply_action(
                self._robot.gripper.forward(action="open")
            )
            self._world.step(render=self._render)

    def _close_gripper(self, steps: int = 50) -> None:
        for _ in range(steps):
            self._robot.gripper.apply_action(
                self._robot.gripper.forward(action="close")
            )
            self._world.step(render=self._render)

    def execute_step(self, step: int, action: ParsedAction) -> StepResult:
        import numpy as np

        try:
            if action.atype == ActionType.MOVE_TO:
                # Navigate robot base — in sim, move EEF to hover above target zone
                target_pos = np.array(ZONE_POSITIONS.get(
                    action.loc, ZONE_POSITIONS["zone_b"]
                )) + np.array([0.0, 0.0, HOVER_Z_OFFSET])
                ok = self._step_to_target(target_pos)

            elif action.atype == ActionType.PICK:
                obj_name = action.obj
                obj = self._objects.get(obj_name)
                if obj is None:
                    return StepResult(step, action.raw, False,
                                      f"Object '{obj_name}' not in scene")
                obj_pos, _ = obj.get_world_pose()

                # 1. Hover above object
                hover = obj_pos + np.array([0.0, 0.0, HOVER_Z_OFFSET])
                ok = self._step_to_target(hover)
                if not ok:
                    return StepResult(step, action.raw, False, "Failed to reach hover")

                # 2. Open gripper
                self._open_gripper()

                # 3. Descend to object
                ok = self._step_to_target(obj_pos)
                if not ok:
                    return StepResult(step, action.raw, False, "Failed to reach object")

                # 4. Close gripper
                self._close_gripper()

                # 5. Lift
                ok = self._step_to_target(hover)

            elif action.atype == ActionType.PLACE:
                target_zone = action.loc
                target_pos = np.array(ZONE_POSITIONS.get(
                    target_zone, ZONE_POSITIONS["zone_b"]
                ))
                hover = target_pos + np.array([0.0, 0.0, HOVER_Z_OFFSET])

                # 1. Move to hover above target
                ok = self._step_to_target(hover)
                if not ok:
                    return StepResult(step, action.raw, False, "Failed to reach target hover")

                # 2. Descend
                ok = self._step_to_target(target_pos)
                if not ok:
                    return StepResult(step, action.raw, False, "Failed to reach place target")

                # 3. Open gripper (release)
                self._open_gripper()

                # 4. Retreat upward
                ok = self._step_to_target(hover)

            elif action.atype == ActionType.STACK:
                bottom_name = action.obj_bottom
                bottom = self._objects.get(bottom_name)
                if bottom is None:
                    return StepResult(step, action.raw, False,
                                      f"Bottom object '{bottom_name}' not in scene")
                bottom_pos, _ = bottom.get_world_pose()
                stack_pos = bottom_pos + np.array([0.0, 0.0, 0.06])  # object height
                hover = stack_pos + np.array([0.0, 0.0, HOVER_Z_OFFSET])

                ok = self._step_to_target(hover)
                if not ok:
                    return StepResult(step, action.raw, False, "Failed to reach stack hover")
                ok = self._step_to_target(stack_pos)
                if not ok:
                    return StepResult(step, action.raw, False, "Failed to reach stack pos")
                self._open_gripper()
                ok = self._step_to_target(hover)

            elif action.atype == ActionType.UNSTACK:
                top_name = action.obj
                top = self._objects.get(top_name)
                if top is None:
                    return StepResult(step, action.raw, False,
                                      f"Top object '{top_name}' not in scene")
                top_pos, _ = top.get_world_pose()
                hover = top_pos + np.array([0.0, 0.0, HOVER_Z_OFFSET])

                ok = self._step_to_target(hover)
                self._open_gripper()
                ok = self._step_to_target(top_pos)
                self._close_gripper()
                ok = self._step_to_target(hover)

            else:
                return StepResult(step, action.raw, False,
                                  f"Unknown action type: {action.atype}")

            if ok:
                return StepResult(step, action.raw, True,
                                  f"{action.atype.value} completed")
            else:
                return StepResult(step, action.raw, False,
                                  f"{action.atype.value} timed out (max sim steps reached)")

        except Exception as exc:
            return StepResult(step, action.raw, False, str(exc))


# ── Main orchestrator ─────────────────────────────────────────────────────────

class IsaacExecutor:
    """Runs a full action plan, reporting feedback to the agent hub after each step.

    Args:
        plan_id:        Hub plan ID (used for /status and /world_state updates).
        hub_url:        Base URL of the agent hub (default: http://localhost:8000).
        on_step:        Optional callback(StepResult) for in-process use.
        mock:           Override MOCK_ISAAC env var (True = mock, False = real sim).
    """

    def __init__(
        self,
        plan_id:  str,
        hub_url:  str = HUB_URL,
        on_step:  Callable[[StepResult], None] | None = None,
        mock:     bool = MOCK_ISAAC,
    ) -> None:
        self.plan_id = plan_id
        self.hub_url = hub_url
        self.on_step = on_step
        self._backend: MockExecutor | IsaacSimExecutor = (
            MockExecutor() if mock else IsaacSimExecutor()
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def run_plan(self, actions: list[dict[str, Any]]) -> bool:
        """Execute all actions in sequence. Returns True if all steps succeeded."""
        self._set_status("running")

        for item in actions:
            step   = item.get("step", 0)
            parsed = ParsedAction.parse(item.get("name", ""))

            result = self._backend.execute_step(step, parsed)

            if self.on_step:
                self.on_step(result)

            self._report_step(result)

            if not result.success:
                log.warning("Plan %s failed at step %d: %s",
                            self.plan_id, step, result.message)
                self._set_status("failure")
                return False

        self._set_status("success")
        return True

    # ── Hub callbacks ─────────────────────────────────────────────────────────

    def _set_status(self, status: str) -> None:
        try:
            requests.post(
                f"{self.hub_url}/execute_status",
                json={"plan_id": self.plan_id, "status": status},
                timeout=5,
            )
        except Exception:
            pass  # hub may not be running during standalone tests

    def _report_step(self, result: StepResult) -> None:
        try:
            requests.post(
                f"{self.hub_url}/execute_status",
                json={
                    "plan_id": self.plan_id,
                    "status":  "running",
                    "step":    result.step,
                    "action":  result.action,
                    "success": result.success,
                    "message": result.message,
                },
                timeout=5,
            )
        except Exception:
            pass


# ── Standalone CLI entry point ────────────────────────────────────────────────
# Mock (system Python):
#   python3 isaac_executor.py '{"plan_id":"abc","actions":[...]}'
#
# Real Isaac Sim GUI (RTX GPU required):
#   MOCK_ISAAC=0 HUB_URL=http://localhost:8000 \
#   ~/.local/share/ov/pkg/isaac-sim-5.1.0/python.sh \
#   SystemCode/ros2_bridge/src/isaac_executor.py '{"plan_id":"<id>","actions":[...]}'
#
# Headless (no window):
#   MOCK_ISAAC=0 ISAAC_HEADLESS=1 ~/.../python.sh isaac_executor.py '...'

if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    if not MOCK_ISAAC:
        # SimulationApp MUST be the first Isaac Sim import — creates the Omniverse window
        headless = os.environ.get("ISAAC_HEADLESS", "0") == "1"
        from isaacsim import SimulationApp
        _app = SimulationApp({"headless": headless, "renderer": "RaytracedLighting"})

    if len(sys.argv) < 2:
        # No payload: run a default demo plan so the window stays open
        DEMO_PLAN = {
            "plan_id": "demo-000",
            "actions": [
                {"step": 0, "name": "pick(franka,red_cube,zone_a)",  "cost": 1.0},
                {"step": 1, "name": "move_to(franka,zone_a,zone_c)", "cost": 1.0},
                {"step": 2, "name": "place(franka,red_cube,zone_c)", "cost": 1.0},
            ],
        }
        payload = DEMO_PLAN
        print("[info] No payload given — running default demo plan.")
    else:
        payload = json.loads(sys.argv[1])

    executor = IsaacExecutor(plan_id=payload["plan_id"], mock=MOCK_ISAAC)
    success  = executor.run_plan(payload["actions"])
    print(json.dumps({"success": success}))

    if not MOCK_ISAAC:
        _app.close()

    sys.exit(0 if success else 1)
