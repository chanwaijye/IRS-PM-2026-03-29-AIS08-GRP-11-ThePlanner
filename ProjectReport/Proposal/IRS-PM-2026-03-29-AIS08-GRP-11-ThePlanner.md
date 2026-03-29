# THE PLANNER  

## Symbolic + Neural Task Reasoning for Robot Manipulation  

### NUS-ISS Intelligent Reasoning Systems Practice Module — Project Proposal

| Field | Detail |
|---|---|
| Submission Date | 29 March 2026 |
| Group Number | 11 |
| Cohort | AIS08 |
| Team Leader | Chan Wai Jye |
| Student ID | A0340644J |
| GitHub Repository | https://github.com/chanwaijye/IRS-PM-2026-03-29-AIS08-GRP-11-ThePlanner |
| Submission Type | Solo Submission — AI-Assisted Development |

---

## Abbreviations

| Abbreviation | Full Form |
|---|---|
| BT | Behaviour Tree |
| DoF | Degrees of Freedom |
| GA | Genetic Algorithm |
| GR00T | Generalist Robot 00 Technology (NVIDIA) |
| IRS | Intelligent Reasoning Systems |
| KG | Knowledge Graph |
| LLM | Large Language Model |
| NL | Natural Language |
| PDDL | Planning Domain Definition Language |
| PM | Practice Module |
| ROS2 | Robot Operating System 2 |
| RSSM | Recurrent State-Space Model |
| SDF | Signed Distance Field |
| URDF | Unified Robot Description Format |
| VLA | Vision-Language-Action (model) |
| YCB | Yale-CMU-Berkeley (object dataset) |

---

## 1. Introduction

Robots in warehouse logistics, hospital supply chains, and light manufacturing today rely overwhelmingly on hard-coded task scripts. These scripts are brittle — any change in object placement, task ordering, or environment requires manual reprogramming by a specialist. Task-level reasoning capabilities are largely absent: the robot cannot adapt to unexpected situations, nor recover automatically when something goes wrong.

The Planner addresses this gap. It is a five-agent AI system that allows a robot arm to accept a natural language task instruction, reason symbolically about how to accomplish it, perceive the real scene to verify preconditions, execute the resulting plan with GPU-accelerated motion planning, and automatically detect and recover from failures — all without human reprogramming.

The Planner is designed as a load-bearing component of a broader capstone project, MANIP-WM, which augments NVIDIA GR00T N1.6 with a language-conditioned RSSM World Model for long-horizon robotic manipulation. PM1 delivers the symbolic task planning layer — the cognitive backbone that generates structured sub-goal sequences consumed by downstream modules in subsequent practice modules.

### 1.1 Project Goals

- **G1:** Demonstrate a working hybrid symbolic-neural reasoning loop on a tabletop manipulation domain.
- **G2:** Prove that all four IRS technique groups can be integrated into a single coherent system.
- **G3:** Produce a fully runnable system in NVIDIA Isaac Sim — photorealistic, physics-accurate, zero hardware cost.
- **G4:** Deliver clear business value: a domain-agnostic reasoning engine that can reduce reliance on hard-coded robot scripts across multiple task domains.

### 1.2 Scope Statement

The Planner operates on a simulated tabletop manipulation domain with up to 6 objects. The robot model is the Franka Research 3 arm (URDF provided by NVIDIA). Tasks are specified in plain English and limited to pick, place, stack, move-to, and inspect actions. The project will be demonstrated entirely in NVIDIA Isaac Sim — no physical hardware is required. A web-based dashboard provides the user interface. The C++ PDDL planner is the primary technical contribution.

---

## 2. Project Background & Market Context

### 2.1 Business Problem

Industrial robot programming is expensive and specialised. A single robot work cell can require 3–6 weeks of programming time by a robotics engineer at $80,000–$120,000/year. When task specifications change — new products, new layouts — the cycle repeats. Global industrial robot installations exceeded 500,000 units annually (IFR World Robotics Report, 2023). Each represents a recurring reprogramming cost.

The core pain point is the absence of task-level reasoning. Current robots execute instructions; they do not plan. An intelligent reasoning layer that can interpret a natural language goal, automatically plan the action sequence, and recover from failures would dramatically reduce deployment cost and time-to-operation.

### 2.2 Market Opportunity

