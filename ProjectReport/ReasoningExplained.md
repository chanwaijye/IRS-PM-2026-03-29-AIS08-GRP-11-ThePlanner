# ThePlanner — Reasoning Explained

## Overview

ThePlanner uses a **hybrid reasoning architecture**: a large language model (LLM) handles
natural-language understanding and PDDL problem generation (symbolic *specification*), while a
classical A* planner handles optimal action sequencing (symbolic *search*). A genetic algorithm
then re-ranks candidate plans by cost.

---

## Stage 1 — Scene Grounding via Knowledge Graph

**File:** `SystemCode/llm_agent/src/knowledge_graph.py`

Before any LLM call, the system queries the Scene Knowledge Graph (KG) to produce a
structured `scene_context` dict. The KG is a NetworkX directed graph where:

| Node type | Examples |
|---|---|
| `robot` | `franka` |
| `object` | `red_cube`, `glass_sphere` |
| `location` | `zone_a`, `zone_b`, `zone_c` |

Edges encode spatial relations (`on`, `in_zone`, `stacked_on`) and affordances (`graspable`,
`stackable`). The `to_scene_context()` method flattens the graph into a JSON-serialisable dict
the LLM can read.

**Why this matters:** Grounding prevents hallucination. The LLM is not asked to invent object
names or locations — it receives them from perception.

---

## Stage 2 — LLM Reasoning (Agent 1)

**File:** `SystemCode/llm_agent/src/nl_to_pddl.py`

### 2a. Prompt Design

The system prompt uses **few-shot chain-of-thought**:

```
Role: "You are a PDDL 2.1 problem generator…"
Constraints: exact predicate names, no free-form text, no markdown fences
Few-shot examples: 3 worked examples (move, stack, fragile-handle)
User turn: goal string + scene_context JSON
```

Three carefully chosen examples cover the main action families:
- `in_zone` goal (move)
- `stacked_on` goal (stack)
- `fragile` property handling (constrained placement)

### 2b. LLM Inference

```python
payload = {
    "model": "llama3:8b",
    "system": SYSTEM_PROMPT,       # few-shot role + examples
    "prompt": user_prompt,         # goal + scene JSON
    "options": {"temperature": 0.2, "top_p": 0.9},
}
```

Low temperature (0.2) is deliberate: PDDL generation is a deterministic translation task, not
creative writing. High temperature increases the chance of syntactically broken output.

### 2c. Output Validation + Fallback

The LLM output passes through `_is_valid_pddl()`, which checks:

1. Starts with `(define`
2. Contains `(:domain`, `(:objects`, `(:init`, `(:goal`
3. Balanced parentheses (depth never goes negative, ends at 0)

If validation fails **or** Ollama is unreachable, `_build_fallback_pddl()` constructs a valid
PDDL problem directly from the `scene_context` dict without any LLM call. The fallback goal
is conservative: move the first object to the last location.

**Reasoning guarantee:** The system always produces a syntactically valid PDDL problem, even
if the LLM fails. This prevents the downstream planner from crashing.

---

## Stage 3 — Classical Planning (Agent 2)

**File:** `SystemCode/planner/src/astar_planner.cpp`

### 3a. State Representation

World state is encoded as a **bitset** indexed by a `PredicateIndex` (a map from
`(predicate_name, arg_tuple)` → `bit position`). A state is satisfied when all goal-state
bits are set.

This compact representation makes state equality checks O(1) and memory efficient for
large grounded action spaces.

### 3b. A* Search

```
h(state) = number of unsatisfied goal predicates
```

A* expands states in order of `f = g + h` where:
- `g` = number of actions taken so far (uniform cost = 1 per action)
- `h` = admissible heuristic (never over-estimates; each action satisfies ≥1 predicate)

The heuristic is admissible because each action can satisfy at most all remaining goal
predicates in one step, so `h` ≤ actual remaining cost.

**Optimality guarantee:** With an admissible heuristic, A* returns the shortest plan.

### 3c. Grounding

The parser cross-products action schemas with all object tuples of the correct types,
producing a flat list of `GroundedAction` structs. Each grounded action stores its
precondition and effect bitsets, enabling O(1) applicability checks during search.

---

## Stage 4 — GA Plan Ranking

**File:** `SystemCode/planner/src/ga_ranker.cpp`

When multiple plans of equal length exist (A* may find several optimal paths), the GA
selects the best by minimising a weighted fitness function:

```
fitness = α × plan_length + β × total_cost + γ × fragile_risk
```

where `fragile_risk` counts actions applied to fragile objects without the `gentle`
modifier. The GA evolves a population of permutations of equivalent plans for a fixed
number of generations, returning the individual with lowest fitness.

---

## Stage 5 — World-State Update and Replanning

**File:** `SystemCode/ros2_bridge/src/agent_hub.py`

After each Isaac Sim execution step, Agent 3 (monitor) pushes a `POST /world_state`
update. The hub rebuilds the KG from the new scene context via
`SceneKnowledgeGraph.from_scene_context()`. If an action fails mid-plan, `POST /replan`
triggers a full re-run of Stages 1–4 with the updated KG as starting state.

The `apply_action()` method on `SceneKnowledgeGraph` can also speculatively update the KG
after each planner step (without waiting for Isaac Sim feedback), enabling faster
look-ahead during replanning.

---

## Reasoning Architecture Summary

```
Perception (Isaac Sim / camera)
    ↓
Knowledge Graph (NetworkX)          ← structured world model
    ↓  scene_context
LLM (LLaMA-3 8B, few-shot)          ← NL understanding + PDDL specification
    ↓  PDDL problem string
    ↓  [validation + fallback]
C++ A* Planner                      ← optimal action sequencing
    ↓  action sequence
GA Ranker                           ← cost/risk minimisation
    ↓  JSON plan
Isaac Sim Execution                 ← physical robot control
    ↓  feedback
Replanning loop (if needed)
```

### Why Hybrid (LLM + Classical)?

| Concern | LLM alone | Classical alone | Hybrid |
|---|---|---|---|
| NL understanding | Good | None | Good |
| Plan optimality | Not guaranteed | Guaranteed (A*) | Guaranteed |
| Novel goal handling | Good | Requires manual PDDL | Good |
| Execution speed | Slow (LLM latency) | Fast | Fast (LLM once, planner fast) |
| Failure recovery | Unpredictable | Deterministic | Deterministic |

The LLM is used exactly once per goal (high-latency, high-expressivity step) to produce
a PDDL problem. All subsequent reasoning (search, ranking, replanning) is deterministic
classical AI — fast, verifiable, and optimal.
