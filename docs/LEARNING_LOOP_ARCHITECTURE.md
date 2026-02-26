# Architecture (Learning Loop)
Documentation HQ: [README](../README.md)

Developer contract for Learning Loop schema, CRUD rules, UI wiring, authorization, and migration.

## EN

### Scope
This document covers only Learning Loop architecture:
- schema extensions around check-ins and experiments,
- CRUD invariants and authorization,
- UI integration points in `streamlit_app/src/ui/dialogs.py`,
- migration and documentation sync rules.

### Runtime Placement (Current System)
Learning Loop logic executes in the shared domain layer (`src/crud.py`) with backend-assisted mutation routing:
- read path: Streamlit UI -> `backend-api` -> `src/crud.py` -> Supabase PostgreSQL.
- write path: Streamlit UI -> `backend-api` -> `src/crud.py` -> Supabase PostgreSQL.
- runtime behavior is fail-closed on backend transport failures (local read/mutation fallback execution is disabled).
- `backend-worker` remains reserved for heavy AI/PDF async jobs, not check-in/experiment/retro mutations.

### Schema Contract
Learning Loop depends on exactly 3 tables/contracts:

| Table | Contract |
|---|---|
| `check_in` (extended) | Adds `variation_type`, `special_cause_note`, `experiment_id` and index `ix_check_in_kr_var_created`. |
| `experiment` | Stores controlled changes per KR (`status`, hypothesis, decision fields, cycle linkage). |
| `retro_experiment_outcome` | Stores retrospective decision snapshots per (`retrospective_id`, `experiment_id`) with unique index `ux_retro_experiment`. |

### CRUD Contract
Core functions and invariants:

| Function | Key Rules |
|---|---|
| `create_check_in` | Requires `variation_type`; `SPECIAL_CAUSE` needs note (>=5 chars) and clears `experiment_id`; `COMMON_CAUSE` clears note and validates linked experiment belongs to same KR. |
| `create_experiment` | Enforces authorization and cycle constraint: `experiment.cycle_id == goal.cycle_id`. |
| `list_experiments_for_kr` | Goal-scoped access only; returns all KR experiments. |
| `get_active_experiments_for_kr` | Goal-scoped access only; returns `ExperimentStatus.RUNNING`. |
| `update_experiment` | Goal-scoped mutation only; updates only whitelisted fields. |
| `close_experiment` | Wrapper that sets `status=DECIDED` plus decision/rationale/end time. |
| `list_experiments_for_retro_window` | Returns RUNNING experiments plus experiments ended in the retro window, filtered by goal-scoped access. |
| `upsert_retro_experiment_outcome` | Retro owner only; insert-or-update on (`retrospective_id`, `experiment_id`). |

### UI Wiring Contract
Learning Loop UI orchestration is in `render_weekly_check-in_dialog` (`streamlit_app/src/ui/dialogs.py`):
- `Step 2 (Update KRs)`:
  - variation classification UI,
  - call `get_active_experiments_for_kr`,
  - optional inline `create_experiment` and `update_experiment(..., status=RUNNING)`,
  - submit check-in through `create_check_in`.
- `Step 1 (Review Week)`:
  - load candidates via `list_experiments_for_retro_window`,
  - on decision: call `upsert_retro_experiment_outcome`,
  - close experiment via `close_experiment` (to `DECIDED`).

### Authorization Contract
- Goal-scoped policy for experiments/check-ins:
  - access scope equals mutation scope (`domain_auth._authorize_goal_scoped_access` delegates to `_authorize_goal_mutation`).
  - owner, manager-of-owner, and admin are allowed.
- Retro outcome policy:
  - `upsert_retro_experiment_outcome` is owner-only for the target retrospective.

### Invariants
- `variation_type` is required on new check-ins.
- `SPECIAL_CAUSE` and experiment linkage are mutually exclusive.
- A linked experiment must belong to the same KR as the check-in.
- Cycle safety: `experiment.cycle_id` must equal the cycle of the KR's goal.
- Decision in retro path closes the experiment to `ExperimentStatus.DECIDED`.

### Migration Contract
- Migration file: `streamlit_app/alembic/versions/f7a8b9c0d1e2_add_learning_loop.py`
- Upgrade adds:
  - `experiment`,
  - `retro_experiment_outcome`,
  - learning-loop fields/index on `check_in`.
- Downgrade removes these additions in reverse order.

### Docs Sync Rule
Any PR that changes Learning Loop models, CRUD, migration, or UI wiring must update both `EN` and `FA` sections in this file and in `docs/learning-loop.md` within the same PR.

## FA