- Global warehouse automation market projected to reach USD $41B by 2027 (MarketsandMarkets, 2023).
- Hospital logistics robots (medication, linen, specimen delivery) represent a $4.5B segment growing at 15% CAGR.
- Small-batch manufacturing — the long tail of industrial automation — is largely unserved by current fixed-program robots.
- NVIDIA's Isaac platform is rapidly becoming the industry standard for simulation-first robot development, validating the technology choice.

### 2.3 Why NVIDIA Omniverse / Isaac?

- Isaac Sim is free for non-production use under the NVIDIA Developer Program — zero licensing cost for the project.
- Isaac ROS cuMotion provides GPU-accelerated motion planning, replacing MoveIt2's OMPL planner with substantially faster trajectory generation.
- Omniverse Replicator enables photorealistic synthetic data generation for training the perception neural network — no real camera or real objects required.
- The entire NVIDIA robotics stack (Isaac Sim, Isaac Lab, Isaac ROS, cuRobo, nvblox) is open-source and integrates natively, reducing inter-component friction.

---

## 3. Literature Review

### 3.1 Symbolic Task Planning — PDDL

Planning Domain Definition Language (PDDL) was introduced by McDermott et al. (1998) as a standard for AI planning competitions. Modern fast planners (Fast Downward, FF) solve thousands of actions in seconds. For robot manipulation, PDDL provides provably correct, interpretable plans — a key advantage over end-to-end neural approaches where failure modes are opaque. The Planner implements its own C++ PDDL planner from scratch to demonstrate understanding and applied implementation of the technique rather than calling an external planner binary.

### 3.2 Neural Task Planning & LLM Integration

SayCan (Ahn et al., Google 2022) and Code as Policies (Liang et al., arXiv 2022, ICRA 2023) showed that LLMs can bridge natural language and robot action spaces. However, both rely purely on the LLM for action selection, producing unverifiable plans. The Planner uses the LLM (LLaMA-3) only for goal extraction and PDDL problem generation — symbolic correctness is enforced by the formal planner, provided the domain model is accurate. This hybrid approach inherits interpretability from PDDL and flexibility from the LLM.

### 3.3 6-DoF Pose Estimation

FoundationPose (Wen et al., NVIDIA 2024) achieves state-of-the-art 6-DoF object pose estimation with minimal per-object training data using a foundation model approach. Its integration into Isaac ROS makes it directly usable in the Perception Agent without additional fine-tuning for new objects.

### 3.4 GPU-Accelerated Motion Planning — cuRobo / cuMotion

cuRobo (Sundaralingam et al., NVIDIA 2023) introduced parallel trajectory optimisation on GPU, generating collision-free, minimum-jerk trajectories 10–100x faster than CPU-based planners. Isaac ROS cuMotion wraps cuRobo as a production MoveIt2 plugin. This replaces the Executor Agent's prior MoveIt2/OMPL dependency with a substantially faster, more reliable planner.

### 3.5 Evolutionary / Genetic Algorithms for Plan Selection

Genetic algorithms have been applied to multi-objective plan quality optimisation in automated planning. Gerevini et al. (2003) introduced metric-temporal plan optimisation in the LPG planner, demonstrating local search over plan quality dimensions. The Planner's GA plan ranker draws on these principles, selecting over valid PDDL plan candidates by minimising a weighted combination of plan length, estimated execution time, and collision risk — providing a principled treatment of the Resource Optimisation IRS requirement.

---

## 4. IRS Technique Coverage

The project requirement specifies that at least three of the four IRS technique groups must be demonstrated. The Planner covers all four:

| Technique Group | IRS Requirement | Implementation in The Planner |
|---|---|---|
| ① | Decision Automation | Custom C++ PDDL Planner — A\* search over symbolic state space with domain action schemas (pick, place, stack, move-to, inspect). Plan validator checks pre/post-conditions. |
| ② | Business Resource Optimisation | Genetic Algorithm plan ranker over valid plan candidates — minimises weighted objective: steps × w₁ + estimated_time × w₂ + collision_risk × w₃. |
| ③ | Knowledge Discovery & Data Mining | NVIDIA Isaac ROS Object Detection + FoundationPose 6-DoF pose estimator builds live scene graph. Omniverse Replicator generates synthetic training data. |
| ④ | Cognitive Systems | LLaMA-3 (local LLM) translates natural language goals into PDDL problem specs. NetworkX knowledge graph encodes object affordances, robot capabilities, and spatial constraints. |

