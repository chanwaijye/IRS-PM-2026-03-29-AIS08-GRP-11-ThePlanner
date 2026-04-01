# Execution Plan — ThePlanner: Environment Setup + Project Catchup (Rev 2)
**Date:** 2026-04-01 | **Deadline:** 2026-05-03 | **Solo Developer:** Chan Wai Jye

---

## Context

The proposal was submitted on Mar 29, 2026 (Week 3 deadline). SystemCode directories are all placeholders — no implementation code exists yet. Week 4 officially begins Apr 5. This plan covers two parallel tracks:

1. **Track A — Dev Environment Setup**: System configuration, toolchain, remote access, and AI CLI tools.  
   **Authentication strategy:** Chrome is set up first with the Google account + sync, then all Google-ecosystem services (Gemini CLI, gcloud, Google Cloud APIs) authenticate via Google IAM / Application Default Credentials (ADC) using that same signed-in identity — no per-service API key management needed.
2. **Track B — Project Catchup**: Technical milestones from Weeks 1–3 deferred during proposal writing (PDDL domain, C++ skeleton, Ollama/LLaMA-3, NetworkX KG, FastAPI hub).

**Corrections vs. Proposal:**
| Proposal | Actual |
|---|---|
| Ubuntu 22.04 | **Ubuntu 24.04 LTS (Noble Numbat)** |
| Isaac Sim 4.x | **Isaac Sim 5.1** |
| ROS2 Humble | **ROS2 Jazzy** (Humble is Ubuntu 22.04 only) |

---

## Track A — Development Environment Setup

### A1. System Baseline

```bash
lsb_release -a                        # Confirm: Ubuntu 24.04 LTS
sudo apt update && sudo apt full-upgrade -y
sudo apt autoremove -y
```

---

### A2. Passwordless sudo

```bash
echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/$USER
sudo chmod 440 /etc/sudoers.d/$USER
sudo -k && sudo whoami                # Must print 'root' without password prompt
```

---

### A3. GRUB — Remember Last Boot Selection

Edit `/etc/default/grub`:
```
GRUB_DEFAULT=saved
GRUB_SAVEDEFAULT=true
GRUB_TIMEOUT=5
```
```bash
sudo update-grub
```
Persists last selected kernel/OS — useful when dual-booting or pinning a kernel for Isaac Sim.

---

### A4. Zsh + Oh My Posh (omp) — Clean Profile

```bash
sudo apt install -y zsh curl
chsh -s $(which zsh)

# Install Oh My Posh
curl -s https://ohmyposh.dev/install.sh | bash -s

# Minimal clean ~/.zshrc (other tool exports appended below)
cat > ~/.zshrc << 'EOF'
# Oh My Posh
eval "$(oh-my-posh init zsh --config ~/.config/ohmyposh/clean.toml)"

# History
HISTSIZE=10000
SAVEHIST=10000
HISTFILE=~/.zsh_history
setopt SHARE_HISTORY HIST_IGNORE_DUPS

# PATH
export PATH="$HOME/.local/bin:$HOME/bin:$PATH"
EOF

mkdir -p ~/.config/ohmyposh
oh-my-posh init zsh --print-default-config > ~/.config/ohmyposh/clean.toml
# Recommended theme: atomic or jandedobbeleer
```

---

### A5. Git — Identity + Config

```bash
sudo apt install -y git git-lfs

git config --global user.name "Chan Wai Jye"
git config --global user.email "<your-email>"
git config --global core.editor "code --wait"
git config --global init.defaultBranch main
git config --global pull.rebase false
git lfs install
```

SSH key for GitHub:
```bash
ssh-keygen -t ed25519 -C "<your-email>" -f ~/.ssh/github
ssh-add ~/.ssh/github
cat ~/.ssh/github.pub   # Paste into: GitHub → Settings → SSH Keys
```

---

### A6. GitHub CLI (gh)

```bash
(type -p wget >/dev/null || sudo apt install wget -y) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  && cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] \
     https://cli.github.com/packages stable main" \
     | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt update && sudo apt install gh -y

gh auth login    # GitHub.com → SSH → browser
gh auth status
```

