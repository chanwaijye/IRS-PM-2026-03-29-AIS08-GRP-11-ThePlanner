"""nl_to_pddl.py — Agent 1: Natural-language goal → PDDL problem string.

Uses Ollama (llama3:8b) with a few-shot system prompt.
Falls back to a template-filled stub if the LLM output fails validation.
"""

from __future__ import annotations

import json
import re
import textwrap
from typing import Any

import requests

# ── Ollama config ──────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3:8b"
TIMEOUT = 30  # seconds

# ── Few-shot examples embedded in system prompt ────────────────────────────
SYSTEM_PROMPT = textwrap.dedent("""\
    You are a PDDL 2.1 problem generator for a tabletop robot manipulation domain.

    Given:
    1. A natural-language manipulation goal.
    2. A JSON scene context describing visible objects, their positions, types,
       and properties (heavy, fragile).

    Output ONLY a valid PDDL problem string — no extra text, no markdown fences.

    Domain name: tabletop
    Available types: robot, object, location
    Available predicates:
      on(?obj - object, ?loc - location)
      on_table(?obj - object)
      clear(?obj - object)
      holding(?robot - robot, ?obj - object)
      hand_empty(?robot - robot)
      at(?robot - robot, ?loc - location)
      heavy(?obj - object)
      fragile(?obj - object)
      in_zone(?obj - object, ?loc - location)
      stacked_on(?obj_top - object, ?obj_bottom - object)

    --- EXAMPLE 1 ---
    Goal: "Move the red cube to the green zone"
    Scene: {"robot": "franka", "objects": [{"name": "red_cube", "type": "object",
            "at": "zone_a"}], "locations": ["zone_a", "zone_b", "zone_c"]}
    Output:
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
    )

    --- EXAMPLE 2 ---
    Goal: "Stack the blue cylinder on top of the red cube at zone B"
    Scene: {"robot": "franka", "objects": [
              {"name": "red_cube",      "type": "object", "at": "zone_b"},
              {"name": "blue_cylinder", "type": "object", "at": "zone_a"}],
            "locations": ["zone_a", "zone_b", "zone_c"]}
    Output:
    (define (problem tabletop-task)
      (:domain tabletop)
      (:objects
        franka - robot
        red_cube blue_cylinder - object
        zone_a zone_b zone_c - location
      )
      (:init
        (hand_empty franka)
        (at franka zone_a)
        (on_table red_cube)
        (clear red_cube)
        (on red_cube zone_b)
        (in_zone red_cube zone_b)
        (on_table blue_cylinder)
        (clear blue_cylinder)
        (on blue_cylinder zone_a)
        (in_zone blue_cylinder zone_a)
      )
      (:goal (and
        (stacked_on blue_cylinder red_cube)
        (in_zone red_cube zone_b)
      ))
    )

    --- EXAMPLE 3 ---
    Goal: "Place the fragile glass sphere gently in zone A"
    Scene: {"robot": "franka", "objects": [
              {"name": "glass_sphere", "type": "object", "at": "zone_c",
               "fragile": true}],
            "locations": ["zone_a", "zone_b", "zone_c"]}
    Output:
    (define (problem tabletop-task)
      (:domain tabletop)
      (:objects
        franka - robot
        glass_sphere - object
        zone_a zone_b zone_c - location
      )
      (:init
        (hand_empty franka)
        (at franka zone_c)
        (on_table glass_sphere)
        (clear glass_sphere)
        (on glass_sphere zone_c)
        (in_zone glass_sphere zone_c)
        (fragile glass_sphere)
      )
      (:goal (and (in_zone glass_sphere zone_a)))
    )
    --- END EXAMPLES ---

    Now generate the PDDL problem for the goal and scene below.
""")

# ── PDDL validation (lightweight structural check) ────────────────────────

def _is_valid_pddl(pddl: str) -> bool:
    """Returns True if pddl looks like a structurally valid problem definition."""
    text = pddl.strip()
    if not text.startswith("(define"):
        return False
    if "(:domain" not in text:
        return False
    if "(:objects" not in text:
        return False
    if "(:init" not in text:
        return False
    if "(:goal" not in text:
        return False
    # Balanced parentheses check
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth < 0:
            return False
    return depth == 0


# ── Template fallback ──────────────────────────────────────────────────────

def _build_fallback_pddl(scene_context: dict[str, Any]) -> str:
    """Construct a minimal PDDL problem from scene_context without the LLM."""
    robot = scene_context.get("robot", "franka")
    objects = scene_context.get("objects", [])
    locations = scene_context.get("locations", ["zone_a", "zone_b", "zone_c"])

    obj_names = [o["name"] for o in objects]
    objects_block = f"    {robot} - robot\n"
    if obj_names:
        objects_block += f"    {' '.join(obj_names)} - object\n"
    objects_block += f"    {' '.join(locations)} - location"

    init_facts: list[str] = [
        f"(hand_empty {robot})",
        f"(at {robot} {locations[0]})",
    ]
    for o in objects:
        name = o["name"]
        at = o.get("at", locations[0])
        init_facts += [
            f"(on_table {name})",
            f"(clear {name})",
            f"(on {name} {at})",
            f"(in_zone {name} {at})",
        ]
        if o.get("fragile"):
            init_facts.append(f"(fragile {name})")
        if o.get("heavy"):
            init_facts.append(f"(heavy {name})")

    init_block = "\n    ".join(init_facts)

    # Fallback goal: move first object to last location
    goal_fact = ""
    if obj_names and locations:
        goal_fact = f"(in_zone {obj_names[0]} {locations[-1]})"

    return textwrap.dedent(f"""\
        (define (problem tabletop-task)
          (:domain tabletop)
          (:objects
        {objects_block}
          )
          (:init
            {init_block}
          )
          (:goal (and {goal_fact}))
        )
    """)


# ── Public API ─────────────────────────────────────────────────────────────

def nl_to_pddl_problem(natural_language_goal: str,
                        scene_context: dict[str, Any]) -> str:
    """Convert a natural-language goal + scene context into a PDDL problem string.

    Args:
        natural_language_goal: e.g. "Move the red cube to the green zone"
        scene_context: dict with keys: robot (str), objects (list), locations (list)

    Returns:
        A valid PDDL problem string.
    """
    user_prompt = (
        f'Goal: "{natural_language_goal}"\n'
        f"Scene: {json.dumps(scene_context)}\n"
        "Output:"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": user_prompt,
        "stream": False,
        "options": {"temperature": 0.2, "top_p": 0.9},
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        # Strip accidental markdown fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE)
        pddl = raw.strip()
        if _is_valid_pddl(pddl):
            return pddl
    except Exception:
        pass

    # Validation failed or LLM unavailable — use template fallback
    return _build_fallback_pddl(scene_context)


# ── CLI smoke-test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    scene = {
        "robot": "franka",
        "objects": [
            {"name": "red_cube", "type": "object", "at": "zone_a"},
            {"name": "blue_cylinder", "type": "object", "at": "zone_b"},
        ],
        "locations": ["zone_a", "zone_b", "zone_c"],
    }
    goal = "Move the red cube to zone C"
    pddl = nl_to_pddl_problem(goal, scene)
    print(pddl)