> **Note:** The C++ PDDL Planner (Agent 2) is the primary technical contribution and covers Technique Groups ① and ②. Writing the planner from first principles allows the team leader to demonstrate direct understanding of A\* search and PDDL semantics, rather than treating an external planner as a black box.

```{.mermaid width=50%}
flowchart LR
    A1["① Decision Automation <BR> PDDL A* Planner<BR>C++17"]
    A2["② Resource Optimisation<BR>Genetic Algorithm<BR>Plan Ranker"]
    A3["③ Knowledge Discovery<BR>FoundationPose<BR>Scene Graph"]
    A4["④ Cognitive Systems<BR>LLaMA-3 + NetworkX<BR>NL Interface"]

    A1 & A2 --> P["Agent 2<BR>Planner ★<BR>Core Contribution"]
    A3 --> P3["Agent 3<BR>Perception"]
    A4 --> P1["Agent 1<BR>NL Interface"]
```

---

## 5. System Design

### 5.1 Architecture Overview

The Planner is a five-agent pipeline. Each agent is a ROS2 node communicating via topics and services, with a FastAPI REST layer exposing the pipeline to the web UI. The pipeline follows a sequential execution order for normal operation and branches to a replanning loop on failure.

```{.mermaid width=50%}
flowchart TD
    A([User: Natural Language Goal<BR>e.g. Stack the red cube on the blue cylinder]) --> B

    B["Agent 1 — NL Interface<BR>LLaMA-3 + NetworkX KG<BR>NL → PDDL problem spec"]
    B --> C

    C["Agent 2 — Planner ★<BR>Custom C++ PDDL A* + GA<BR>PDDL → action sequence"]
    C --> D

    D["Agent 3 — Perception<BR>Isaac ROS + FoundationPose<BR>RGB-D → world state JSON"]
    D --> E

    E["Agent 4 — Executor<BR>Isaac Sim + cuMotion<BR>action → robot motion"]
    E --> F

    F{"Agent 5 — Monitor<BR>C++ rules + BT"}
    F -->|SUCCESS| G([Simulated Robot Motion Complete])
    F -->|FAILURE: replan| C
```

### 5.2 Agent Specifications

| Agent | Role | Technology | Implementation Detail |
|---|---|---|---|
| **Agent 1 — NL Interface** | Translate natural language goals into formal PDDL problem specifications | LLaMA-3:8b (Ollama) + NetworkX knowledge graph | Python 3.11. Structured prompt extracts objects, goal states, constraints. KG stores affordances (graspable, stackable) and spatial relations. |
| **Agent 2 — Planner ★** | Symbolic task planning over PDDL domain — core IRS contribution | Custom C++ PDDL Planner + A\* + GA Optimiser | C++17. PDDL parser, state-space A\* with h+ heuristic, plan validator. Genetic algorithm ranks valid plans by multi-objective cost function. |
| **Agent 3 — Perception** | Build live world-state scene graph from RGB-D camera input | Isaac ROS Object Detection, FoundationPose, nvblox, Omniverse Replicator | Python/ROS2. Detects YCB objects + 6-DoF pose. nvblox builds SDF obstacle map. Replicator generates synthetic training data. |
| **Agent 4 — Executor** | Convert action plans into collision-free robot trajectories and execute in Isaac Sim | Isaac ROS cuMotion (MoveIt2 plugin) + Isaac Sim (Omniverse) | C++/Python ROS2. cuMotion computes GPU-accelerated optimal-time trajectories. Isaac Sim provides photorealistic physics simulation. |
| **Agent 5 — Monitor** | Detect execution failures and trigger replanning loops | Isaac ROS Behaviour Trees + custom C++ rule engine | C++. Failure classes: grasp_failure, collision_detected, object_not_found. On failure: re-observe → update world state → re-plan. |

### 5.3 PDDL Domain — Action Schema (C++)

The PDDL domain defines five actions. A representative excerpt of the C++ planner's state-space A\* loop:

```cpp
// C++17 — PDDLPlanner::solve()
Plan PDDLPlanner::solve() {
  auto open = PriorityQueue<Node, float>();
  open.push({problem_.init, 0, heuristic(problem_.init)});
  while (!open.empty()) {
    auto [state, g, h] = open.pop();
    if (problem_.goal.satisfiedBy(state)) return reconstruct(state);
    for (auto& a : domain_.applicable(state)) {
      auto next = a.applyEffects(state);
      float f = g + a.cost + heuristic(next); // h+ relaxed plan
      open.push({next, g + a.cost, heuristic(next), f});
    }
  }
  return Plan::FAILURE;
}
```

