# OKR vs BAU Boundary Guide
Documentation HQ: [README](../README.md)

This guide defines a strict boundary between strategic OKR work and Business as Usual (BAU) operations.

## Introduction (Read First)

This system exists because conventional management and OKRs solve different problems:
- Conventional management keeps operations reliable (delivery, deadlines, SLA, routine execution).
- OKR management changes system performance (new capabilities, measurable KPI baseline movement).

If both are mixed in one bucket, leadership gets activity noise instead of strategy signal.

Typical failure when mixed:
1. Teams look busy, but baseline KPIs do not change.
2. Deadline completion is mistaken for strategic progress.
3. Managers cannot tell whether results came from real change or routine effort.

What this "sophisticated boundary" actually does:
1. Preserves BAU discipline: BAU tasks still have owners, deadlines, and tracking (Odoo/ticketing/paper).
2. Protects OKR integrity: only change work with hypothesis and KPI delta counts as OKR evidence.
3. Improves decisions: investment discussions use true change outcomes, not throughput volume.

If you remember one sentence:
- BAU keeps the engine running; OKR upgrades the engine.

Why this matters:
- OKRs are for changing performance systems.
- BAU is for running current systems reliably.
- Mixing BAU into OKRs creates false progress and weak strategy execution.

Memory rule for everyone:
- `Keep service running` = BAU.
- `Change KPI baseline` = OKR.
- Deadline, urgency, or manager pressure do not convert BAU into OKR.
- This policy does not require BAU data entry in the app.

## 1. Non-Negotiable Rule

- Do not place routine operating work inside OKRs.
- If work would still happen exactly the same without the Objective/KR, it is BAU.
- BAU should be measured with operational KPIs, not strategic KR attainment.

### 1.1 10-Second Dummy Check (Use Before `SHIFT`)

Ask these in order:
1. Would this still be assigned every week if no OKR existed?
   - Yes -> BAU.
2. Can I state a KPI movement with a timebox (from A to B by date)?
   - No -> BAU.
3. Is the evidence a KPI baseline shift (not just activity volume)?
   - No -> BAU.

## 2. Definitions

BAU work:
- Repeating operational activities needed to keep current service levels.
- Predictable, runbook-driven, and throughput-oriented work.
- Examples: daily ticket triage, routine approvals, standard reporting, recurring maintenance.

OKR work:
- Deliberate change initiatives expected to move a baseline KPI.
- Requires hypothesis, experiment, and learning loop.
- Examples: reduce ticket inflow via self-service redesign, cut incident recurrence via root-cause elimination.

### 2.1 Language Cue Card (Fast Filter)

| Usually BAU wording | Usually OKR wording |
| --- | --- |
| keep, run, handle, monitor, follow up, close tickets | reduce, increase, eliminate, redesign, automate, re-architect |
| "do X every day/week" | "move KPI from A to B by date" |
| "on-time completion" | "baseline improvement" |

### 2.2 Objective vs KR Boundary (Inside OKR Lane)

- Objective = strategic outcome state for the cycle ("what should be different").
- KR = measurable proof line for that objective ("how we verify change").

Quick split rule:
- If it is one metric delta with time boundary (`A -> B by date`), write it as a KR.
- If it is a broader outcome that needs multiple indicators, write it as an Objective.
- If it is an action step, keep it as initiative/task, not Objective/KR wording.

## 3. The `SHIFT` Test (Fast Classification)

Use this for every proposed KR task or check-in narrative:

| Letter | Question | BAU signal | OKR signal |
| --- | --- | --- | --- |
| `S` | **System change**: Does this change how work is done? | No process/capability change | New workflow/capability/process introduced |
| `H` | **Hypothesis**: Is there a falsifiable prediction? | No testable expectation | Clear "if we do X, KPI Y should change by Z" |
| `I` | **Insight creation**: Will this generate reusable learning? | No new learning; just execution | Measurable learning that informs next cycle |
| `F` | **Frequency pattern**: Is this recurring regardless of strategy? | Recurs weekly/daily by default | Time-boxed intervention tied to objective |
| `T` | **Target delta**: Is a KPI baseline shift expected? | Maintains current level only | Moves KPI baseline materially |

