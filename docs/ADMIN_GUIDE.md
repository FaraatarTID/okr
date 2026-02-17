# System Administrator Guide: The Execution Guardian (Literal Alignment)

Documentation HQ: [README](../README.md)

This guide provides authoritative technical instructions for system administrators, strictly aligned with the `RBAC` models, `Cycle` management, and `AI Progress Sync` logic defined in the codebase.

---

## 1. Professional Role & Permission Model

The system enforces a strict **Role-Based Access Control (RBAC)** architecture as defined in `models.py`.

### A) User Roles & Scopes

1. **Admin (`UserRole.ADMIN`)**: Full vertical visibility. Can access the `Admin Panel`, manage `User` accounts, and override any `Goal` or `Cycle`.
2. **Manager (`UserRole.MANAGER`)**: Visibility into the `Team` dashboard for their direct reports (`manager_id` linkage). Can manage assigned OKRs.
3. **Member (`UserRole.MEMBER`)**: Execution focus. Limited to seeing/editing their own OKRs and those shared within their hierarchy.

### B) Governance Expectations

- **Naming Enforcement**: Ensure clear, quantitative naming for `Key Results` to optimize the semantic processing of the AI service.
- **Hierarchy Integrity**: Every `Task` (leaf) must be correctly linked to a `Key Result` (branch) to ensure progress rolls up accurately to the `Objective` (root).

---

## 2. Technical Administration: Quarterly Lifecycle

Admin actions are critical for the initialization and archival of 90-day cycles.

### Phase 1: Cycle Initialization (Weeks -2 to 0)

1. **Create Cycle**: Use the `Manage Cycles` dialog to create a new `Cycle` entry. Define the `start_date` and `end_date`.
2. **Identity Linkage**: Ensure every new `User` is linked to a `manager_id` and `team_id`. Without this link, the `get_leadership_metrics` query will not aggregate their effort correctly.
3. **Database Preflight**: Verify connection health to the Supabase PostgreSQL layer before the cycle launch.

### Phase 2: Core Oversight (Weeks 1-12)

1. **The Leadership Dashboard**: Use the **Strategic Dashboard** (invoking `get_leadership_metrics`) to monitor organization-wide progress, risk, and confidence scores.
2. **Progress Reconciliation**: If percentage roll-ups appear stale, invoke the **AI Progress Sync** (or `rebuild_calculation_tree`) to clear the cache and force a fresh rollup from the task table.
3. **Status Audit**: Scan for "Needs care" nodes. Use the `User Management` panel to assist managers whose teams are significantly lagging behind the expected `Cycle` timeline.

### Phase 3: Archive & Transition (Week 13)

1. **Cycle Deactivation**: Once the quarter ends, set the `active_cycle_id` to inactive.
2. **Stale Task Cleanup**: Identify tasks with zero `total_time_spent` or those older than 21 days for archival.
3. **Historical Data Sync**: Perform a final database export to ensure 90 days of execution history are securely preserved.

---

## 3. Crisis Response & Technical Sync

### Handling "Red" Dashboards

A red dashboard indicates that nodes have fallen into the `Needs care` classification (Progress < 40% or Overdue).

- **Step 1**: Check the **AI Progress Sync**. Ensure the calculated percentages reflect the most recent database commits.
- **Step 2**: Use the **Strategic Dashboard** to identify the specific `owner_id` or `team_id` responsible for the lag.
- **Step 3**: Review the `WorkLog` entries to see if effort has been logged but not yet results.

---

## 4. Disaster Recovery & Security Ethics

### A) Backup Protocols

- **Primary Persistence**: Data is stored in Supabase PostgreSQL (`database.py`).
- **Export Discipline**: Regularly use the "Export Database" feature to maintain an off-site copy of the current `Cycle`.

### B) Oversight Ethics

- **Support-First Protocol**: Access levels are designed for unblocking teams (identifying `Needs care` nodes), not for micro-surveillance.
- **Data Privacy**: Administrative access must respect the Zero-Trust architecture, only accessing `inspector` logs during troubleshooting or strategic health audits.

---

## 5. Technical Troubleshooting FAQ

### Q: "Rollup values don't match child progress."

**Answer**: This is usually a caching issue. Use the **AI Progress Sync** in the Admin panel to force a reconciliation of the `Goal` and `KeyResult` tables with the latest `Task` status.

### Q: "User role changes not taking effect."

**Answer**: User session state is cached in Streamlit. Instruct the user to perform a hard refresh (`Ctrl + F5`) to pull the updated `UserRole` from the DB.

### Q: "Cycle timelines are overlapping."