---

### A7. Google Chrome + Account Sync  ← IAM Anchor

**This step establishes the Google identity used by all subsequent Google services.**

```bash
wget -q -O /tmp/chrome.deb \
  https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i /tmp/chrome.deb
sudo apt --fix-broken install -y
```

**Post-install: sign in and sync**
1. Launch Chrome
2. Settings → "Sign in to Chrome" → sign in with your Google account
3. Enable Sync: everything (passwords, extensions, history, bookmarks)
4. This account becomes the Google IAM identity for all tools below

---

### A8. Google Cloud CLI (gcloud) — IAM Foundation

**All Google services (Gemini, Vertex AI, Cloud APIs) will use these Application Default Credentials (ADC).**

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL          # reload shell to pick up gcloud in PATH
gcloud init             # select/create project, set region

# Authenticate as the same Google account used in Chrome
gcloud auth login       # opens browser → use same Google account → grant access

# Set Application Default Credentials (ADC) — used by all Google SDKs
gcloud auth application-default login
# This writes credentials to: ~/.config/gcloud/application_default_credentials.json

# Verify
gcloud auth list        # should show active account
gcloud config list      # project, region confirmed
```

Add to `~/.zshrc`:
```bash
# gcloud
source "$(gcloud info --format='value(installation.sdk_root)')/path.zsh.inc"
source "$(gcloud info --format='value(installation.sdk_root)')/completion.zsh.inc"
export GOOGLE_CLOUD_PROJECT="<your-project-id>"
```

---

### A9. Gemini CLI — via Google IAM

```bash
# Node.js 22 (required for Gemini CLI)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Install Gemini CLI
npm install -g @google/gemini-cli

# Authenticate via Google OAuth (same account as Chrome/gcloud — NO API key needed)
gemini auth login       # opens browser → sign in with same Google account

# Verify: ADC is used automatically once gcloud auth application-default login is done
gemini --version
```

**How it works:** Gemini CLI uses Google OAuth / ADC. Since `gcloud auth application-default login` was already run in A8, Gemini CLI picks up those credentials automatically. No `GEMINI_API_KEY` env var required.

---

### A10. Claude Code CLI

```bash
# Install (Node.js already installed in A9)
npm install -g @anthropic-ai/claude-code

claude --version

# Authenticate via Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
```

---

### A11. OpenAI Codex CLI

```bash
npm install -g @openai/codex

export OPENAI_API_KEY="sk-..."
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.zshrc

codex --version
```

*(OpenAI is not part of Google IAM — OpenAI API key is required separately.)*

---

### A12. Remote Access to Home PC

**Recommended: Tailscale + SSH** (works behind NAT/CGNAT, zero config)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --operator=$USER
tailscale ip -4               # note your Tailscale IP (100.x.x.x)
sudo tailscale set --ssh      # enable Tailscale SSH (uses Tailscale auth, no keys needed)
```

From any device on Tailscale network: `ssh user@100.x.x.x`

**VS Code Remote SSH** (for coding remotely):
- Install "Remote - SSH" extension
- `~/.ssh/config` entry: `Host home-pc` / `HostName 100.x.x.x` / `User $USER`
- Command Palette → "Remote-SSH: Connect to Host → home-pc"

**GUI remote desktop** (needed to run Isaac Sim UI remotely):
```bash
# NoMachine — best for GPU-accelerated remote desktop
wget https://download.nomachine.com/download/8.x/Linux/nomachine_8.x.x_amd64.deb
sudo dpkg -i nomachine_*.deb
# Access: NoMachine client → connect to Tailscale IP
```

---

### A13. NVIDIA Isaac Sim 5.1

**Prerequisites:**
```bash
# NVIDIA driver ≥ 535 (required for Isaac Sim 5.1)
sudo ubuntu-drivers autoinstall
# or: sudo apt install -y nvidia-driver-570

# CUDA Toolkit 12.6
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update && sudo apt install -y cuda-toolkit-12-6

# Verify
nvidia-smi                  # driver ≥535
nvcc --version              # CUDA 12.x
```

