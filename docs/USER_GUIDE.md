# User Guide: The Master Anthology

Documentation HQ: [README](../README.md)

This guide provides authoritative instructions for using the OKR platform, strictly aligned with the features, labels, and models defined in the codebase. It maps the 90-day quarterly program to literal UI workspaces and technical workflows.

---

## 1. Technical Framework: Leading vs. Lagging Indicators

The system architecture distinguishes between two primary data classes:

### A) Leading Indicators: Tasks (Leaf Nodes)

Stored in the `task` table, these are the actionable units of work.

- **Literal Capability**: You control these through the **Focus Task** page.
- **Data Impact**: Progress on tasks is the primary driver for all higher-level percentage calculations.

### B) Lagging Indicators: Objectives & Goals

Stored in the `objective` and `goal` tables, these represent the cumulative success of your tasks.

- **Literal Capability**: These are visualized in the **Atlas Map** (treemap).
- **Data Impact**: These values are "Lagging" because they only change once the underlying tasks reach a `DONE` status.

**The Golden Execution Rule**: Focus on the **Focus Task** (Leading) to move the **Atlas Map** (Lagging) status from gray/red to blue.

---

## 2. Core Workspace: The Atlas Interaction Model

The UI is split into a Control-plane and a Work-plane as defined in the system architecture.

### A) The Focus Map (Control-plane)

The primary visual overview of the `Cycle`.

- **Status Grounding**: Encodes urgency into three literal categories:
  - `Needs care`: Incomplete nodes with <40% progress or overdue deadlines.
  - `On track`: Incomplete nodes with >70% progress and healthy deadlines.
  - `Complete`: Nodes where `progress == 100`.
- **Interaction**: Clicking a node in the treemap updates the `atlas_selected_ref` and opens the **Inspector**.

### B) The Commit Spotlight (Work-plane)

Located within the **Focus Map**, this is the single dominant action area for time tracking.

- **Sprint Presets**: Support for `25m`, `50m`, and `Custom` timer commitments.
- **Sticky State**: The `atlas_focus_task_ref` remains persistent across navigation until the timer is stopped.

### C) The Inspector (Deep Context)

The right-hand sidebar optimized for depth.

- **Technical Capability**: Contains the full description, owner details, and the **Magic Wand (AI Analysis)**.
- **Edit Loop**: All metadata mutations (Title, Deadline, Weight) are performed here.

---

## 3. The 90-Day Quarterly Program (Technical Roadmap)

Mastering a 13-week `Cycle` requires using the following tools in sequence:

### Phase 1: Planning & Seeding (Weeks 1-2)

1. **Cycle Selection**: Ensure the correct `active_cycle_id` is selected in the Sidebar.
2. **Atlas Seeding**: Create `Goal`, `Objective`, and `KeyResult` nodes to build the hierarchy.
3. **Task Definition**: Populate `Key Results` with `Tasks`. Use the **Magic Wand** to suggest tactical task lists.
4. **Instruction**: Every task MUST be a child of a `Key Result` to contribute to the cycle's progress calculations.

### Phase 2: Execution & Momentum (Weeks 3-10)

1. **Focus Mode**: Start every day in the **Focus Task** page. Use **Suggested Next** to rank tasks by urgency and effort.
2. **Timer Commitment**: Use the **Commit Spotlight** to start a `WorkLog`. Log your minutes to update the `total_time_spent` field.
3. **Weekly Ritual**: Every Thursday/Friday, open the **Weekly Ritual** dialog. This tool identifies `Key Results` needing check-ins and allows you to update `current_value` and `confidence_score`.
4. **Mid-Cycle Audit (Week 7)**: Use the **Strategic Dashboard** to identify nodes in the `Needs care` state.

### Phase 3: The Sprint (Weeks 11-12)

1. **Needs Care Management**: Focus exclusively on nodes flagged as `Needs care` in the Atlas.
2. **Check-in Frequency**: Increase the frequency of `CheckIn` entries to maintain real-time visibility in the **Leadership Dashboard**.

### Phase 4: Reflection & Clean Slate (Week 13)

1. **RetroBox**: Use the **RetroBox** dialog to submit a `Retrospective` entry for the week. Document what worked and what didn't.
2. **Clean Slate Protocol**: Finalize all pending tasks. Use the Admin-level `Cycle Management` to deactivate the cycle and prepare for the next period.