### Scope
Ø§ÛŒÙ† Ø³Ù†Ø¯ ÙÙ‚Ø· Ù…Ø¹Ù…Ø§Ø±ÛŒ Learning Loop Ø±Ø§ Ù¾ÙˆØ´Ø´ Ù…ÛŒâ€ŒØ¯Ù‡Ø¯:
- ØªÙˆØ³Ø¹Ù‡ schema Ø¨Ø±Ø§ÛŒ check-in Ùˆ experimentØŒ
- Ù‚ÙˆØ§Ø¹Ø¯ CRUD Ùˆ authorizationØŒ
- Ù†Ù‚Ø§Ø· Ø§ØªØµØ§Ù„ UI Ø¯Ø± `streamlit_app/src/ui/dialogs.py`,
- Ù‚ÙˆØ§Ø¹Ø¯ migration Ùˆ Ù‡Ù…Ú¯Ø§Ù…â€ŒØ³Ø§Ø²ÛŒ Ù…Ø³ØªÙ†Ø¯Ø§Øª.

### Runtime Placement (Current System)
Ù…Ù†Ø·Ù‚ Learning Loop Ø¯Ø± Ù„Ø§ÛŒÙ‡ Ø¯Ø§Ù…Ù†Ù‡ Ø§ØµÙ„ÛŒ Ø§Ø¬Ø±Ø§ Ù…ÛŒâ€ŒØ´ÙˆØ¯:
- Ù…Ø³ÛŒØ± read/write: Ø±Ø§Ø¨Ø· Streamlit -> `src/crud.py` -> Ù¾Ø§ÛŒÚ¯Ø§Ù‡â€ŒØ¯Ø§Ø¯Ù‡ Supabase PostgreSQL.
- Ø¯Ø± ÙˆØ¶Ø¹ÛŒØª ÙØ¹Ù„ÛŒ Ø¨Ù‡ `backend-worker` Ù…Ù†ØªÙ‚Ù„ Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª.
- ØµÙ backend ÙÙ‚Ø· Ø¨Ø±Ø§ÛŒ Ú©Ø§Ø±Ù‡Ø§ÛŒ Ø³Ù†Ú¯ÛŒÙ† AI/PDF Ø§Ø³ØªÙØ§Ø¯Ù‡ Ù…ÛŒâ€ŒØ´ÙˆØ¯ØŒ Ù†Ù‡ mutationÙ‡Ø§ÛŒ check-in/experiment.

### Schema Contract
Learning Loop Ø¨Ø± Û³ Ù‚Ø±Ø§Ø±Ø¯Ø§Ø¯ Ø¬Ø¯ÙˆÙ„ÛŒ Ù…ØªÚ©ÛŒ Ø§Ø³Øª:

| Table | Contract |
|---|---|
| `check_in` (extended) | ÙÛŒÙ„Ø¯Ù‡Ø§ÛŒ `variation_type`ØŒ `special_cause_note`ØŒ `experiment_id` Ùˆ Ø§ÛŒÙ†Ø¯Ú©Ø³ `ix_check_in_kr_var_created` Ø§Ø¶Ø§ÙÙ‡ Ù…ÛŒâ€ŒØ´ÙˆÙ†Ø¯. |
| `experiment` | ØªØºÛŒÛŒØ±Ø§Øª Ú©Ù†ØªØ±Ù„â€ŒØ´Ø¯Ù‡ Ø¨Ø±Ø§ÛŒ Ù‡Ø± KR Ø±Ø§ Ù†Ú¯Ù‡ Ù…ÛŒâ€ŒØ¯Ø§Ø±Ø¯ (`status`ØŒ hypothesisØŒ ÙÛŒÙ„Ø¯Ù‡Ø§ÛŒ decisionØŒ Ø§ØªØµØ§Ù„ cycle). |
| `retro_experiment_outcome` | Ø®Ø±ÙˆØ¬ÛŒ ØªØµÙ…ÛŒÙ… Ø¨Ø§Ø²Ù†Ú¯Ø±ÛŒ Ø±Ø§ Ø¨Ø±Ø§ÛŒ Ù‡Ø± Ø¬ÙØª (`retrospective_id`, `experiment_id`) Ø¨Ø§ Ø§ÛŒÙ†Ø¯Ú©Ø³ ÛŒÚ©ØªØ§ `ux_retro_experiment` Ù†Ú¯Ù‡ Ù…ÛŒâ€ŒØ¯Ø§Ø±Ø¯. |

### CRUD Contract
ØªÙˆØ§Ø¨Ø¹ Ø§ØµÙ„ÛŒ Ùˆ invariantÙ‡Ø§:

| Function | Key Rules |
|---|---|
| `create_check_in` | `variation_type` Ø§Ø¬Ø¨Ø§Ø±ÛŒ Ø§Ø³ØªØ› Ø¯Ø± `SPECIAL_CAUSE` note (Ø­Ø¯Ø§Ù‚Ù„ Ûµ Ú©Ø§Ø±Ø§Ú©ØªØ±) Ø§Ù„Ø²Ø§Ù…ÛŒ Ùˆ `experiment_id` Ù¾Ø§Ú© Ù…ÛŒâ€ŒØ´ÙˆØ¯Ø› Ø¯Ø± `COMMON_CAUSE` note Ù¾Ø§Ú© Ù…ÛŒâ€ŒØ´ÙˆØ¯ Ùˆ ØªØ¹Ù„Ù‚ experiment Ø¨Ù‡ Ù‡Ù…Ø§Ù† KR Ø¨Ø±Ø±Ø³ÛŒ Ù…ÛŒâ€ŒÚ¯Ø±Ø¯Ø¯. |
| `create_experiment` | authorization Ùˆ constraint Ú†Ø±Ø®Ù‡ Ø±Ø§ enforce Ù…ÛŒâ€ŒÚ©Ù†Ø¯: `experiment.cycle_id == goal.cycle_id`. |
| `list_experiments_for_kr` | ÙÙ‚Ø· Ø¨Ø§ goal-scoped accessØ› Ù‡Ù…Ù‡ experimentÙ‡Ø§ÛŒ KR Ø±Ø§ Ø¨Ø±Ù…ÛŒâ€ŒÚ¯Ø±Ø¯Ø§Ù†Ø¯. |
| `get_active_experiments_for_kr` | ÙÙ‚Ø· Ø¨Ø§ goal-scoped accessØ› ÙÙ‚Ø· `ExperimentStatus.RUNNING`. |
| `update_experiment` | ÙÙ‚Ø· goal-scoped mutationØ› ÙÙ‚Ø· ÙÛŒÙ„Ø¯Ù‡Ø§ÛŒ whitelisted Ù‚Ø§Ø¨Ù„ ØªØºÛŒÛŒØ± Ù‡Ø³ØªÙ†Ø¯. |
| `close_experiment` | wrapper Ø¨Ø±Ø§ÛŒ ØªÙ†Ø¸ÛŒÙ… `status=DECIDED` Ù‡Ù…Ø±Ø§Ù‡ decision/rationale/end time. |
| `list_experiments_for_retro_window` | experimentÙ‡Ø§ÛŒ RUNNING Ùˆ experimentÙ‡Ø§ÛŒ ØªÙ…Ø§Ù…â€ŒØ´Ø¯Ù‡ Ø¯Ø± Ø¨Ø§Ø²Ù‡ retro Ø±Ø§ Ø¨Ø§ ÙÛŒÙ„ØªØ± goal-scoped access Ø¨Ø±Ù…ÛŒâ€ŒÚ¯Ø±Ø¯Ø§Ù†Ø¯. |
| `upsert_retro_experiment_outcome` | ÙÙ‚Ø· Ù…Ø§Ù„Ú© retrospectiveØ› Ø¯Ø±Ø¬ ÛŒØ§ Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ø±ÙˆÛŒ (`retrospective_id`, `experiment_id`). |

### UI Wiring Contract
Ù‡Ù…Ø§Ù‡Ù†Ú¯ÛŒ UI Ø¯Ø± `render_weekly_check-in_dialog` Ø¯Ø± `streamlit_app/src/ui/dialogs.py` Ø§Ù†Ø¬Ø§Ù… Ù…ÛŒâ€ŒØ´ÙˆØ¯:
- `Step 2 (Update KRs)`:
  - UI Ø¯Ø³ØªÙ‡â€ŒØ¨Ù†Ø¯ÛŒ variationØŒ
  - ÙØ±Ø§Ø®ÙˆØ§Ù†ÛŒ `get_active_experiments_for_kr`,
  - Ø³Ø§Ø®Øª inline Ø¨Ø§ `create_experiment` Ùˆ Ø³Ù¾Ø³ `update_experiment(..., status=RUNNING)`,
  - Ø«Ø¨Øª check-in Ø¨Ø§ `create_check_in`.
- `Step 1 (Review Week)`:
  - Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ experimentÙ‡Ø§ Ø¨Ø§ `list_experiments_for_retro_window`,
  - Ø«Ø¨Øª outcome Ø¨Ø§ `upsert_retro_experiment_outcome`,
  - Ø¨Ø³ØªÙ† experiment Ø¨Ø§ `close_experiment` (Ø¨Ù‡ `DECIDED`).