**Install Isaac Sim 5.1 via Omniverse Launcher:**
1. Download NVIDIA Omniverse Launcher from developer.nvidia.com/omniverse
2. `chmod +x omniverse-launcher-linux.AppImage && ./omniverse-launcher-linux.AppImage`
3. Launcher → Exchange → Isaac Sim → 5.1.0 → Install
4. Default path: `~/.local/share/ov/pkg/isaac-sim-5.1.0/`

**Verify:**
```bash
~/.local/share/ov/pkg/isaac-sim-5.1.0/python.sh \
  -c "import omni; print(omni.__version__)"      # prints 5.1.x

~/.local/share/ov/pkg/isaac-sim-5.1.0/isaac-sim.sh \
  --headless --test                               # smoke test, no GPU display needed
```

**Add to `~/.zshrc`:**
```bash
alias isaac="~/.local/share/ov/pkg/isaac-sim-5.1.0/isaac-sim.sh"
alias isaac-py="~/.local/share/ov/pkg/isaac-sim-5.1.0/python.sh"
```

---

### A14. Additional Dev Tools

```bash
# Build tools
sudo apt install -y build-essential cmake ninja-build ccache \
  python3-pip python3-venv python3-dev \
  curl wget jq htop tmux tree bat ripgrep fd-find \
  clang-format clang-tidy valgrind gdb

# Fast Python package manager
pip install uv

# ROS2 Jazzy (Ubuntu 24.04 — Humble is EOL on 24.04)
sudo apt install -y software-properties-common
sudo add-apt-repository universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu noble main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update && sudo apt install -y ros-jazzy-desktop ros-dev-tools
echo "source /opt/ros/jazzy/setup.zsh" >> ~/.zshrc

# Ollama (local LLaMA-3)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b
# ollama serve runs as systemd service automatically
```

---

## Track B — Project Technical Catchup (Weeks 1–3 Backlog)

### B1. PDDL Domain Design

**File:** `SystemCode/planner/domain/tabletop.pddl`

PDDL 2.1 domain with 5 actions:
- `pick(robot, obj, from_loc)` — lift from surface
- `place(robot, obj, to_loc)` — set on surface
- `stack(robot, obj_top, obj_bottom)` — place on top of another object
- `unstack(robot, obj_top, obj_bottom)` — remove top from stack
- `move_to(robot, from_loc, to_loc)` — base navigation

Predicates: `on`, `on_table`, `clear`, `holding`, `hand_empty`, `at`, `heavy`, `fragile`, `in_zone`

**File:** `SystemCode/planner/domain/problem_template.pddl`  
Template with `{{OBJECTS}}`, `{{INIT}}`, `{{GOAL}}` placeholders filled by Agent 1.

---

### B2. C++ PDDL Planner Skeleton

```
SystemCode/planner/
├── CMakeLists.txt
├── include/
│   ├── pddl_parser.hpp      # domain + problem parser
│   ├── state.hpp            # state as predicate bitset
│   ├── action.hpp           # action schema + grounded action
│   ├── astar_planner.hpp    # A* over state space
│   ├── ga_ranker.hpp        # GA plan ranker (minimize steps, time, collision risk)
│   └── plan.hpp             # plan = vector<GroundedAction>
├── src/
│   ├── main.cpp             # CLI: read PDDL → output JSON plan
│   ├── pddl_parser.cpp
│   ├── astar_planner.cpp
│   └── ga_ranker.cpp
└── tests/
    ├── test_parser.cpp
    ├── test_astar.cpp
    └── test_ga.cpp
```

```bash
cd SystemCode/planner
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
./build/planner_node domain/tabletop.pddl domain/problem_template.pddl
```

---

### B3. LLaMA-3 / Ollama + Prompt Engineering

**File:** `SystemCode/llm_agent/src/nl_to_pddl.py`

```python
def nl_to_pddl_problem(natural_language_goal: str, scene_context: dict) -> str:
    # Input:  "Move the red cube to the green zone"
    # Output: valid PDDL problem string
    # Validates output with pddl-parser; falls back to template if invalid
```

System prompt: few-shot (3 examples), role-based, PDDL-constrained output.

---

### B4. NetworkX Knowledge Graph Scaffold