---

## 4. UI Navigation & Hierarchy

- **Sidebar (Nav)**:
  - **Focus Task**: Daily landing zone for execution.
  - **Home / OKRs**: Returns to the root of the Atlas navigation stack.
  - **Insights/Reports**: Access to `Weekly Report`, `Daily Report`, `Weekly Ritual`, `RetroBox`, `Project Timeline`, and `Strategic Dashboard`.
- **Top Header**: Cycle Selector and the **Suggested Next** AI priority tool.
- **Atlas Map**: Supports both `full scope` and `branch lens` views.

---

## 5. Status & Legend: The Ground Truth

- 🟢 **On track**: Progressing normally.
- 🟡 **Warning**: Progress or deadline risk detected.
- 🔴 **Needs care**: Critical risk or high lag.
- 🔵 **Complete**: Task or Goal is finished.
- ⚪ **Pending / Draft**: The node is not yet active.

### 🔄 The Lifecycle Filter

In the platform, nodes move through a formal lifecycle: `DRAFT` -> `ACTIVE` -> `GRADING` -> `ARCHIVED`.

- **Instruction**: Nodes in the **DRAFT** state are ignored by the progress rollup engine. You must move your objectives to **ACTIVE** for your work to contribute to the Goal or Cycle total.

---

## 6. Organizational Alignment (Cross-Goal Dependencies)

While the default view for OKRs is a tree, the organization is often a web. The Platform supports **Vertical and Horizontal Alignment** via the Alignment Graph.

### High-Foresight Linkage

Within the Objective Inspector, you can manage "Supports" links:

- **Vertical Alignment**: Your objective supports a high-level organizational Goal or another Objective.
- **Horizontal Alignment**: Your objective relates to a peer department's objective.

### Directional Accountability

The system ensures all links are one-way and acyclic. You can visualize these dependencies to see exactly who is relying on your success, and whose success you are built upon.

---

## 7. Precision Scoring & Weighted Rollups

Not all Key Results are created equal. The platform provides two scoring modes for Objectives:

- **Unweighted (Standard)**: Every KR contributes equally to the 100% progress goal.
- **Weighted (Advanced)**: You assign a specific **Weight** (multiplier) to each KR. An "Objective Weight" of 2.0 makes that KR twice as important as a 1.0 weight for the parent's progress.

---

### "Why is my KR progress at 0%?"

**Literal Answer**: Review the `Task` child nodes. Progress only rolls up if the children belong to the `DONE` status or have their `progress` field updated manually.

### "How is the AI score calculated?"

**Literal Answer**: The `Effectiveness Score` is a comparison of your `Task` title/description against the parent `Key Result` and `Objective` metadata, processed through the `ai_service.py` logic.

---

_Grounded in the codebase. Built for precise execution._

---

## 7. The Psychology of Execution: Small Wins & Momentum

Real progress is rarely linear. This system is designed around the **Psychology of Small Wins**.

- **Inertia Breaking**: By focusing on a single `Task` in the **Commit Spotlight**, you bypass the cognitive load of a massive `Objective`. Every time you stop the timer and log progress, you trigger a micro-momentum boost.
- **Visual Validation**: The shifting colors on the **Focus Map** (from red to yellow to green) are not just data; they are psychological signals. Building a "Green Branch" creates a sense of mastery that fuels the next sprint.

### B) Deep Work vs. Shallow Work

Use the **Timer** as a ritualistic boundary to protect your cognitive resources.

- **The Boundary**: When you start a `50m` timer, you are declaring an "Uninterrupted Research/Execution Zone."
- **The Odometer**: Treat the `total_time_spent` metric like an odometer on a professional vehicle. Shallow work (emails, meetings) should ideally not be logged here; keep this space for the deep efforts that move the `Key Result` percentage.

### C) The Organizational North Star: Your Hierarchy GPS

Understanding the hierarchy is like reading a map. If you are lost, use these analogies:

- **The Family Tree**: The `Objective` is the Grandparent (The Legacy). `Key Results` are the Parents (The Support). `Tasks` are the Children (The Daily Effort). If the children aren't moving, the legacy is stalled.
- **The GPS**: The **Atlas Workspace** is your 90-day work GPS. It doesn't just show you where you are; it shows you the "Traffic Jams" (Nodes flagged as **Needs care**).

