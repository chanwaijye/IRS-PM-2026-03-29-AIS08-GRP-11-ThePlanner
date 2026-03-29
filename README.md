### [ Practice Module ] Project Submission Template: Github Repository & Zip File

**[ Naming Convention ]** CourseCode-StartDate-BatchCode-TeamName-ProjectName.zip

* **[ MTech Stackable Group Project Naming Example ]** IRS-PM-2026-03-29-AIS08-GRP-11-ThePlanner.zip

---

## SECTION 1 : PROJECT TITLE
## THE PLANNER — Symbolic + Neural Task Reasoning for Robot Manipulation

---

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

Robots in warehouse logistics, hospital supply chains, and light manufacturing today rely on hard-coded task scripts that break whenever object placement, task ordering, or the environment changes. The Planner addresses this gap with a five-agent AI system that accepts a natural language task instruction, reasons symbolically about how to accomplish it, perceives the scene to verify preconditions, executes the plan with GPU-accelerated motion planning, and automatically recovers from failures — all without human reprogramming.

The core technical contribution is a custom C++ PDDL planner implementing A\* search with an h+ relaxed-plan heuristic and a Genetic Algorithm plan ranker for multi-objective optimisation. The system covers all four IRS technique groups:

| Technique Group | Implementation |
|---|---|
| Decision Automation | Custom C++ PDDL A\* Planner |
| Business Resource Optimisation | Genetic Algorithm plan ranker |
| Knowledge Discovery & Data Mining | FoundationPose 6-DoF pose estimation + scene graph |
| Cognitive Systems | LLaMA-3 NL interface + NetworkX knowledge graph |

The entire system runs in NVIDIA Isaac Sim at zero software cost, using the Franka Research 3 robot arm on a tabletop manipulation domain with up to 6 objects.

---

## SECTION 3 : CREDITS / PROJECT CONTRIBUTION

| Official Full Name | Student ID | Work Items | Email |
| :------------ |:---------------:| :-----| :-----|
| Chan Wai Jye | A0340644J | All system architecture, PDDL domain design, C++ planner implementation, agent integration, report, videos. Solo submission — AI-assisted development. | A0340644J@nus.edu.sg |

**AI Development Tools Used:**

| Tool | Role |
|---|---|
| Claude Chat (Anthropic) | Architecture design, literature review, proposal drafting, report writing |
| Claude Code (Anthropic) | Orchestrates 5 coding subagents for module implementation |
| GitHub Copilot (optional) | Boilerplate C++ code completion |

All AI-generated outputs are reviewed and validated by the team leader. Full AI usage disclosure in Appendix A of the project report.

---

## SECTION 4 : VIDEO OF SYSTEM MODELLING & USE CASE DEMO

> Videos will be uploaded by the final submission deadline (3 May 2026).

- **Promo video (5 min)** — business pain, live use-case demo in Isaac Sim, pricing/value proposition.
- **Technical video (5 min)** — system architecture walkthrough, C++ planner code explanation, agent pipeline demo.

---

## SECTION 5 : USER GUIDE

`Refer to appendix <Installation & User Guide> in project report at Github Folder: ProjectReport`

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Ubuntu | 22.04 LTS | Preferred OS |
| NVIDIA GPU | RTX 3070+ (8GB VRAM min) | RTX 4080+ (16GB) recommended |
| NVIDIA Isaac Sim | 4.x | Free — NVIDIA Developer Program |
| ROS2 | Humble | Robot middleware |
| CMake | 3.20+ | C++ build system |
| GCC | 11/12 | C++17 support |
| Ollama | Latest | Local LLM runtime |
| Python | 3.11 | Agent 1 + Agent 5 |
| Node.js | 18+ | Web UI |

### Build & Run

```bash
# 1. Clone the repository
git clone https://github.com/chanwaijye/IRS-PM-2026-03-29-AIS08-GRP-11-ThePlanner.git
cd IRS-PM-2026-03-29-AIS08-GRP-11-ThePlanner

# 2. Install LLaMA-3 via Ollama
ollama pull llama3:8b

# 3. Build the C++ PDDL planner
cd SystemCode/planner
mkdir build && cd build
cmake .. && make -j$(nproc)

# 4. Launch Isaac Sim environment
# (Follow NVIDIA Isaac Sim installation guide first)

# 5. Start the agent pipeline
# (Detailed instructions in project report appendix)
```

---

## SECTION 6 : PROJECT REPORT / PAPER

`Refer to project report at Github Folder: ProjectReport`

- **Proposal:** [ProjectReport/Proposal/](ProjectReport/Proposal/)

**Report Sections:**
- Executive Summary
- Business Problem Background
- Market Research
- Project Objectives & Success Measurements
- Project Solution (domain modelling & system design)
- Project Implementation (system development & testing)
- Project Performance & Validation
- Project Conclusions: Findings & Recommendation
- Appendix: Project Proposal
- Appendix: Mapped System Functionalities against MR, RS, CGS
- Appendix: Installation and User Guide
- Appendix: Individual project report
- Appendix: List of Abbreviations
- Appendix: References

---

## SECTION 7 : MISCELLANEOUS

`Refer to Github Folder: Miscellaneous`

### System Architecture

Five-agent pipeline: NL Interface (LLaMA-3) → Planner (C++ PDDL A\* + GA) → Perception (FoundationPose) → Executor (cuMotion) → Monitor (C++ rules + BT). Agents communicate via ROS2 topics/services with a FastAPI REST layer for the web UI.

### Key Technologies

- NVIDIA Isaac Sim / Omniverse — photorealistic robot simulation
- Isaac ROS cuMotion / cuRobo — GPU-accelerated motion planning
- FoundationPose — 6-DoF object pose estimation
- Omniverse Replicator — synthetic training data generation
- LLaMA-3:8b via Ollama — local LLM for NL-to-PDDL translation
- NetworkX — object affordance knowledge graph

---

**This [Machine Reasoning (MR)](https://www.iss.nus.edu.sg/executive-education/course/detail/machine-reasoning "Machine Reasoning") course is part of the Analytics and Intelligent Systems and Graduate Certificate in [Intelligent Reasoning Systems (IRS)](https://www.iss.nus.edu.sg/stackable-certificate-programmes/intelligent-systems "Intelligent Reasoning Systems") series offered by [NUS-ISS](https://www.iss.nus.edu.sg "Institute of Systems Science, National University of Singapore").**

**Lecturer: [GU Zhan (Sam)](https://www.iss.nus.edu.sg/about-us/staff/detail/201/GU%20Zhan "GU Zhan (Sam)")**

[![alt text](https://www.iss.nus.edu.sg/images/default-source/About-Us/7.6.1-teaching-staff/sam-website.tmb-.png "Let's check Sam' profile page")](https://www.iss.nus.edu.sg/about-us/staff/detail/201/GU%20Zhan)

**zhan.gu@nus.edu.sg**