**File:** `SystemCode/llm_agent/src/knowledge_graph.py`

Nodes: objects (cube/cylinder/sphere), locations (zones A–C, table), robot (Franka FR3)  
Edges: affordances (graspable, stackable), properties (heavy >0.5kg, fragile), spatial relations

---

### B5. FastAPI Integration Hub

**File:** `SystemCode/ros2_bridge/src/agent_hub.py`

```
POST /goal          → NL goal in → plan_id out
GET  /plan/{id}     → JSON action sequence
POST /world_state   → perception update
GET  /status/{id}   → running / success / failure
POST /replan        → trigger replanning with new world state
```

Mock I/O mode per endpoint for independent agent testing.

---

## Authentication Architecture Summary

```
Google Account (Chrome sync)
    │
    ├── gcloud auth login               → gcloud CLI
    └── gcloud auth application-default login
            │
            ├── Gemini CLI              → uses ADC automatically
            ├── google-cloud Python SDK → uses ADC automatically
            └── Vertex AI APIs          → uses ADC automatically

GitHub account (SSH key)
    └── gh auth login                   → gh CLI

Anthropic API key
    └── ANTHROPIC_API_KEY               → Claude Code CLI

OpenAI API key
    └── OPENAI_API_KEY                  → Codex CLI
```

---

## Verification Checklist

```bash
# System
lsb_release -a                         # Ubuntu 24.04
nvidia-smi                             # driver ≥535
nvcc --version                         # CUDA 12.x

# Google IAM
gcloud auth list                       # active account shown
gcloud auth application-default print-access-token   # prints a token

# Tools
gh --version
claude --version
gemini --version
codex --version
ollama list | grep llama3

# Isaac Sim
~/.local/share/ov/pkg/isaac-sim-5.1.0/python.sh -c "import omni; print(omni.__version__)"

# ROS2
source /opt/ros/jazzy/setup.zsh && ros2 --version

# Remote access
tailscale status

# Project build
cd SystemCode/planner && cmake -B build && cmake --build build
./build/planner_node domain/tabletop.pddl domain/problem_template.pddl

# Python agents
cd SystemCode/llm_agent && python -m pytest tests/ -v
cd SystemCode/ros2_bridge && curl http://localhost:8000/goal \
  -X POST -d '{"goal":"Move red cube to green zone"}' -H "Content-Type: application/json"
```

---

## Critical Path Notes

| Issue | Resolution |
|---|---|
| ROS2 Humble → Jazzy | Ubuntu 24.04 requires ROS2 Jazzy; verify message type compatibility |
| Isaac Sim 4.x → 5.1 | Audit `omni.isaac.*` API changes before writing Agent 4 code |
| Gemini API key removed | Google ADC (A8) handles auth — `gemini auth login` uses same account |
| GRUB savedefault | Requires `GRUB_DEFAULT=saved` + `GRUB_SAVEDEFAULT=true` + `update-grub` |

---

## Files to Create/Modify

| Path | Action |
|---|---|
| `/etc/sudoers.d/$USER` | Create — NOPASSWD |
| `/etc/default/grub` | Edit — GRUB_DEFAULT=saved |
| `~/.zshrc` | Create — omp + PATH + source ROS2 + aliases |
| `~/.config/ohmyposh/clean.toml` | Create — omp theme |
| `~/.gitconfig` | Create — identity + prefs |
| `~/.ssh/github` + `github.pub` | Create — SSH key pair |
| `SystemCode/planner/domain/tabletop.pddl` | Create |
| `SystemCode/planner/domain/problem_template.pddl` | Create |
| `SystemCode/planner/CMakeLists.txt` | Create |
| `SystemCode/planner/include/*.hpp` (6 files) | Create |
| `SystemCode/planner/src/*.cpp` (4 files) | Create |
| `SystemCode/planner/tests/*.cpp` (3 files) | Create |
| `SystemCode/llm_agent/src/nl_to_pddl.py` | Create |
| `SystemCode/llm_agent/src/knowledge_graph.py` | Create |
| `SystemCode/ros2_bridge/src/agent_hub.py` | Create |