### Authorization Contract
- Ø³ÛŒØ§Ø³Øª goal-scoped Ø¨Ø±Ø§ÛŒ experiments/check-ins:
  - Ø¯Ø§Ù…Ù†Ù‡ access Ø¨Ø±Ø§Ø¨Ø± Ø¯Ø§Ù…Ù†Ù‡ mutation Ø§Ø³Øª (`domain_auth._authorize_goal_scoped_access` Ø¨Ù‡ `_authorize_goal_mutation` ÙˆØ§Ú¯Ø°Ø§Ø± Ù…ÛŒâ€ŒÚ©Ù†Ø¯).
  - ownerØŒ manager-of-owner Ùˆ admin Ù…Ø¬Ø§Ø² Ù‡Ø³ØªÙ†Ø¯.
- Ø³ÛŒØ§Ø³Øª retro outcome:
  - Ø¯Ø± `upsert_retro_experiment_outcome` ÙÙ‚Ø· Ù…Ø§Ù„Ú© retrospective Ù…Ø¬Ø§Ø² Ø§Ø³Øª.

### Invariants
- Ø¯Ø± check-in Ø¬Ø¯ÛŒØ¯ØŒ `variation_type` Ø§Ø¬Ø¨Ø§Ø±ÛŒ Ø§Ø³Øª.
- `SPECIAL_CAUSE` Ø¨Ø§ Ù„ÛŒÙ†Ú© experiment Ù†Ø§Ø³Ø§Ø²Ú¯Ø§Ø± Ø§Ø³Øª (mutually exclusive).
- experiment Ù„ÛŒÙ†Ú©â€ŒØ´Ø¯Ù‡ Ø¨Ø§ÛŒØ¯ Ù…ØªØ¹Ù„Ù‚ Ø¨Ù‡ Ù‡Ù…Ø§Ù† KR Ø¨Ø§Ø´Ø¯.
- Ø§ÛŒÙ…Ù†ÛŒ Ú†Ø±Ø®Ù‡: `experiment.cycle_id` Ø¨Ø§ÛŒØ¯ Ø¨Ø§ cycle Ù‡Ø¯Ù KR ÛŒÚ©Ø³Ø§Ù† Ø¨Ø§Ø´Ø¯.
- ØªØµÙ…ÛŒÙ… Ø¯Ø± Ù…Ø³ÛŒØ± retro Ø¨Ø§ÛŒØ¯ experiment Ø±Ø§ Ø¨Ù‡ `ExperimentStatus.DECIDED` Ø¨Ø¨Ù†Ø¯Ø¯.

### Migration Contract
- ÙØ§ÛŒÙ„ migration: `streamlit_app/alembic/versions/f7a8b9c0d1e2_add_learning_loop.py`
- Upgrade Ø§ÛŒÙ† Ù…ÙˆØ§Ø±Ø¯ Ø±Ø§ Ø§Ø¶Ø§ÙÙ‡ Ù…ÛŒâ€ŒÚ©Ù†Ø¯:
  - `experiment`,
  - `retro_experiment_outcome`,
  - ÙÛŒÙ„Ø¯Ù‡Ø§ Ùˆ Ø§ÛŒÙ†Ø¯Ú©Ø³ Learning Loop Ø±ÙˆÛŒ `check_in`.
- Downgrade Ø§ÛŒÙ† ØªØºÛŒÛŒØ±Ø§Øª Ø±Ø§ Ø¨Ù‡â€ŒØªØ±ØªÛŒØ¨ Ù…Ø¹Ú©ÙˆØ³ Ø­Ø°Ù Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

### Docs Sync Rule
Ù‡Ø± PR Ú©Ù‡ Ù…Ø¯Ù„â€ŒÙ‡Ø§ØŒ CRUDØŒ migration ÛŒØ§ UI wiring Ù…Ø±Ø¨ÙˆØ· Ø¨Ù‡ Learning Loop Ø±Ø§ ØªØºÛŒÛŒØ± Ù…ÛŒâ€ŒØ¯Ù‡Ø¯ØŒ Ø¨Ø§ÛŒØ¯ Ø¯Ø± Ù‡Ù…Ø§Ù† PR Ù‡Ø± Ø¯Ùˆ Ø¨Ø®Ø´ `EN` Ùˆ `FA` Ø±Ø§ Ø¯Ø± Ø§ÛŒÙ† ÙØ§ÛŒÙ„ Ùˆ Ø¯Ø± `docs/learning-loop.md` Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ú©Ù†Ø¯.

