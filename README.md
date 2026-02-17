# OKR Tracker 🚀

A powerful Streamlit application for managing Objectives and Key Results (OKRs), featuring multi-user support, role-based access, AI-driven strategic analysis, and deadline tracking.

---

## Documentation HQ

Use this section as the single entry point for all project docs.

### 📘 Core Guides

- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **License**: [LICENSE](LICENSE)
- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Performance Budget**: [performance.md](performance.md)
- **AI Features (En)**: [docs/AI_FEATURES_GUIDE.md](docs/AI_FEATURES_GUIDE.md)
- **AI Features (Fa)**: [docs/AI_FEATURES_GUIDE_FA.md](docs/AI_FEATURES_GUIDE_FA.md)
- **User Guide (En)**: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- **User Guide (Fa)**: [docs/USER_GUIDE_FA.md](docs/USER_GUIDE_FA.md)
- **Admin Guide (En)**: [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md)
- **Admin Guide (Fa)**: [docs/ADMIN_GUIDE_FA.md](docs/ADMIN_GUIDE_FA.md)
- **Manager Playbook (En)**: [docs/MANAGER_PLAYBOOK.md](docs/MANAGER_PLAYBOOK.md)
- **Manager Playbook (Fa)**: [docs/MANAGER_PLAYBOOK_FA.md](docs/MANAGER_PLAYBOOK_FA.md)
- **OKR Lifecycle (En)**: [docs/OKR_LIFECYCLE_GUIDE.md](docs/OKR_LIFECYCLE_GUIDE.md)
- **OKR Lifecycle (Fa)**: [docs/OKR_LIFECYCLE_GUIDE_FA.md](docs/OKR_LIFECYCLE_GUIDE_FA.md)

### 🛠️ Ops & Infrastructure

- **Config Reference**: [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md)
- **Deployment Checklist**: [docs/DEPLOY_CHECKLIST.md](docs/DEPLOY_CHECKLIST.md)
- **Docker Compose**: [docs/DOCKER_COMPOSE.md](docs/DOCKER_COMPOSE.md)
- **Kubernetes**: [docs/KUBERNETES.md](docs/KUBERNETES.md)
- **Reverse Proxy**: [docs/REVERSE_PROXY.md](docs/REVERSE_PROXY.md)
- **Operations**: [docs/OPERATIONS.md](docs/OPERATIONS.md)
- **Troubleshooting**: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **First-Run Runbook**: [docs/RUNBOOK.md](docs/RUNBOOK.md)

---

- Operations guide: [docs/OPERATIONS.md](docs/OPERATIONS.md)
- Troubleshooting guide: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- First deployment runbook: [docs/RUNBOOK.md](docs/RUNBOOK.md)

---

## Deployment Modes (Important)

Choose one mode:

1. Streamlit Cloud (MVP/simple hosting)

- No SSH deploy secrets are required.
- App is deployed by Streamlit Cloud from this GitHub repository.
- The SSH deploy workflow/job is expected to skip.

2. Self-hosted Docker Compose (server/VM)

- Use this for Nginx + Docker Compose + your own server.
- If you enable GitHub Actions SSH deploy, set:
  - `SSH_HOST`
  - `SSH_USER`
  - `SSH_KEY`
  - `REMOTE_DEPLOY_DIR`
- Supported fallback secret names in workflow:
  - Host: `DEPLOY_HOST` or `HOST`
  - User: `DEPLOY_USER` or `USERNAME`
  - Key: `DEPLOY_KEY`
  - Deploy dir: `DEPLOY_DIR`

Where to set `SSH_KEY`:

- GitHub repository -> `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`.
- Add the private key content under `SSH_KEY` (or `DEPLOY_KEY`).

Security note:

- Never commit private keys or deploy secrets to the repository.

---

## 🌟 Features Overview

### Core Functionality