### 5.4 Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Simulation | NVIDIA Isaac Sim (Omniverse) | Free — NVIDIA Dev Program |
| Motion Planning | Isaac ROS cuMotion + cuRobo | GPU-accelerated, C++/Python |
| Perception | Isaac ROS + FoundationPose + nvblox | 6-DoF pose + SDF scene map |
| Synthetic Data | Omniverse Replicator | Bundled in Isaac Sim |
| Task Planner | Custom C++ PDDL A\* + GA | Core IRS contribution |
| LLM Interface | LLaMA-3:8b via Ollama | Local, zero API cost |
| Robot Middleware | ROS2 Humble + FastAPI | Agent communication bus |
| Knowledge Graph | NetworkX | Object affordances + relations |
| Build System | CMake 3.20 + GCC 11/12 | C++17 standard; GCC 12 recommended for Isaac Sim 4.x |
| Web UI | React + Three.js + D3.js | 3D viewer + plan timeline |

---

## 6. Data Collection & Knowledge Sources

### 6.1 Scene Perception Data

- **YCB Object Dataset** — 77 common household objects with CAD models and ground-truth 6-DoF pose annotations. Used for training/fine-tuning the perception pipeline.
- **Omniverse Replicator** — generates unlimited photorealistic synthetic RGB-D training images of YCB objects in the Isaac Sim tabletop environment. Domain randomisation of lighting, textures, and camera angles. Eliminates the need for real camera data collection.
- **Isaac Sim ground-truth poses** — during development, the simulator provides exact object poses, enabling rapid prototyping of the planning pipeline without depending on perception accuracy.

### 6.2 PDDL Domain Knowledge

- **Hand-authored PDDL domain file** — 5 actions: `pick(?robot ?obj ?loc)`, `place(?robot ?obj ?loc)`, `stack(?robot ?obj1 ?obj2)`, `move-to(?robot ?loc)`, `inspect(?robot ?obj)`.
- **NetworkX knowledge graph** — nodes: object instances + robot; edges: affordance relations (graspable, stackable, fragile, too-heavy). Built manually from domain knowledge by the team leader.
- **PDDL problem files** — generated automatically by Agent 1 (LLaMA-3) from the user's natural language input and the current scene state from Agent 3.

### 6.3 Robot Model

- **Franka Research 3 URDF** — provided by NVIDIA in the Isaac Assets library. Includes accurate joint limits, mass properties, and collision geometry. No custom robot modelling required.

### 6.4 Benchmark Tasks

Each task is scored PASS or FAIL against three criteria: (1) correct final object configuration verified against the PDDL goal state, (2) completion within the time limit, and (3) number of replanning attempts within the allowed budget.

| Task | Instruction | Pass Condition | Time Limit | Max Replans |
|---|---|---|---|---|
| **Task 1 — Pick-and-place** | "Move the red cube to the green zone." | `on(red_cube, green_zone)` true in final world state | 30s | 2 |
| **Task 2 — Stacking** | "Stack the blue cylinder on top of the yellow block." | `on(blue_cylinder, yellow_block)` true; `on(yellow_block, table)` unchanged | 45s | 2 |
| **Task 3 — Conditional sort** | "Separate the fragile objects from the heavy ones." | All fragile objects on zone_A; all heavy objects on zone_B; no object misclassified | 90s | 3 |
| **Failure injection** | Inject: mid-grasp slip, object disappearance, joint limit violation | System detects failure, triggers replan, recovers and completes task | 60s per scenario | 3 |

Overall system target: **≥ 3/4 tasks PASS** across a run of 10 randomised scene configurations per task.

---

## 7. Team Structure & AI Agent Collaboration

This is a solo project. All development, design, and reporting is undertaken by a single human team leader. In place of human teammates, AI agents serve as development-time collaborators and are embedded as functional components of the system itself.