### D) Decision Matrix: "AI-Led vs. Human-Led Priority"

How do you decide what to work on today? Use this matrix for the **Focus Task** page:

| Scenario          | Recommendation | Action                                                                                                               |
| :---------------- | :------------- | :------------------------------------------------------------------------------------------------------------------- |
| **Overwhelmed**   | AI-Led         | Open the Header and follow the **Suggested Next** list. It ranks by urgency and session history.                     |
| **High Strategy** | Human-Led      | Browse the **Atlas Map** for nodes in the "On track" state and pick one that needs a final push.                     |
| **Crisis (Red)**  | Hybrid         | Filter for **Needs care** in the Map, then use the **Magic Wand** in the Inspector to find the fastest tactical fix. |

---

## 8. The Ultra-Roadmap: Your 13-Week Success Sequence

This is a comprehensive, week-by-week mentorship path to ensure you win the quarter.

### Phase 1: The Architect (Weeks 1-2)

_Goal: Build a high-clarity map of the future._

- **Step 1**: Use the **Magic Wand** in the Inspector to decompose every `Objective` into 3-5 quantitative `Key Results`.
- **Step 2**: Ensure every KR has a clear `target_value`. A goal without a number is just a wish.
- **Step 3**: Launch your first "Momentum Sprint" (25 min) to prove the system works.

### Phase 2: The Execution Engine (Weeks 3-10)

_Goal: Maintain high-velocity "Deep Work" rituals._

- **Daily**: Use the **Commit Spotlight** to pick one "Frog" (hardest task) and eat it first thing in the morning.
- **Weekly**: Complete the **Weekly Ritual**. Update your `current_value` metrics literal evidence from your work logs.
- **Mid-Point (Week 7)**: Perform a "Tactical Audit." Use the **Inspector** to identify KRs that are stalled. Ask the AI: _"What is the primary technical blocker here?"_

### Phase 3: The Final Sprint (Weeks 11-12)

_Goal: Burn down the red nodes and secure the wins._

- **Action**: Focus exclusively on **Needs care** nodes. Use the "Rescue Plan" (Section 9) for anything below 60% progress.
- **Negotiation**: If a KR is impossible to finish, use the **Weekly Ritual** to note the "Lessons Learned" and set a more realistic target for the next cycle.

### Phase 4: The Clean Slate (Week 13)

_Goal: Archive the past and prepare for the next ascent._

- **Action**: Complete the **RetroBox** entry for the entire cycle. Summarize your "Effectiveness Journey."
- **Cleanup**: Archive completed tasks to ensure the **Atlas Map** is ready for the next 90-day initialization.

---

## 9. The "Failing KR" Rescue Plan (Advanced)

If a Key Result is flagged as **Needs care** (Red) or stuck in "The Perfectionism Trap" (lots of effort, zero progress):

1. **Analytical Audit**: Select the KR, open the Inspector, and click the Magic Wand. Request a "Gap Analysis" between your tasks and the KR metric.
2. **The "Micro-Slice" technique**: If a task feels too big, slice it into 15-minute chunks. Seeing 3 small "Complete" checkmarks breaks the perfectionist block.
3. **Admin Escalation**: Use the **Weekly Ritual** to move your `confidence_score` to 2/10. This is a technical signal to your Manager that you need a resource re-allocation or a tactical pivot.
4. **Spotlight Blitz**: Dedicate a full 3-hour "Deep Work" block in the **Commit Spotlight** to a single KR to force it out of the stagnant phase.

---

## 10. Pro-Tips for Mastery

- **The "Invisible" Boundary**: If the timer is red and running, your focus is a professional asset. Protect it.
- **Semantic Clarity**: The smarter your Task titles, the better the **Effectiveness Score**. Use verbs and outcomes.
- **The Odometer Philosophy**: Every minute logged in `total_time_spent` is a brick in the wall of your professional reputation. Build with quality.

---

## 11. The OKR-Scrum Hybrid Masterclass: Tactical Playbook

This section integrates the aspirational power of **OKRs** with the execution discipline of **SCRUM**. Use this step-by-step playbook to manage your 90-day cycle as a series of disciplined sprints.