| Feature                 | Description                                                |
| ----------------------- | ---------------------------------------------------------- |
| **Multi-User System**   | Secure authentication with bcrypt password hashing         |
| **Role-Based Access**   | Admin, Manager, and Member roles with distinct permissions |
| **4-Level Hierarchy**   | Goal → Objective → Key Result → Task                       |
| **Time Tracking**       | Built-in timer with work session logging                   |
| **Deadline Management** | Set due dates with health status indicators (🟢🟡🔴)       |
| **AI Analysis**         | Google Gemini integration for strategic evaluation         |
| **PDF Reports**         | Export daily/weekly work summaries                         |
| **RTL Support**         | Full Persian/Arabic layout support with Vazirmatn font     |

### Hierarchy Structure

```
🏁 Goal (with ♟️ Strategy Tags)
└── 🎯 Objective
    └── 📊 Key Result (with ⚡ Initiative Tags)
        └── 📋 Task (with ⏱️ Timer & 📅 Deadline)
```

---

## 📖 User Guide

### Getting Started

#### 1. Login

- Default credentials: `admin` / `admin`
- First-time setup: Create additional users via Admin Panel

#### 2. Select a Cycle

Use the cycle selector in the sidebar to choose your active OKR period (e.g., "Q1 2025").

#### 3. Navigate the Hierarchy

- Click **Open** on any card to drill down into children
- Use **breadcrumbs** at the top to navigate back
- Click **Inspect** to view/edit details

---

### Creating OKRs

#### Add a Goal

1. From the home view, click **➕ Add Goal**
2. Enter title and description
3. Assign Strategy Tags (e.g., "Growth", "Efficiency")

#### Add an Objective

1. Open a Goal and click **➕ Add Objective**
2. Objectives define _what_ you want to achieve

#### Add a Key Result

1. Open an Objective and click **➕ Add Key Result**
2. Set **Target Value** and **Unit** (e.g., "100", "%")
3. Add Initiative Tags for categorization

#### Add a Task

1. Open a Key Result and click **➕ Add Task**
2. Tasks are actionable items with:
   - Progress tracking (0-100%)
   - Time tracking with built-in timer
   - Deadline setting

---

### ⏱️ Time Tracking

**For Members Only**

1. Click **Start Timer** on any task card
2. Work on the task - timer runs in background
3. Click **Stop & Save** when done
4. Add a summary of what you accomplished
5. View work history in the Task Inspector

---

### 📅 Deadline Management

#### Setting a Deadline

1. Open Task Inspector (click **Inspect** on task card)
2. Scroll to **📅 Deadline** section
3. Select a due date and click **Save Deadline**

#### Deadline Status Indicators

| Status    | Icon | Meaning                                 |
| --------- | ---- | --------------------------------------- |
| Completed | ✅   | Task is 100% done                       |
| On Track  | 🟢   | Progress matches expected pace          |
| At Risk   | 🟡   | Behind schedule but deadline not passed |
| Overdue   | 🔴   | Deadline passed, not complete           |

#### Deadline Health Score

The system calculates expected progress based on time elapsed:

```
Expected Progress = (Days Elapsed / Total Days) × 100%
```

If actual progress < expected, the task is flagged "At Risk".

---

### 🧠 AI Strategic Analysis

**Available on Key Results**

1. Open a Key Result and click **Inspect**
2. Scroll to **🧠 AI Strategic Analysis**
3. Click **✨ Run Analysis**

#### What AI Analyzes

- **Efficiency Score**: Is the work scope complete?
- **Effectiveness Score**: Are the right strategies in place?
- **Gap Analysis**: What's missing to reach 100%?
- **Deadline Warnings**: Flags overdue/at-risk tasks
- **Proposed Tasks**: AI-suggested tasks to fill gaps

#### Acting on Suggestions

Click **Add** next to any proposed task to create it directly.

---

### 🧭 Strategic Health Dashboard

**For Admin/Manager**

Access via the **🧭** button in sidebar.

#### Dashboard Features

| Section                | Description                                     |
| ---------------------- | ----------------------------------------------- |
| **Team Filter**        | Select which members to include (Admin/Manager) |
| **Scorecard**          | Data hygiene %, confidence, at-risk counts      |
| **Progress by Member** | Bar chart comparing team progress               |
| **Deadline Health**    | Overdue/at-risk tasks per member                |
| **Strategic Matrix**   | Efficiency vs Effectiveness scatter plot        |
| **At-Risk Lists**      | KRs and tasks needing attention                 |
| **AI Team Coach**      | Get personalized coaching tips from AI          |