| Role | Name / Tool | Contribution | Type |
|---|---|---|---|
| **Team Leader (Human)** | Chan Wai Jye | All system architecture, PDDL domain design, integration decisions, report, videos. Sole human contributor. Estimated effort: 10 man-days. | Human |
| **Claude Chat (Anthropic)** | Claude (Anthropic) | Development-time assistant for architecture design, debugging, literature review, proposal drafting, and report writing. | Dev AI (Development only) |
| **Claude Code — Orchestrator** | Claude Code (Anthropic) | Orchestrates 5 specialised coding subagents. Delegates module implementation, enforces I/O contracts between agents, runs integration tests, triggers replanning on build/test failures. | Dev AI (Development only) |
| **Coding Subagent 1** | Claude Code subagent | Implements `nl_interface` module — LLaMA-3 Ollama client, PDDL prompt engineering, PDDL validator, fallback template generator. C++ + libcurl + nlohmann/json. | Dev AI (Development only) |
| **Coding Subagent 2** | Claude Code subagent | Implements `pm1_planner` module — PDDL parser, A\* search engine, h+ heuristic, GA plan optimiser, plan validator. C++17 core contribution. | Dev AI (Development only) |
| **Coding Subagent 3** | Claude Code subagent | Implements `scene_bridge` module — Isaac Sim scene graph query, symbolic fact extraction, FastAPI REST server (port 8001), C++ client, mock mode. | Dev AI (Development only) |
| **Coding Subagent 4** | Claude Code subagent | Implements `executor` module — ActionInstance-to-cuMotion bridge, ROS2 action client, ExecResult handling, simulation-only mode. C++ + ROS2. | Dev AI (Development only) |
| **Coding Subagent 5** | Claude Code subagent | Implements `monitor` module — rule-based failure detection, SQLite episode logging, replanning signal generation, FastAPI REST server (port 8002). Python. | Dev AI (Development only) |
| **AI Agent — NL Interface** | LLaMA-3:8b (local, Ollama) | Translates natural language task goals into PDDL problem specifications at runtime. Embedded in the system as Agent 1. | System AI (Runtime) |
| **AI Agent — Planner** | Custom C++ PDDL Engine | The symbolic reasoning core — A\* search over PDDL state space with GA plan optimiser. Deterministic, not an LLM. Built by Coding Subagent 2. | System AI (Runtime) |
| **AI Agent — Perception** | FoundationPose (NVIDIA) | 6-DoF object pose estimation embedded in Agent 3. Provides scene state to the planner. | System AI (Runtime) |

> **Effort note:** Approximately 10 man-days by the sole human contributor, as required by the module. Claude Code and its 5 coding subagents accelerate implementation of each module but operate under the team leader's direction — the human defines all I/O contracts, reviews all generated code, and owns all architectural decisions. All submitted code is reviewed and validated by the team leader.

**Development-time agent orchestration:**

```{.mermaid width=110%}
flowchart TD
    H([Human Team Leader<BR>Chan Wai Jye]) --> CC

    CC["Claude Code<BR>Orchestrator<BR>Development-time only"]

    CC --> SA1["Coding Subagent 1<BR>nl_interface<BR>C++ + Ollama client"]
    CC --> SA2["Coding Subagent 2<BR>pm1_planner<BR>C++ A* + GA — core"]
    CC --> SA3["Coding Subagent 3<BR>scene_bridge<BR>Isaac Sim + FastAPI"]
    CC --> SA4["Coding Subagent 4<BR>executor<BR>C++ + cuMotion ROS2"]
    CC --> SA5["Coding Subagent 5<BR>monitor<BR>Python + SQLite"]

    SA1 & SA2 & SA3 & SA4 & SA5 --> SYS["The Planner<BR>Runnable System"]
```

---

## 8. Project Timeline