### A) The Sprint Lifecycle (2-Week Rhythms)

While your OKRs are quarterly (13 weeks), your execution happens in **2-week Sprints**.

1. **Week 1-2**: Launch Sprint. Focus on "low-hanging fruit" KRs to build momentum.
2. **Week 3-10**: The Core Sprints. High-velocity execution of complex tasks.
3. **Week 11-13**: The Closure Sprint. Aggressive focus on finishing "Needs care" nodes.

### B) Ritual 1: Sprint Planning (Every 2nd Monday)

_Goal: Groom the backlog and commit to the next 10 days._

1. **Step-by-Step Step 1**: Open the **Inspector** tab in the Atlas Workspace. Select your primary `Key Result`.
2. **Step-by-Step Step 2**: Review the child `Tasks`. This is your "Sprint Backlog."
3. **Estimation Masterclass**: Ensure every `TODO` task has an `estimated_minutes` value.
   - _Rule of Thumb_: If a task is >240m (4 hours), it is a "Block" of work, not a task. Slice it into smaller items!
4. **The Commitment**: Drag/Select 3-5 tasks for the upcoming week. Use the **Magic Wand** to ask: _"Assess the feasibility of these tasks for a 40-hour work week."_

### C) Ritual 2: The 120-Second Daily Standup (Every Morning)

_Goal: Sync with yourself and the system._

1. **Step-by-Step Step 1**: Open the **Focus Task** page. Look at the **Suggested Next** list.
2. **Step-by-Step Step 2**: Select your "Frog" (the highest priority task) and click **Commit Task**.
3. **Step-by-Step Step 3**: Review your **Focus Map**. Are you building a "Green Branch"? If your branch is red, today's goal is strictly "Color Restoration" (Fixing red nodes).
4. **Action**: Set the **Timer** for a 25m or 50m block and start.

### D) Ritual 3: Sprint Review & Demo (Every 2nd Friday)

_Goal: Demonstrate literal progress to your manager/team._

1. **Update Values**: Open the **Weekly Ritual** dialog. Move your `current_value` sliders based on the work you delivered.
2. **The "Demo" Logic**: Your "Demo" is your **WorkLog history**. Ensure your summaries are descriptive (e.g., _"Successfully deployed auth middleware"_ instead of _"Work done"_).
3. **AI Sync**: Click the manual sync button. Watch your percentage move. This is the literal "Burn-down" of your organizational debt.

### E) Ritual 4: Sprint Retrospective (Bi-Weekly)

_Goal: Improve the "HOW" of your work._

1. **Open RetroBox**: Select the cycle and enter your reflection.
2. **Efficiency vs. Effectiveness**: Look at your **Effectiveness Score**. If it is low despite high hours, ask in the RetroBox: _"Am I doing busy-work? How can I align my next sprint closer to the parent Objective?"_
3. **The Pivot**: If you identified a "Strategic Gap," add a new task immediately for the next sprint to bridge that gap.

### F) Vertical Alignment: The "Zero-Waste" Protocol

In a high-performing SCRUM-OKR hybrid, every click must add value.

- **Rule of 3**: Every `Task` should contribute to at least 3% of a `Key Result`. If it contributes 0%, it is "Waste" and should be deleted or moved to an experimental cycle.
- **The Traceability Link**: Whenever you finish a task, look at the **Atlas Workspace**. If the parent node didn't change color, use the **Inspector** to verify if the "Target Value" for the KR is set too high.

---

_The Agile Compendium. Master the mechanics, win the quarter._

---

## 12. Technical Proficiency Masterclass: Components & Integrity

This section provides expert-level guidance for every interaction in the system. Use these steps to ensure your digital workflow matches the precision of the underlying code.

### A) Deep-Dive: The Atlas Inspector

The **Inspector** is your primary tool for "Surgical Correction" of your OKRs.

1. **The Magic Wand (Decomposition Logic)**:
   - _Action_: Select a sub-node and click the Magic Wand.
   - _Technical Step_: Choose "Decomposition." The AI doesn't just "chat"; it performs a RAG-based analysis of the parent `Objective` to ensure every new `Task` it suggests is technically aligned with the metric you need to move.