#### Strategic Alignment Matrix Quadrants

| Quadrant           | Meaning                              |
| ------------------ | ------------------------------------ |
| 🌟 High Performers | High efficiency + High effectiveness |
| ⚠️ Busy Work       | High efficiency + Low effectiveness  |
| 🤔 Strategy Gap    | Low efficiency + High effectiveness  |
| ❌ Disconnected    | Low efficiency + Low effectiveness   |

---

### 🧠 AI Team Coach

**For Admin/Manager** - Available in the Dashboard

Click **✨ Get Coaching Tips** to receive AI-powered insights:

#### What You Get

| Output                | Description                                                                                       |
| --------------------- | ------------------------------------------------------------------------------------------------- |
| **Health Grade**      | A-F grade with overall team health score                                                          |
| **5 Dimensions**      | Scores for Productivity, Deadline Discipline, Strategic Alignment, Workload Balance, and Momentum |
| **Detailed Insights** | Specific observations and recommended actions per dimension                                       |
| **Top 3 Priorities**  | What to focus on this week                                                                        |
| **Quick Wins**        | Easy fixes for immediate impact                                                                   |
| **Risk Alert**        | Critical issue to monitor                                                                         |

The AI analyzes your team's data including:

- Member progress distribution
- Deadline health (overdue/at-risk tasks)
- Key Result status and confidence scores
- Data hygiene (update frequency)

**Language-aware**: Responds in the same language as your OKR data.

---

### 📄 Reports

Access via **Daily Report** or **Weekly Report** buttons.

#### Report Contents

- Work log with time spent per task
- Time distribution by objective
- Key Result status summary
- Deadline status column

#### PDF Export

Click **📄 Export as PDF** to generate a formatted report.

---

## 🔒 Role Permissions

| Feature                 |  Admin   | Manager  |       Member        |
| ----------------------- | :------: | :------: | :-----------------: |
| Manage Users & Cycles   |    ✅    |    ❌    |         ❌          |
| View All Teams          |    ✅    |    ❌    |         ❌          |
| Team Dashboard          |    ✅    |    ✅    |         ❌          |
| AI Team Coach           |    ✅    |    ✅    |         ❌          |
| Create Goals/Objectives |    ✅    |    ✅    |         ❌          |
| Create Tasks            |    ✅    |    ✅    |         ✅          |
| Use Timer               | ✅ (Own) | ✅ (Own) | ✅ (Own + Assigned) |
| Edit Own Items          |    ✅    |    ✅    |         ✅          |
| Edit Others' Items      |    ❌    |    ❌    |         ❌          |

> **Note**: Only the **Owner** (creator) can edit/delete an item.

---

## 🛠️ Installation

### Prerequisites