| Week | Dates | Tasks & Milestones |
|---|---|---|
| Wk 1 | Mar 14–21 | Project setup: GitHub repo from IRS template. NVIDIA Dev Program accounts. Isaac Sim installation & smoke-test. PDDL domain design (5 actions). C++ project skeleton (CMake). LLaMA-3 local setup via Ollama. |
| Wk 2 | Mar 22–28 | Core C++ PDDL planner: parser, State struct, A\* search with h+ heuristic. Unit tests on toy 3-object tabletop problem. LLM prompt engineering: NL → PDDL problem spec. NetworkX knowledge graph skeleton. |
| **★ Wk 3** | **Mar 29 (DEADLINE)** | **PROPOSAL SUBMISSION DUE 23:59.** |
| Wk 4 | Apr 5–11 | PROPOSAL PRESENTATION (TBA). Isaac Sim environment: load Franka Research 3 URDF, tabletop scene with YCB objects. Perception pipeline: Isaac ROS + FoundationPose → scene JSON. cuRobo IK baseline test. |
| Wk 5 | Apr 12–18 | Agent integration sprint: NL → LLaMA-3 → PDDL → C++ Planner → plan JSON → cuMotion → Isaac Sim execution. End-to-end test on 3 benchmark tasks. |
| Wk 6 | Apr 19–25 | GA plan optimiser. Monitor agent failure-detection + replanning loop. FastAPI hardening. React + Three.js web UI. Promo video (5 min) + technical video (5 min) recording. |
| **★ Wk 7** | **May 3 (DEADLINE)** | **FINAL SUBMISSION DUE 23:59.** GitHub repo zip, 2 videos, group project report PDF, individual peer review forms. |


---

## 9. Budget & Resource Requirements

| Tool / Resource | Purpose | Cost | Notes |
|---|---|---|---|
| NVIDIA Isaac Sim + Isaac Lab | Robot simulation & RL training | **$0** | Free — NVIDIA Dev Program |
| Isaac ROS cuMotion | GPU-accelerated motion planning | **$0** | Free — open-source |
| cuRobo Library | Collision-free trajectory optimisation | **$0** | Free — research use |
| nvblox (Isaac ROS) | 3D scene SDF reconstruction | **$0** | Free — open-source |
| Omniverse Replicator | Synthetic training data generation | **$0** | Bundled with Isaac Sim |
| LLaMA-3:8b via Ollama | Local LLM — NL to PDDL translation | **$0** | Free — ~5GB download |
| ROS2 Humble + CMake | Robot middleware + C++ build | **$0** | Free — open-source |
| NetworkX | Object knowledge graph | **$0** | Free — Python library |
| GitHub (template repo) | Version control + submission | **$0** | Free |
| Cloud GPU (contingency) | AWS g6e if local GPU unavailable | **~$20 USD** | ~8 hrs × $2.50/hr |
| **TOTAL** | | **$0 baseline / ~$20 USD contingency** | |

> **Hardware note:** The team leader's desktop (Ryzen 9700X, RTX 5070 Ti 16GB VRAM, 64GB RAM) exceeds the recommended specification. Cloud GPU contingency applies only if local GPU is unavailable.

### 9.1 Hardware Minimum Requirements

- GPU: NVIDIA RTX 3070 (8GB VRAM) minimum — RTX 4080 (16GB) recommended
- RAM: 32GB DDR4/DDR5
- Storage: 100GB free NVMe (Isaac Sim ~50GB)
- OS: Ubuntu 22.04 LTS (preferred) or Windows 11

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| No qualifying GPU in team | Cannot run Isaac Sim locally | Use free AWS/Azure NVIDIA Isaac Sim Development Workstation AMI. ~$20 USD total. |
| PDDL planner scope creep | C++ planner too complex to complete on time | Fix domain to exactly 5 actions and 3 object types. Planner is unit-tested independently from Week 1. |
| Isaac Sim install issues | First-time setup can take 2+ hours | Dedicate full Day 1 of Week 1 to installation. |
| LLM PDDL generation errors | LLaMA-3 may produce invalid PDDL syntax | Implement a PDDL validator layer after LLM output. Fall back to template-based generation. |
| Agent integration complexity | 5 agents interacting via ROS2 topics | FastAPI backend as the integration hub. Each agent independently testable with mock inputs/outputs. |
| Video production time crunch | Two 5-minute videos take more time than expected | Allocate full Week 6 to video recording. Script both videos in Week 5. |
| Solo developer — no redundancy | Single point of failure on all tasks | Modular mock I/O per agent allows pipeline to run end-to-end even if one module is incomplete. MVP scoped to Agent 1 + Agent 2 + mock scene state — sufficient for a passing demonstration without full Isaac Sim integration. Daily GitHub commits preserve incremental progress for assessor visibility. |

---

## 11. Deliverables & Assessment Alignment

### 11.1 Final Deliverables (due 3 May 2026)

