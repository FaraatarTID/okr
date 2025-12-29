# OKR Tracker 🚀

A powerful Streamlit application for managing Objectives and Key Results (OKRs), featuring multi-user support, role-based access, AI-driven strategic analysis, and deadline tracking.

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
pip install -r streamlit_app/requirements.txt

# 4. Configure secrets (optional - for AI features)
# Create streamlit_app/.streamlit/secrets.toml:
# GEMINI_API_KEY = "your-api-key"

# 5. Run the app
streamlit run streamlit_app/app.py
```

---

## 📂 Architecture

| Component | Technology                                                             |
| --------- | ---------------------------------------------------------------------- |
| Frontend  | Streamlit + Plotly + streamlit-agraph                                  |
| Styling   | Vanilla CSS + Vazirmatn font                                           |
| Auth      | bcrypt password hashing                                                |
| Database  | SQLModel (SQLite) + **Google Sheets (Unified Single Source of Truth)** |
| Storage   | **Write-Through Caching** (Sheets Master -> MySQL/SQLite Cache)        |
| AI        | Google Gemini API                                                      |
| PDF       | pdfkit (local) / PDFShift (cloud)                                      |

---

## 🆕 Recent Updates

### 🤝 Unified Collaboration

- **Task Assignment**: Managers can assign tasks to specific team members.
- **Shared Inbox**: Members have a dedicated "Assigned by Manager" inbox for incoming tasks.
- **Collaborative Timer**: Members can track time on tasks assigned by their manager.
- **Enhanced Visibility**: Task assignees are clearly visible on cards and in the inspector.

### ☁️ Unified Data Architecture

- **Google Sheets Master Data**: All app data uses Google Sheets as the single source of truth.
- **Resilient Sync**: Automatic write-through caching ensures data safety and offline resilience.

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