**Answer**: Check the `start_date` and `end_date` in the `Cycle` model. The system allows multiple active cycles, but ensure the UI default `active_cycle_id` is points to the current quarter.

---

## _The backbone of organizational integrity. Built for the Execution Guardian._

## 6. The Governance Mentor: Scaling & Stewardship

### A) The Governance Audit Checklist (Weekly Routine)

As an Admin, your goal is to ensure the `Cycle` remains healthy. Run this 10-minute audit every week:

1. **Orphan Objective Identification**: Search the **Atlas Map** for Objectives with 0% progress. Open them in the **Inspector** to verify if they have child Key Results.
2. **Ghost Node Cleanup**: Use the **Strategic Dashboard** to find tasks with 0 `total_time_spent` that have been open for >14 days. Suggest that the owner either archives them or commits a sprint.
3. **Identity Verification**: Ensure every new user has an assigned `manager_id`. Without this, the **Team Momentum Matrix** will have missing data points.

### B) Team Momentum Matrix: "Effort vs. Impact"

Use the **Strategic Dashboard** (driven by `get_leadership_metrics`) to categorize team health:

| Momentum Type      | Indicator                               | Admin Intervention                                                                         |
| :----------------- | :-------------------------------------- | :----------------------------------------------------------------------------------------- |
| **High Velocity**  | High `total_time_spent` + High Progress | None. Use these as a "Success Case" for other departments.                                 |
| **Busy-Work Trap** | High `total_time_spent` + Low Progress  | Review their **Effectiveness Scores**. They may be working on unaligned tasks.             |
| **The Stall**      | Low `total_time_spent` + Low Progress   | Technical/Auth blocker check. Verify if they are using the **Commit Spotlight** correctly. |

## 7. The Philosophy of Stewardship

### A) The Garden Caretaker Framing

As a System Administrator, you are not a "Police Officer"; you are a **Garden Caretaker**.

- **The Soil**: The database and server configuration.
- **The Branches**: The departmental Objectives and Key Results.
- **Your Tool**: The **Strategic Dashboard** (Your "Bird's Eye View").
  Your goal is to ensure the soil is healthy (backups) and that no branches are withering due to lack of attention (low engagement).

### B) The Ethics of Oversight

Managing an OKR system is a high-trust activity.

- **Zero-Trust Technicals**: The `RBAC` models ensure that sensitive notes remain private. However, as an Admin, you have the "Master Key."
- **Psychological Safety**: Use your oversight power to find teams in trouble, not to punish individuals. If a team's **Effectiveness Score** is low, approach with: _"The system signals a tactical bottleneck. How can we re-align resources?"_ rather than _"Why is your score low?"_

---

## 8. Enterprise-Scale Governance & Standards

### A) Global Naming Standards

To prevent the "Atlas Map" from becoming a swamp of confusing labels, enforce these standards:

- **Objectives**: Must start with an active verb (e.g., "Revolutionize," "Expand," "Stabilize").
- **Key Results**: Must contain a quantitative metric (e.g., "15% increase," "0% downtime").
- **Tags**: Use department prefixes (e.g., `TECH_`, `HR_`, `SALES_`) for easy filtering in the **Leadership Dashboard**.

### B) The "Scrum of Scrums" Protocol

The **Strategic Dashboard** serves as your organizational pulses. Run a weekly "Pulse Check":

1. **Identify Red Flags**: Filter the map for **Needs care**.
2. **Confidence Audit**: Look for users with `confidence_score` < 3/10. These are the "silent crises."
3. **Capacity Rebalancing**: If a manager has 20+ active nodes, their team is likely suffering from "Strategic Drift." Suggest moving objectives to the next `Cycle`.

---

## 9. Quarterly Governance Lifecycle (The Master Schedule)

### Phase 1: Pre-Quarter Preparation (Initialization)

- **Cycle Setup**: Define the new 90-day `Cycle`.
- **User-Manager Audit**: Ensure every new hire is assigned a `Manager`. An orphan user produces data that is invisible to the relevant dashboards.
- **Seed-Vault Backup**: Perform a manual export of the current `okr_database.db` and store it off-site before the new cycle begins.

### Phase 2: Active Quarter Stewardship (Maintenance)

- **The Friday Audit**: Every Friday, check the **Global Sync Status**. Ensure manual AI Progress Sync is running smoothly.
- **Ghost Node Detection**: Scan for objectives with zero children (Tasks). An objective without tasks is a "ghost" that provides no progress data.
- **Resource Rehearsal**: Ensure all `Admin` users know how to use the **Inspector** to manually correct status errors if a manager is unavailable.

### Phase 3: The End-Quarter "Clean Slate"