- GitHub repository — https://github.com/chanwaijye/IRS-PM-2026-03-29-AIS08-GRP-11-ThePlanner — code, README, installation guide.
- Promo video (5 min) — business pain, live use-case demo in Isaac Sim, pricing/value proposition.
- Technical video (5 min) — system architecture walkthrough, C++ planner code explanation, agent pipeline demo.
- Group project report (PDF) — market research, system design, implementation, findings & discussion. Appendices: this proposal, technique-to-course map, installation & user guide.
- Individual peer review forms — submitted separately to Canvas.

### 11.2 Grading Criterion Alignment

| Assessment Criterion | How The Planner Addresses It |
|---|---|
| Business Value | Warehouse/hospital logistics framing with quantified ROI (reduced reprogramming cost). Market research in Section 2. |
| System Design | 5-agent architecture covering all 4 IRS techniques. NVIDIA-only stack is industry-aligned. C++ PDDL planner is a custom implementation demonstrating applied symbolic reasoning. |
| System Implementation | End-to-end runnable in Isaac Sim. Demo-able from React web UI. Three benchmark tasks with pass/fail metrics. |
| Presentation Videos | Promo: business pain + Isaac Sim demo + pricing. Technical: architecture + code walkthrough + live agent pipeline run. |
| Project Contribution | Solo submission — all contributions by one human team leader. AI development tools used transparently (see Appendix A). Individual reflection in peer review form. |
| Value Adds | GA plan optimiser; replanning failure loop; 3D web viewer; Omniverse Replicator synthetic data; Isaac Sim photorealistic demo video. |

---

## 12. Conclusion

The Planner proposes an intelligent reasoning system for robot manipulation that aims to integrate all four IRS technique groups into a coherent, working pipeline. Rather than treating each technique in isolation, the design attempts to connect symbolic planning, heuristic search, neural perception, and natural language understanding into a single reasoning loop for tabletop manipulation tasks.

The decision to use the NVIDIA Omniverse / Isaac ecosystem is motivated by zero software licensing cost and compatibility with industry-standard robotics tooling. The custom C++ PDDL planner with A\* search and GA plan optimisation is intended as the core academic contribution, with the goal of demonstrating applied symbolic AI and heuristic search within a practical system.

The project is planned to be feasible within the 7-week timeline for a solo developer, supported by simulation-first development and AI-assisted implementation. If successful, the system may be applicable to domains such as warehouse logistics, hospital automation, and small-batch manufacturing — though this will depend on the quality of the final implementation and demonstration.

---

## Appendix A — Solo Submission & AI Usage Disclosure

### A.1 Solo Submission Declaration

This project is submitted as a solo effort by a single human team leader. The NUS-ISS IRS Practice Module permits groups of up to 5 members; this project operates at the minimum of 1 member. The estimated 10 man-days of effort required by the module is contributed entirely by the sole human participant.

### A.2 AI Agents as Development Collaborators

**Development-time AI (not present at runtime):**

| AI Tool | Usage Context | Scope & Limitations |
|---|---|---|
| Claude Chat (Anthropic) | Development-time only | Architecture design, literature review, debugging assistance, proposal drafting, report writing. All outputs reviewed and validated by the team leader. |
| Claude Code — Orchestrator | Development-time only | Orchestrates 5 specialised coding subagents via the Claude Code agentic framework. Delegates module implementation, enforces I/O contracts, runs integration tests. Human team leader defines all contracts and reviews all outputs. |
| Coding Subagent 1 | Development-time only | Implements `nl_interface` C++ module — Ollama client, PDDL prompt engineering, validator, template fallback. |
| Coding Subagent 2 | Development-time only | Implements `pm1_planner` C++ module — PDDL parser, A\* search, h+ heuristic, GA optimiser. Primary technical contribution. |
| Coding Subagent 3 | Development-time only | Implements `scene_bridge` module — Isaac Sim scene graph query, FastAPI server, C++ client, mock mode. |
| Coding Subagent 4 | Development-time only | Implements `executor` C++ module — cuMotion ROS2 action client, ExecResult handling, simulation-only mode. |
| Coding Subagent 5 | Development-time only | Implements `monitor` Python module — rule-based failure detection, SQLite logging, replanning signal, FastAPI server. |
| GitHub Copilot (optional) | Development-time only | May be used for boilerplate C++ code completion. All generated code reviewed and tested by the team leader. |

**Runtime AI (embedded in the submitted system):**