- Python 3.9+
- wkhtmltopdf (for PDF export) - [Download](https://wkhtmltopdf.org/downloads.html)

### Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd okr

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install --require-hashes -r streamlit_app/requirements.txt

# 4. Configure secrets (optional - for AI features)
# Create streamlit_app/.streamlit/secrets.toml:
# ALLOW_EXTERNAL_AI = true  # set false to disable outbound AI calls
# AI_PROVIDER = "gemini"  # or "openai_compatible"
# GEMINI_API_KEY = "your-api-key"  # required for gemini provider
# AI_BASE_URL = "http://localhost:11434"  # required for openai_compatible provider
# AI_MODEL = "llama3.1"  # required for openai_compatible provider
# [database]
# url = "postgresql+psycopg2://user:pass@host:5432/okr"

# 5. Run the app
streamlit run streamlit_app/app.py

# Optional: verify AI provider configuration/connectivity
python streamlit_app/scripts/ai_provider_health_check.py
```

---

## 📂 Architecture

| Component | Technology                                   |
| --------- | -------------------------------------------- |
| Frontend  | Streamlit + Plotly + streamlit-agraph        |
| Styling   | Vanilla CSS + Vazirmatn font                 |
| Auth      | bcrypt password hashing                      |
| Database  | SQLModel + Supabase PostgreSQL               |
| Storage   | Supabase PostgreSQL (single source of truth) |
| AI        | Provider abstraction (Gemini or OpenAI-compatible local/self-hosted) |
| PDF       | pdfkit (local) / PDFShift (cloud)            |

---

## 🏗️ Project Structure

The codebase is organized modularly to separate concerns across the UI, business logic, and data layers:

- **`streamlit_app/app.py`**: Main authenticated application entrypoint.
- **`streamlit_app/login_app.py`**: Login-first launcher entrypoint used by `run_app.bat`.
- **`streamlit_app/src/`**:
  - **`ui/`**: Streamlit UI modules (`components.py`, `dialogs.py`, `visualizations.py`, `styles.py`).
  - **`services/`**: Integrations and output services (AI, PDF, HTTP client).
  - **`domain/`**: Focused business-rule modules (authorization, analytics).
  - **`crud.py`**, **`models.py`**, **`database.py`**: Core app facade, data model, and persistence layer.
- **`streamlit_app/src/utils/`**: Shared utility helpers used across app layers.
- **`streamlit_app/alembic/`**: Database migration environment and versions.
- **`tests/`**: Automated regression and performance-path tests.
- **`docs/`**, **`deploy/`**: Operations and deployment assets.

---

## 🆕 Recent Updates

### 🤝 Unified Collaboration

- **Task Assignment**: Managers can assign tasks to specific team members.
- **Shared Inbox**: Members have a dedicated "Assigned by Manager" inbox for incoming tasks.
- **Collaborative Timer**: Members can track time on tasks assigned by their manager.
- **Enhanced Visibility**: Task assignees are clearly visible on cards and in the inspector.

### Supabase-Only Data Architecture

- **Supabase PostgreSQL**: All app data uses Supabase as the single source of truth.
- **No local database fallback**: Runtime persistence is centralized and migration-driven.

### AI Team Coach

- Get personalized coaching tips from AI in the dashboard
- Analyzes 5 dimensions: Productivity, Deadlines, Strategy, Workload, Momentum
- Provides top priorities, quick wins, and risk alerts
- Beautiful health grade card with color-coded scores

### Deadline Feature

- Set deadlines on tasks with date picker
- Automatic health status calculation (🟢🟡🔴)
- Deadline warnings in AI analysis
- Dashboard metrics for overdue/at-risk tasks

### Enhanced Dashboard

- Team member filtering for Admin/Manager
- Progress breakdown by team member
- Deadline health visualization per member
- Overdue tasks list with owner display

---

_Built for excellence in strategic alignment and execution tracking._

---

## Developer Workflow (Fast Loop)

### Local setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install --require-hashes -r streamlit_app/requirements-dev.txt
pip install pre-commit
pre-commit install
```

### Refresh lock files

```bash
python -m pip install --upgrade pip pip-tools
python -m piptools compile streamlit_app/requirements.in --resolver=backtracking --generate-hashes --strip-extras --pip-args="--python-version 3.11" --output-file streamlit_app/requirements.txt
python -m piptools compile streamlit_app/requirements-dev.in --resolver=backtracking --generate-hashes --strip-extras --pip-args="--python-version 3.11" --output-file streamlit_app/requirements-dev.txt
```

### Verify quality locally

```bash
pre-commit run --all-files
# Runs Documentation HQ link checks + targeted Ruff + targeted Mypy hooks
python scripts/check_docs_hq_links.py
python -m ruff check streamlit_app/src/crud.py streamlit_app/src/utils/deadline_utils.py streamlit_app/scripts/perf_hotpaths.py tests/test_deadline_utils.py tests/test_performance_hotpaths.py --select E9,F63,F7,F82
python -m ruff format --check streamlit_app/src/crud.py streamlit_app/src/utils/deadline_utils.py streamlit_app/scripts/perf_hotpaths.py tests/test_deadline_utils.py tests/test_performance_hotpaths.py
python -m mypy --ignore-missing-imports streamlit_app/src/utils/deadline_utils.py streamlit_app/scripts/perf_hotpaths.py
python -m pytest -q
```

### Benchmark hot paths

```bash
python streamlit_app/scripts/perf_hotpaths.py
```

See `performance.md` for current baselines and budgets.