2. **The Notes Field (Contextual Memory)**:
   - _Expert Tip_: Use the `Notes` field in the Inspector to record "Strategic Blockers." The AI reads these notes during the **Strategic Gap Analysis** to identify why you are stuck.
3. **The Parent Link (Traceability)**:
   - _The Step_: Always check the `parent_id` link in the Inspector. If a task isn't linked to a KR, its progress is "Ghost Progress"—it won't help you win the quarter.

### B) Deep-Dive: The Focus Task (Timer Logic)

Precision timing is the foundation of the **Effectiveness Score**.

1. **The Hand-Off**: When you switch from one task to another, stop the first timer _before_ starting the second. The system calculates `total_time_spent` as a contiguous block. Overlapping timers create "Data Friction."
2. **The Error Correction**: If you forget to stop the timer, use the **WorkLog** dialog (in the next section) to manually adjust the minutes.
3. **Commit Spotlight**: Use the "Focus" button to hide all other branches of the Atlas tree. This reduces visual noise and triggers a "Deep Work" state in the browser session.

### C) Deep-Dive: Weekly Ritual (Metric Synchronization)

The **Weekly Ritual** is where you transform effort into organizational proof.

1. **The Progress Slider**: When you move the `current_value` slider, the system doesn't just update a number. It triggers a `SyncService` call that recalculates the health (color) of every parent node up to the root.
2. **The Evidence Field**: Don't just summarize. Record **Literal Outcomes** (e.g., "Merged 14 PRs", "Resolved 3 customer tickets"). High-density summaries result in a +15% boost to your **AI Sentiment Score**.

### D) The "Semantic Integrity" Protocol

The AI is a "Literal Engine." To double your **Effectiveness Score** accuracy, follow this naming convention for every task:

- **Format**: `[Action Verb] + [Quantitative Metric] + [Target Outcome]`
- **Weak Title**: _"Work on documentation"_
- **Elite Title**: _"Expand USER_GUIDE by 500 words to improve Onboarding Velocity"_
- **Result**: The AI will correctly identify this as a "High Impact" task in your **Suggested Next** list.

---

_The Expert's Compendium. Technical precision. Tactical mastery._

---

## 13. Master’s Playbook: Strategic Foresight & Resilience

This final section transforms you from a user into a **Master of Execution**. It provides the foresight needed to navigate complex organizational changes and the resilience to protect your data.

### A) The Strategic Forecast: Mid-Quarter Pivot

In a volatile environment, your OKRs may need to change mid-quarter.

1. **Step 1: Identifying the Shift**: Open your **Suggested Next** list. If the AI is recommending tasks that no longer align with your department's new priorities, do not just "ignore" them.
2. **Step 2: The Strategic Pivot**: Open the **Inspector** for the outdated Objective. Click **Edit** and update the `description` with the new strategic context.
3. **Step 3: AI Re-Alignment**: Click the **Magic Wand** -> **Refine**. The AI will now re-scan your entire 90-day plan and suggest a "Pivot Path" that keeps your momentum high despite the change in direction.

### B) The Progress Gap Analysis (Burnout Prevention)

Execution isn't just about moving fast; it's about sustainable velocity.

1. **The Trend Check**: Every Sunday, open the **Inspector** for your primary Objective. Look at the **Trend Chart**.
2. **The Warning Sign**: If your `total_time_spent` is increasing while your `Effectiveness Score` is decreasing, you are in the **Burnout Zone**.
3. **The Step-by-Step Recovery**:
   - Manually "Freeze" (Archival) 2 sub-tasks.
   - Use the **Focus Map** to isolate only the 3% of tasks that move the needle.
   - Communicate this data to your manager using the **Leadership Dashboard** to justify a scope reduction.

### C) Data-Driven Professional Confidence

Use the system's "Evidence Layer" to advocate for your career growth.

1. **The WorkLog Audit**: Once a month, open your **WorkLog History**.
2. **The Step**: Export your logs. Filter for tasks with an **Effectiveness Score** > 8.0.
3. **The Professional Portfolio**: These tasks represent your "High-Value Contributions." Use this literal evidence during your 1-on-1s to prove your strategic value beyond simple task completion.

---

_The Master of Execution. Foresight. Resilience. Data-driven growth._

---

_The Grand Compendium of Execution. Mentorship built for mastery. Grounded in the code, designed for the human._