- **Closing the Cycle**: Run the **Curator's Audit**. Ensure all `Complete` nodes are celebrated in the final report.
- **Carry-Over Protocol**: Move incomplete but still relevant Objectives to the next cycle. Ensure the `current_value` is preserved.
- **Archive Verification**: Verify that finished cycles are archived correctly to maintain high performance in the Atlas visualization.

---

## 10. Disaster Recovery & Crisis Management

### A) Handling the "Red Dashboard"

If the organization's dashboard is >40% Red:

1. **Pivot to Stability**: Recommend a "Pause Week" where teams stop creating new tasks and only focus on completing current ones.
2. **Global AI Sync**: Trigger a manual "Refresh All" to ensure the data is not simply stale.
3. **Manager Alignment**: Call a meeting with the Managers of the red departments to investigate systemic hurdles (resource loss, market shifts).

### B) System Recovery Rehearsal

Don't wait for a crash. Every 30 days:

- Verify the `km_backups/` directory has fresh snapshots.
- Practice an "Import DB" action on a staging environment.
- Check the **Integrity Logs** for any `Access Denied` spikes that might indicate a configuration error in the `RBAC` definitions.

---

_The Guardian of the Organization. Precision stewardship through technical excellence._

### C) Scaling Strategies: handling Growth

As your organization grows from 10 to 100+ users:

1. **Cycle Fragmentation**: Instead of one global cycle, create Department-specific cycles (e.g., `Engineering-Q1`, `Sales-Q1`) to keep the **Atlas Map** from becoming visually over-saturated.
2. **Manager Decentralization**: Shift the first-line audit responsibility to users with the `UserRole.MANAGER` role. Training them to use the **Team Filter** in the dashboard reduces Admin bottleneck.
3. **Bulk Cleanup**: Periodically use the **AI Progress Sync** across all active cycles to ensure the organization's aggregate success score is technically accurate.

### D) Pro-Tips for System Stewardship

- **The "Single Source of Truth"**: Always defer to the `WorkLog` density as the ultimate proof of execution. If a manager claims progress but logs are empty, use the **Strategic Dashboard** to show the data discrepancy.
- **Role Audits**: Once per month, scan the User Management panel to ensure no "Member" role should actually be a "Manager" based on their team growth.
- **The "Clean Slate" Mentor**: In Week 13, guide managers through the archival of incomplete nodes. This ensures the next cycle starts with high semantic clarity for the AI.

---

## 11. Agile Enterprise Masterclass: Higher-Level Stewardship

As an Admin, you are the **Chief Scrum Master** of the organization. Your role is to remove systemic impediments that prevent teams from achieving their OKRs.

### A) Managing Organizational Impediments (Step-by-Step)

An impediment is any red node that stays red for >14 days despite "Rescue Plans."

1. **Step 1: Identify the Root**: Open the **Strategic Dashboard**. Filter by `Needs care`.
2. **Step 2: Capacity Audit**: Select the parent objective. Use the **Inspector** to check if the `estimated_minutes` of the children tasks exceeds the team's weekly capacity (e.g., >2400 mins/person).
3. **Step 3: The Administrative Pivot**: If the backlog is overloaded, manually move 30% of the tasks to the "Icebox" (TODO for next cycle). This instantly lowers the team's cognitive load and restores focus.

### B) Data-Driven Capacity Planning (Masterclass)

Use the system's "Odometer" logic to prevent burnout.

1. **Ratio Analysis**: Compare `total_time_spent` vs. `Progress %` in the dashboard.
   - _High Time / Low Progress_: Indicates heavy impediments. Step in to re-align resources.
   - _Low Time / High Progress_: Indicates "Sandbagging" (targets set too low). Suggest increasing the `target_value` for the next cycle.
2. **Predictive Balancing**: If the AI summary predicts a completion date _after_ the cycle ends, use the **Inspector** to decrease the scope or increase the team size assigned to that objective.

### C) The "Quarterly Backlog Grooming" Protocol

In Week 12, perform a global grooming session:

1. **Pruning**: Delete any tasks that have 0 minutes logged and are no longer strategically relevant. This ensures the AI's "Predicted Next" algorithm stays clean.
2. **Normalization**: Ensure all `current_value` metrics across all departments use similar scales (e.g., 0-100) to ensure the **Momentum Matrix** is visually coherent.

---

_The Agile Guardian. Scaling organizational velocity through precision stewardship._

---

## 12. Leadership Dashboard Masterclass & Error Recovery

This section documents the technical workflows for high-level organizational oversight and system correction.

### A) The Leadership Dashboard: Deep Audit (Step-by-Step)

