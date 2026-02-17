# AI Features Guide
Documentation HQ: [README](../README.md)

This guide documents AI behavior that is currently implemented in code (`streamlit_app/src/services/ai_service.py`, `streamlit_app/src/ui/components.py`, `streamlit_app/src/ui/dialogs.py`).

## 1. Where AI Is Available in the UI

AI is used in these places:
- `Inspector` (KR/Object analysis via `analyze_node`).
- `Weekly Ritual` step 1 (AI weekly summary generation).
- `Weekly Report` (AI executive brief generation).
- `Atlas -> Focus Map` sidebar (`AI Progress Sync` controls).
- `Leadership Insights -> Execution` (`AI Team Coach`, manager/admin).
- `Leadership Insights -> Strategy Pulse` (burnout, strategy gaps, predictive outlook, achievement portfolio PDF).

## 2. Implemented AI Capabilities

### A) Node Analysis (Magic Wand / Run Analysis)

Scope:
- Primarily for Key Results, with objective-aware context.

Typical outputs:
- `efficiency_score`
- `effectiveness_score`
- `overall_score`
- `gap_analysis`
- `proposed_tasks`
- short summary and warnings

How it is applied:
- Analysis is generated on demand.
- Results are stored in KR analysis fields.
- No autonomous structural change is applied unless user confirms follow-up actions.

### B) AI Weekly Summary

Available in:
- Weekly Ritual (week review step)
- Weekly Report

Input basis:
- Work log text
- total minutes
- completed tasks
- KR update count

Output shape:
- markdown summary
- highlights list
- focus analysis sentence

### C) AI Progress Sync in Atlas

Location:
- Focus Map sidebar under `AI` controls.

Capabilities:
- Refresh AI analysis across visible KRs.
- Optional `Apply AI overall score to KR progress`.
- Policy controls: preview mode, max delta, allow/disallow decreases.
- Undo support for recently applied progress updates.

Important behavior:
- DRAFT KRs are skipped during bulk sync.
- Progress writes happen only when user runs sync with write mode enabled.

### D) Suggested Next Task

Two sources are used:
- Local ranking logic in Atlas (`Suggested Next`).
- Optional AI suggestion (`suggest_critical_task`) during AI sync flow.

Purpose:
- Pick one high-priority next task using urgency, progress, and strategic context.

### E) AI Team Coach (Dashboard)

Available for manager/admin in Strategic Dashboard.

Uses aggregated team metrics to return:
- overall health score/grade
- per-dimension insights (productivity, deadlines, alignment, workload, momentum)
- top priorities, quick wins, and watch-out signal

### F) Strategy Pulse (Leadership Insights)

Location:
- Open `Strategic Dashboard`, then switch to `Strategy Pulse` tab in `Leadership Insights`.

Capabilities:
- Burnout risk scoring from recent effort/output signals (`calculate_burnout_risk`).
- Ghost-goal / strategy-gap detection for active objectives (`detect_strategy_gaps`).
- AI predictive forecast generation (`generate_predictive_outlook`).
- Achievement portfolio generation and PDF export (`generate_achievement_portfolio`, `generate_achievement_portfolio_pdf`).

Manager leadership use:
- Team monitoring: detect workload risk and stalled objectives early.
- Team building/coaching: use mitigation suggestions and portfolio evidence in 1:1 and team reviews.

## 3. Human-in-the-Loop Rules

- AI suggestions are advisory until the user applies them.
- KR progress changes from AI require explicit user action.
- Manual KR edits/check-ins remain first-class and can override AI-driven values.

## 4. RBAC Boundaries for AI Access

- UI analysis actions pass actor context into `analyze_node`.
- `analyze_node` reads node context through `get_node(..., actor_username=...)` when actor context is provided.
- `get_node` performs `READ` authorization against the node's ancestor goal before returning data.
- AI result writes still use normal mutation paths (for example `update_key_result(..., actor_username=...)`).
- Objective alignment mutations are separately authorization-gated (`create_alignment` / `delete_alignment`).

## 5. Data Quality Requirements

AI output quality depends on:
- clear KR titles and descriptions
- current KR metric values (`start/current/target`)
- clean work log summaries
- regular Weekly Ritual check-ins (confidence + comments)

If these inputs are weak, AI recommendations become generic.

## 6. Limits and Non-Features (Current Build)

The current implementation does not guarantee:
- citation-number outputs in every response,
- autonomous background retraining from every user edit,
- automatic execution of proposed tasks,
- a separate global AI control center outside Atlas/Dashboard surfaces.

Deployment policy control:
- Set `ALLOW_EXTERNAL_AI=false` (or `OKR_ALLOW_EXTERNAL_AI=false`) to hard-disable outbound Gemini calls.

## 7. Practical Prompt Patterns

Use short, constrained prompts in Inspector analysis flows:
- "What is the main blocker to this KR reaching target?"
- "Which proposed task has the highest impact in the next 3 days?"
- "Is current progress realistic relative to logged effort?"

For team coaching:
- "Prioritize top 3 interventions for next week and explain tradeoffs."
