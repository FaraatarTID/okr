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
- read path: Streamlit UI -> `src/crud.py` -> Supabase PostgreSQL.
- write path (when backend mode is enabled): Streamlit UI -> `backend-api` -> `src/crud.py` -> Supabase PostgreSQL.
- production default is fail-closed on backend transport failures; local mutation fallback is non-production only (`OKR_ALLOW_LOCAL_MUTATION_FALLBACK=true`).
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
Learning Loop UI orchestration is in `render_weekly_ritual_dialog` (`streamlit_app/src/ui/dialogs.py`):
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
این سند فقط معماری Learning Loop را پوشش می‌دهد:
- توسعه schema برای check-in و experiment،
- قواعد CRUD و authorization،
- نقاط اتصال UI در `streamlit_app/src/ui/dialogs.py`,
- قواعد migration و همگام‌سازی مستندات.

### Runtime Placement (Current System)
منطق Learning Loop در لایه دامنه اصلی اجرا می‌شود:
- مسیر read/write: رابط Streamlit -> `src/crud.py` -> پایگاه‌داده Supabase PostgreSQL.
- در وضعیت فعلی به `backend-worker` منتقل نشده است.
- صف backend فقط برای کارهای سنگین AI/PDF استفاده می‌شود، نه mutationهای check-in/experiment.

### Schema Contract
Learning Loop بر ۳ قرارداد جدولی متکی است:

| Table | Contract |
|---|---|
| `check_in` (extended) | فیلدهای `variation_type`، `special_cause_note`، `experiment_id` و ایندکس `ix_check_in_kr_var_created` اضافه می‌شوند. |
| `experiment` | تغییرات کنترل‌شده برای هر KR را نگه می‌دارد (`status`، hypothesis، فیلدهای decision، اتصال cycle). |
| `retro_experiment_outcome` | خروجی تصمیم بازنگری را برای هر جفت (`retrospective_id`, `experiment_id`) با ایندکس یکتا `ux_retro_experiment` نگه می‌دارد. |

### CRUD Contract
توابع اصلی و invariantها:

| Function | Key Rules |
|---|---|
| `create_check_in` | `variation_type` اجباری است؛ در `SPECIAL_CAUSE` note (حداقل ۵ کاراکتر) الزامی و `experiment_id` پاک می‌شود؛ در `COMMON_CAUSE` note پاک می‌شود و تعلق experiment به همان KR بررسی می‌گردد. |
| `create_experiment` | authorization و constraint چرخه را enforce می‌کند: `experiment.cycle_id == goal.cycle_id`. |
| `list_experiments_for_kr` | فقط با goal-scoped access؛ همه experimentهای KR را برمی‌گرداند. |
| `get_active_experiments_for_kr` | فقط با goal-scoped access؛ فقط `ExperimentStatus.RUNNING`. |
| `update_experiment` | فقط goal-scoped mutation؛ فقط فیلدهای whitelisted قابل تغییر هستند. |
| `close_experiment` | wrapper برای تنظیم `status=DECIDED` همراه decision/rationale/end time. |
| `list_experiments_for_retro_window` | experimentهای RUNNING و experimentهای تمام‌شده در بازه retro را با فیلتر goal-scoped access برمی‌گرداند. |
| `upsert_retro_experiment_outcome` | فقط مالک retrospective؛ درج یا به‌روزرسانی روی (`retrospective_id`, `experiment_id`). |

### UI Wiring Contract
هماهنگی UI در `render_weekly_ritual_dialog` در `streamlit_app/src/ui/dialogs.py` انجام می‌شود:
- `Step 2 (Update KRs)`:
  - UI دسته‌بندی variation،
  - فراخوانی `get_active_experiments_for_kr`,
  - ساخت inline با `create_experiment` و سپس `update_experiment(..., status=RUNNING)`,
  - ثبت check-in با `create_check_in`.
- `Step 1 (Review Week)`:
  - بارگذاری experimentها با `list_experiments_for_retro_window`,
  - ثبت outcome با `upsert_retro_experiment_outcome`,
  - بستن experiment با `close_experiment` (به `DECIDED`).

### Authorization Contract
- سیاست goal-scoped برای experiments/check-ins:
  - دامنه access برابر دامنه mutation است (`domain_auth._authorize_goal_scoped_access` به `_authorize_goal_mutation` واگذار می‌کند).
  - owner، manager-of-owner و admin مجاز هستند.
- سیاست retro outcome:
  - در `upsert_retro_experiment_outcome` فقط مالک retrospective مجاز است.

### Invariants
- در check-in جدید، `variation_type` اجباری است.
- `SPECIAL_CAUSE` با لینک experiment ناسازگار است (mutually exclusive).
- experiment لینک‌شده باید متعلق به همان KR باشد.
- ایمنی چرخه: `experiment.cycle_id` باید با cycle هدف KR یکسان باشد.
- تصمیم در مسیر retro باید experiment را به `ExperimentStatus.DECIDED` ببندد.

### Migration Contract
- فایل migration: `streamlit_app/alembic/versions/f7a8b9c0d1e2_add_learning_loop.py`
- Upgrade این موارد را اضافه می‌کند:
  - `experiment`,
  - `retro_experiment_outcome`,
  - فیلدها و ایندکس Learning Loop روی `check_in`.
- Downgrade این تغییرات را به‌ترتیب معکوس حذف می‌کند.

### Docs Sync Rule
هر PR که مدل‌ها، CRUD، migration یا UI wiring مربوط به Learning Loop را تغییر می‌دهد، باید در همان PR هر دو بخش `EN` و `FA` را در این فایل و در `docs/learning-loop.md` به‌روزرسانی کند.