Use the **Strategic Dashboard** to perform "Precision Mentorship" for your managers.

1. **The Team Filter (Isolation Logic)**:
   - _Technical Step_: Open the Dashboard and select a specific `Manager` from the dropdown.
   - _Audit_: Look at their team's **Distribution Chart**. If >50% of their nodes are yellow, the team is likely "Busy but not Moving."
2. **Global AI Progress Sync**:
   - _The Workflow_: If you notice a department's metrics are "Lagging" behind their actual work logs, click the **Global Refresh** button in the Admin Panel.
   - _Technical Outcome_: This triggers a batch iterate of all `KeyResults` in the active cycle, forcing the AI to re-read the latest `WorkLogs` and recalibrate the completion percentages.

### B) The "Error Recovery" Playbook (Step-by-Step)

Mistakes in the database can cause "Data Pollution" in your dashboards. Use these steps for surgical correction.

1. **Graceful Deletion of a Node**:
   - _Scenario_: A user accidentally created an objective with 10 duplicate tasks.
   - _The Step_: Select the objective in the **Atlas Workspace**, open the **Inspector**, and click **Delete**.
   - _Warning_: Deleting a parent node will recursively delete all children `Tasks`. Always verify the `Node ID` before clicking confirm.
2. **Historical WorkLog Correction**:
   - _Scenario_: A user logged 800 minutes instead of 80.
   - _The Step_: Open the **WorkLog History** for that specific Task. Click the **Edit** icon (Pencil) on the erroneous entry.
   - _The Fix_: Manually change the `duration` value and click **Save**. The dashboard health color will update on the next rerun.

### C) Technical Alignment Verification

To ensure the organization is technically healthy, perform this "Integrity Run" every 30 days:

1. **Empty Description Audit**: Use the **Inspector** to scan for Objectives with empty `description` fields.
2. **The "Description" Requirement**: The AI uses the description as the primary context for the **Suggested Next** list. An empty description lowers the AI's "Context Score" by 40%.
3. **The Fix**: Mandate that all managers provide at least 2 sentences of tactical context for every `Objective` they create.

---

_The Expert Guardian. Command the data. Master the system._

---

## 13. Master’s Playbook: System Resilience & Enterprise Troubleshooting

This final section transforms the Admin from a system maintainer into a **Guardian of Organizational Continuity**. It focuses on the technical resilience needed to protect the organization's strategic data.

### A) The System Resilience Protocol (Step-by-Step)

Data loss is the ultimate organizational impediment. Follow this protocol to ensure 100% uptime.

1. **Disaster Recovery Rehearsal**:
   - **Step 1**: Go to the Admin Panel and trigger a **Database Backup**.
   - **Step 2**: Download the `.db` file.
   - **Step 3 (The Rehearsal)**: Once every 90 days, create a "Sandbox Cycle." Upload the backup file to this cycle to verify that all nodes, work logs, and AI scores are restored correctly.
2. **Security Hygiene Audit**:
   - **The Step**: Every 30 days, filter the User Management list by `UserRole.ADMIN`.
   - **Expert Check**: If a user no longer needs administrative access, downgrade them to `MANAGER` immediately. This prevents "Privilege Creep" and protects the integrity of the Global AI Sync.

### B) Enterprise-Scale Troubleshooting (High-Stakes)

When the system behaves unexpectedly at scale, use these high-precision correction steps.

1. **Resolving "Zombie Syncs"**:
   - **Scenario**: A user reports that their progress bar hasn't moved despite numerous work logs.
   - **The Fix**: Open the **Strategic Dashboard**. Click the **Global AI Progress Sync**. If the sync hangs, check the server logs for "Vector Store Connection Timeout." Restart the server only after ensuring a backup is complete.
2. **Orphaned Task Recovery**:
   - **Scenario**: A task exists in the database but isn't visible in the Atlas Map (usually due to a deleted parent Objective).
   - **The Step**: Use the **WorkLog History** search. Locate the `Task ID`. Open the **Inspector** for that ID and manually re-assign it to an active `Key Result` to restore map visibility.

### C) The "Master Guardian" Mindset

- **Audit the Auditors**: Use the **Leadership Dashboard** to verify that managers are performing their Weekly Rituals. If ritual density is <70%, the organization's OKR health is entering the "Red Zone" regardless of actual work.
- **Continuous Alignment**: Every 90 days, initiate the **Clean Slate Protocol**. This is your most powerful tool for maintaining the "Semantic Clarity" of the organization’s long-term vision.

---

_The Master Guardian. Protecting continuity. Ensuring strategic truth._

---

_Command with precision. Scale with clarity._