Decision:
- If `S/H/T` are mostly "No" and `F` is "Yes": classify as BAU.
- If `S/H/T` are "Yes" and work is time-boxed: classify as OKR.
- If uncertain: run as a short experiment; if no baseline KPI movement, release it to BAU.

## 4. BAU Release Workflow (Member + Manager)

Use this every week during check-in/review:

1. Member logs BAU candidates in an external governance artifact (meeting notes/release log), not in app check-in comments.
2. Manager reviews candidates in weekly governance.
3. Manager decides one of:
   - `RELEASE_TO_BAU`: remove from KR plan and track in operations system/KPI board.
   - `CONVERT_TO_OKR_CHANGE`: rewrite as change initiative with hypothesis + target delta.
   - `KEEP_IN_OKR`: only if strategic change criteria are explicitly met.
4. Record decision in a BAU release log (template below).
5. Review contamination trend monthly.

Template:
- `docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md`

### 4.1 Dual-Track Weekly Check-In Output (Required)

Weekly check-in should produce two separate outputs:

1. Strategic lane (OKR):
   - KR check-ins, hypothesis updates, and change initiatives.
   - Only this lane can influence OKR progress interpretation.
2. Operational lane (BAU):
   - BAU assignments with owners and deadlines.
   - Track in an operations system (for example Odoo ERP, ticketing/project tool, or paper log).
   - This lane does not count as KR attainment.

Non-negotiable separation rules:
- BAU deadlines are valid and important, but they remain operational commitments.
- BAU assignment completion must not be used as KR score evidence.
- If a BAU project starts changing KPI baseline materially, reclassify it into OKR lane explicitly.

Required weekly separation format (external artifact only; not an in-app field):
- Strategic lane section: `<change statement + KPI delta>`
- Operational lane section: `<operational task + owner + deadline + external system reference>`
- Any unclassified item is invalid until placed in one lane.

Implementation note:
- Current product does not enforce a dedicated BAU flag at the data model level.
- Teams should keep BAU classification/release evidence in external manager/admin governance artifacts.
- KR check-in forms remain for KR metrics/learning-loop data, not BAU classification.

## 5. Rewrite Patterns (From BAU to True OKR)

| Weak (BAU disguised as KR) | Strong (Strategic KR) |
| --- | --- |
| "Handle daily support tickets quickly." | "Reduce incoming support tickets per active user by 30% through self-service and defect elimination." |
| "Run weekly ops report." | "Cut report preparation lead time by 70% via automated data pipeline." |
| "Keep incidents low." | "Reduce repeat incident rate by 50% by eliminating top 3 root causes." |

## 6. Governance Metrics (Detect Contamination Early)

Track these at manager/admin review:

- BAU contamination rate:
  - `BAU-classified tasks linked to KRs / total KR-linked tasks`
- Strategic change ratio:
  - `KR tasks with explicit hypothesis / total KR tasks`
- BAU release cycle time:
  - `time from candidate logging in external governance artifact to manager decision`

Recommended policy thresholds:
- BAU contamination rate should trend toward `0` in mature teams.
- Every active Objective should have at least one KR with explicit hypothesis + target delta.

## 7. Role Responsibilities

Member:
- Flag BAU candidates early in external governance notes/logs.
- Avoid presenting throughput-only work as strategic progress.

Manager:
- Enforce boundary decisions weekly.
- Rewrite weak KRs into system-change KRs.

Admin/Transformation lead:
- Audit BAU contamination trends.
- Coach teams that repeatedly mix BAU and OKRs.

## 8. Anti-Patterns (Block Immediately)

- Counting raw ticket throughput as KR progress.
- Creating Objectives that describe steady-state operations.
- Reporting activity volume without outcome delta.
- Leaving routine run tasks under strategic KRs for multiple cycles.

## 9. Minimal Policy for Every New Cycle

Before activating Objectives/KRs:
1. Run `SHIFT` test for top KR initiatives.
2. Remove or release BAU items.
3. Confirm each KR has measurable strategic delta.
4. Capture decisions in BAU release log.