| AI Tool | Usage Context | Scope & Limitations |
|---|---|---|
| LLaMA-3:8b (Ollama, local) | Runtime system component | Embedded as Agent 1 (NL Interface) — translates natural language goals into PDDL problem specs at task-time. Core system function. |
| NVIDIA FoundationPose | Runtime system component | Embedded as pose estimation backbone of Agent 3 (Perception). Pre-trained model; no fine-tuning required for YCB objects. |

### A.3 Academic Integrity Statement

All intellectual contributions to system design, PDDL domain authoring, C++ planner architecture, IRS technique selection, and project decisions are made by the human team leader. AI tools are used in the same capacity as a search engine, Stack Overflow, or a knowledgeable colleague — as accelerators of understanding, not replacements for it. The team leader takes full academic responsibility for all submitted work. This disclosure will be reproduced in the final project report in accordance with NUS-ISS academic integrity guidelines.

---

## Appendix B — Technique-to-Course Module Mapping

```{.mermaid width=35%}
flowchart TD
    PM1["<b>PM1</b> — IRS<BR><b>The Planner</b><BR>Symbolic + Neural Task Reasoning"]
    PM2["PM2 — PRS<BR>The Eyes<BR>6-DoF Pose Estimation"]
    PM3["PM3 — Lang<BR>GR00T N1.6 VLA Fine-tuning"]
    PM4["PM4 — World Model<BR>RSSM Imagination Loop — C++"]
    CAP["Capstone<BR>MANIP-WM<BR>GR00T + RSSM (>85% success)"]

    PM1 -->|"dataset 500 episodes"| PM2
    PM2 -->|"6-DoF poses to VLA"| PM3
    PM3 -->|"fine-tuned action head"| PM4
    PM4 -->|"full integration"| CAP
```

> This proposal covers **PM1 only**. Scene state initialisation uses Isaac Sim ground-truth object poses in PM1; real 6-DoF visual perception is addressed in the subsequent Pattern Recognition Systems practice module (PM2).

| IRS Technique | Course Module | Where Demonstrated in The Planner |
|---|---|---|
| Business rules & knowledge-based reasoning | MR — Machine Reasoning | PDDL domain + C++ planner. Action schemas with typed preconditions/effects are a formal knowledge-based reasoning system. |
| Informed search (A\*) | RS — Reasoning Systems | C++ A\* planner with h+ relaxed-plan heuristic. GA plan optimiser as evolutionary search. |
| Knowledge discovery / data mining | MR — Machine Reasoning | Scene graph construction from neural perception (FoundationPose + nvblox). Synthetic data generation via Replicator. |
| Cognitive systems (NLP, knowledge graph) | CGS — Cognitive Systems | LLaMA-3 natural language interface. NetworkX affordance knowledge graph. Behaviour tree orchestration. |

---

## References

Ahn, M., Brohan, A., Brown, N., Chebotar, Y., Cortes, O., David, B., ... & Zeng, A. (2022). Do as I can, not as I say: Grounding language in robotic affordances. *arXiv preprint arXiv:2204.01691*.

Gerevini, A., Saetti, A., & Serina, I. (2003). Planning through stochastic local search and temporal action graphs in LPG. *Journal of Artificial Intelligence Research*, 20, 239–290.

International Federation of Robotics (IFR). (2023). *World Robotics Report 2023*. IFR Press.

Liang, J., Huang, W., Xia, F., Xu, P., Hausman, K., Ichter, B., ... & Zeng, A. (2022). Code as policies: Language model programs for embodied control. *arXiv preprint arXiv:2209.07753*. Presented at ICRA 2023.

MarketsandMarkets. (2023). *Warehouse Automation Market — Global Forecast to 2027*. MarketsandMarkets Research.

McDermott, D., Ghallab, M., Howe, A., Knoblock, C., Ram, A., Veloso, M., ... & Wilkins, D. (1998). PDDL — the planning domain definition language. *Technical Report CVC TR-98-003*, Yale Center for Computational Vision and Control.

Sundaralingam, B., Hari, S. S., Fishman, A., Garrett, C., Van Wyk, K., Blukis, V., ... & Fox, D. (2023). cuRobo: Parallelized collision-free robot motion generation. *arXiv preprint arXiv:2310.17274*.

Wen, B., Yang, W., Kautz, J., & Birchfield, S. (2024). FoundationPose: Unified 6D pose estimation and tracking of novel objects. *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)*.

---

*IRS-PM-2026-03-29-AIS08-GRP-11-ThePlanner*
