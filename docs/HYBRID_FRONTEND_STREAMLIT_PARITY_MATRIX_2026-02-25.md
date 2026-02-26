Documentation HQ: [README](../README.md)

Hybrid Frontend Streamlit Parity Matrix

Date
- 2026-02-25

Purpose
- Provide a concrete Streamlit-to-SPA feature parity snapshot for unified-app migration.
- Separate `migrated`, `partial`, and `gap` items so execution can proceed without ambiguity.

Status Legend
- Migrated: implemented in SPA + BFF + backend path.
- Partial: visible in SPA but missing important behavior/details.
- Gap: still Streamlit-only behavior.

| Area | Streamlit Capability | SPA Status | Notes / Evidence | Next Action |
| --- | --- | --- | --- | --- |
| Auth/session | Login + role-aware session | Migrated | `spa-web` login/session + role-gated admin route in `AtlasShell.tsx` | Keep |
| Atlas Focus Map | Hierarchy browse + search + select | Migrated | `AtlasShell.tsx` focus map tree and inspector binding | Keep |
| Atlas Inspector | Edit title/description/progress | Migrated | `updateNodeMutation` path wired via BFF | Keep |
| Focus timer | Start/stop timer with summary | Migrated | timer controls in inspector; backend timer endpoints used | Keep |
| Node lifecycle | Goal/Object/KR/Task create/delete | Migrated | create/delete flows wired in Atlas inspector | Keep |
| Objective alignment | Add/remove alignment edges | Migrated | `createAlignmentMutation` / `deleteAlignmentMutation` | Keep |
| Mindmap | Mindmap payload visibility | Migrated | SPA now renders structured goal/objective/KR/task hierarchy with direct node selection while keeping raw payload fallback. | Keep |
| Timeline / Gantt | Schedule timeline visualization for cycle tasks | Migrated | SPA Timeline now renders a status-coded Gantt board with today marker, projected-end styling, and overdue highlighting from `tasks.by_cycle` payloads. | Keep |
| Atlas snapshot loading | Auto-load current cycle snapshot | Migrated | cycle resolution + automatic snapshot fetch + Atlas-mode auto-sync polling (45s) | Keep |
| AI progress sync | Preview/apply KR progress from AI score | Migrated | new `AI Assist` panel: preview/apply/undo with policy controls | Keep |
| AI undo | Rollback last AI progress update set | Migrated | `Undo Sync` action in `AI Assist` | Keep |
| AI suggested next task | AI job-based next-task suggestion | Migrated | `Suggest Next Task` via `ai.generate_json` async job | Keep |
| KR/Object analysis (magic-wand) | On-demand `analyze_node` writeback | Migrated | SPA inspector `Run Analysis` now uses semantic backend endpoint (`POST /v1/ai/analyze-node`) for both KR/objective and persists `gemini_analysis` through node updates for both types. | Keep |
| Weekly check-in | KR check-in submission UX | Migrated | Check-In mode now ships guided Review -> Check-In -> Plan flow, variation governance, active-experiment linkage, and in-flow experiment creation plus backend persistence (`POST /v1/check-ins`, `POST /v1/experiments`). | Keep |
| Weekly/Daily reports | Export + AI summary/brief workflows | Migrated | Weekly/Daily modes now support AI narrative generation using backend async jobs (`ai.generate_json`) in addition to PDF/HTML export. | Keep |
| Dashboard leadership AI | Team coach insights | Migrated | SPA dashboard Team Coach now uses semantic backend endpoint (`POST /v1/ai/team-coach`) with Streamlit-compatible coaching dimensions/priority structures. | Keep |
| Strategy Pulse | Burnout/gaps/predictive/portfolio | Migrated | SPA dashboard Strategy Pulse now uses semantic backend endpoint (`POST /v1/ai/strategy-pulse`) backed by Streamlit burnout/gap/predictive services (`calculate_burnout_risk`, `detect_strategy_gaps`, `generate_predictive_outlook`). | Keep |
| Admin: cycles | Create/activate/delete cycles | Migrated | admin cycles tab with active-cycle controls | Keep |
| Admin: users/teams/security | Manage users/teams/password reset | Migrated | admin tabs implemented | Keep |
| Admin: system diagnostics | AI/PDF health probes | Migrated | admin health tab wired to backend | Keep |
| Admin: DB ops | Backup + guarded restore | Migrated | backup export + restore UI in admin | Keep |
| Unified app behavior | No required Streamlit bridge for core workflows | Migrated | Core Atlas/admin/report/leadership/check-in flows run directly in SPA; Streamlit bridge route retired from active runtime paths. | Keep |

Immediate Gap Closure Order
1. Continue tightening UX polish and automated parity tests for guided Check-In and timeline surfaces.

