# AI Features Guide
Documentation HQ: [README](../README.md)

This guide documents AI behavior that is currently implemented in code (`src/services/ai_service.py`, `spa-web/`, `spa-bff/`).

## 1. Where AI Is Available in the UI

AI is used in these places:
- **AI Analysis button** (Atlas workspace, below Focus Map): batch-analyzes all KRs in scope.
- **KR Inspector modal** (popup): shows cached AI analysis for a Key Result, with "Run Analysis" button to re-analyze.
- **Suggest Next Task** (timer section, top sidebar): picks the single best next task.
- `Weekly Check-In` step 1 (AI weekly summary generation).
- `Weekly Report` (AI executive brief generation).
- `Leadership Insights -> Execution` (`AI Team Coach`, manager/admin).
- `Leadership Insights -> Strategy Pulse` (burnout, strategy gaps, predictive outlook, achievement portfolio PDF).

## 1.1 Runtime Execution Path

Runtime path is backend-segregated:
- Frontend submits `ai.generate_json` jobs to `backend-api`.
- `backend-worker` executes provider calls asynchronously.

For `analyze_node` specifically, the backend calls the AI provider directly (synchronously) rather than through the job queue, since the result is needed immediately.

## 2. Implemented AI Capabilities

### A) AI Analysis (Atlas workspace)

The primary AI interaction point. A single "AI Analysis" button analyzes all KRs in scope.

**Flow:**
1. User clicks "AI Analysis" below the Focus Map.
2. System auto-analyzes all KRs that need analysis (no existing `ai_analysis` or stale >24h).
3. Analysis results are stored on each KR as `ai_analysis` JSON.
4. Report shows: analyzed count, cached count, errors.

**Key design principle:** AI provides analysis only — it does NOT estimate or update KR progress. KR progress is entered exclusively by users via check-in sessions.

**Data sent to AI per KR:**
- KR title, description, metrics (target/current/progress).
- Children (tasks) with title, description, progress, time spent, deadlines, work log summaries.
- Check-in history (cycle-scoped, last 10): value, confidence (0-10), variation type, comment.
- Experiments (cycle-scoped): hypothesis, change description, status, decision, expected effect direction.
- Parent context: Objective title/progress + Goal title/progress.
- Cycle context: cycle title, start/end dates, elapsed percentage, days remaining.
- Previous analysis results (for delta comparison with prior run).

### B) Per-Node AI Analysis (KR Inspector)

Available as a read-only display in the Inspector modal for Key Results only. Shows:
- Efficiency/effectiveness/overall scores
- Gap analysis, quality assessment
- Proposed tasks, deadline warnings
- Summary

If no analysis exists, a "Run Analysis" button appears to trigger on-demand analysis.

**Objectives do NOT have AI analysis** — their score is a weighted rollup from child KRs.

### C) Suggest Next Task (Timer section)

Located in the task timer section of the top sidebar.

Uses local priority scoring (urgency, progress gaps, parent KR scores) to pick the single best next task.

### D) AI Team Coach (Dashboard)

Available for manager/admin in Strategic Dashboard.

Uses aggregated team metrics to return:
- overall health score/grade
- per-dimension insights (productivity, deadlines, alignment, workload, momentum)
- top priorities, quick wins, and watch-out signal

### E) Strategy Pulse (Leadership Insights)

Location:
- Open `Strategic Dashboard`, then switch to `Strategy Pulse` tab in `Leadership Insights`.

Capabilities:
- Burnout risk scoring from recent effort/output signals.
- Ghost-goal / strategy-gap detection for active objectives.
- AI predictive forecast generation.
- Achievement portfolio generation and PDF export.

## 3. Task Progress: Auto-Computed

Task progress is no longer manually set. It is auto-computed from time tracking:

```
progress = total_time_spent / estimated_minutes * 100
```

- If `estimated_minutes > 0`: progress is computed as percentage (can exceed 100% when task takes longer than estimated).
- If `estimated_minutes = 0` (no estimate): falls back to `total_time_spent` as raw minutes.
- Progress is recomputed automatically when a work log is created (timer stopped) or deleted.
- The `progress <= 100` CHECK constraint has been removed for tasks.

## 4. AI Analysis Data Storage

- Analysis results are stored in the `ai_analysis` column on KeyResult.
- `ai_overall_score` is a virtual/derived field computed at read time from `ai_analysis` JSON.
- Analysis staleness is tracked via `analysis_updated_at` (24h threshold for re-analysis).

## 5. Human-in-the-Loop Rules

- AI suggestions are advisory only — no autonomous mutations.
- KR progress is entered exclusively by users via check-in sessions.
- Manual KR edits/check-ins remain first-class.

## 6. RBAC Boundaries for AI Access

- UI analysis actions pass actor context into `analyze_node`.
- `analyze_node` reads node context through `get_node(..., actor_username=...)` when actor context is provided.
- `get_node` performs `READ` authorization against the node's ancestor goal before returning data.
- AI result writes still use normal mutation paths.

## 7. Data Quality Requirements

AI output quality depends on:
- clear KR titles and descriptions
- current KR metric values (`start/current/target`)
- clean work log summaries
- regular Weekly Check-In check-ins (confidence + comments)
- task estimated minutes (for AI to assess effort allocation)

If these inputs are weak, AI recommendations become generic.

## 8. DB Connection Fallback

For `analyze_node`, the system implements a two-tier fallback:
1. **Default**: Direct PostgreSQL via port 6543 (transaction mode pooler).
2. **Fallback**: If port 6543 is unreachable → Supabase REST API via HTTPS 443.

This ensures AI analysis works even when direct database connectivity is unavailable.

## 9. Limits and Non-Features (Current Build)

The current implementation does not guarantee:
- citation-number outputs in every response,
- autonomous background retraining from every user edit,
- automatic execution of proposed tasks,
- a separate global AI control center outside Atlas/Dashboard surfaces.

Deployment policy control:
- Set `ALLOW_EXTERNAL_AI=false` to hard-disable outbound AI calls.
- Set `AI_PROVIDER=openai_compatible` with `AI_BASE_URL` + `AI_MODEL` to route AI to local/self-hosted OpenAI-compatible runtimes.

## 10. AI Data and Privacy Notice

AI features are optional and provider-driven:
- `AI_PROVIDER=gemini` uses Google Gemini (`GEMINI_API_KEY` required).
- `AI_PROVIDER=openai_compatible` routes to any OpenAI-compatible endpoint using `AI_BASE_URL` + `AI_MODEL` (optional `AI_API_KEY`).

Hard-disable policy:
- Set `ALLOW_EXTERNAL_AI=false` to block all outbound AI calls.

When AI is enabled, relevant OKR content can be sent to the configured provider, including:
- titles and descriptions
- progress and deadlines
- work-log summaries/reflections used for analysis
- check-in history (cycle-scoped)
- experiment outcomes (cycle-scoped)
- parent Objective/Goal context
- cycle timeline (start/end dates, elapsed percentage)

Before enabling AI in production, confirm provider/data-flow compliance with your company privacy and data-classification policies.
