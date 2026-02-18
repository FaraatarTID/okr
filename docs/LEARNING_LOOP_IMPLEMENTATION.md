# Learning Loop Implementation Report

Canonical docs for ongoing usage and maintenance:
- Operator workflow (EN+FA): [`docs/learning-loop.md`](learning-loop.md)
- Developer contract (EN+FA): [`docs/architecture.md`](architecture.md)

This file is kept as an implementation history report.

**Date:** 2026-02-18  
**Status:** Implemented  
**Version:** 1.0.0  

---

## Executive Summary

This document describes the implementation of a "learning loop" feature for the OKR Tracker application. The feature transforms weekly check-ins from passive reporting into active system improvement by requiring users to classify metric variations and link them to controlled experiments.

The implementation adds:
- Variation classification (common cause vs. special cause) for every check-in
- First-class experiment artifacts linked to Key Results
- Retrospective-to-experiment outcome linking for institutional learning
- Authorization-enforced data access matching existing goal-scoped permissions

---

## 1. Problem Statement

### 1.1 Original Behavior

The existing check-in flow collected metric values and confidence scores but provided no mechanism to:
- Distinguish between system behavior (common cause) and exceptional events (special cause)
- Run controlled experiments on Key Results
- Institutionalize learnings from experiments

This led to:
- Pressure-based responses to normal variation
- No structured way to test system changes
- Lost institutional knowledge when experiments concluded

### 1.2 Objectives

1. Require every check-in to classify variation type
2. Enable creating/linking experiments to Key Results
3. Allow retrospectives to record experiment outcomes
4. Enforce the same authorization model as existing goal-scoped operations
5. Integrate into existing weekly ritual workflow without creating new screens

---

## 2. Architecture Overview

### 2.1 Design Principles

| Principle | Implementation |
|-----------|----------------|
| Composable primitives | Two new tables (Experiment, RetroExperimentOutcome), one extended table (CheckIn) |
| Authorization reuse | All operations use existing `_authorize_goal_mutation` or `_authorize_goal_scoped_access` |
| Ritual integration | Experiments surface in weekly ritual, outcomes in retrospectives |
| Cycle alignment | Experiments are cycle-scoped, matching quarterly planning cadence |
| Backward compatibility | New CheckIn columns are nullable; existing data unaffected |

### 2.2 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Weekly Ritual                              │
│  ┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐    │
│  │ Review Week │───▶│ Update KRs      │───▶│ Plan Next Week   │    │
│  └─────────────┘    │ (with variation │    └──────────────────┘    │
│                     │  classification)│                             │
│                     └────────┬────────┘                             │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Data Model                                   │
│                                                                      │
│  ┌──────────┐     ┌──────────────┐     ┌─────────────────────────┐ │
│  │ CheckIn  │────▶│ Experiment   │◀────│ RetroExperimentOutcome  │ │
│  │          │     │              │     │                         │ │
│  │variation_│     │key_result_id │     │retrospective_id         │ │
│  │type      │     │cycle_id      │     │experiment_id            │ │
│  │experiment│     │hypothesis    │     │decision                 │ │
│  │_id       │     │status        │     │rationale                │ │
│  │special_  │     │decision      │     └─────────────────────────┘ │
│  │cause_note│     └──────────────┘                                 │
│  └──────────┘                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Model Changes

### 3.1 New Enums

```python
class VariationType(str, Enum):
    COMMON_CAUSE = "COMMON_CAUSE"    # System behavior
    SPECIAL_CAUSE = "SPECIAL_CAUSE"  # Exceptional event

class ExperimentStatus(str, Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    DECIDED = "DECIDED"

class ExperimentDecision(str, Enum):
    ADOPT = "ADOPT"        # Keep the change
    REVERT = "REVERT"      # Roll back
    ITERATE = "ITERATE"    # Modify and retry
    UNKNOWN = "UNKNOWN"    # Inconclusive

class ExpectedEffectDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
```

### 3.2 Extended CheckIn Table

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `variation_type` | VARCHAR | Yes | COMMON_CAUSE or SPECIAL_CAUSE |
| `special_cause_note` | VARCHAR | Yes | Required if SPECIAL_CAUSE (min 5 chars) |
| `experiment_id` | INTEGER | Yes | FK to experiment, only for COMMON_CAUSE |

**New Index:** `ix_check_in_kr_var_created (key_result_id, variation_type, created_at)`

### 3.3 New Experiment Table

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | No | Primary key |
| `key_result_id` | INTEGER | No | FK to key_result |
| `cycle_id` | INTEGER | No | FK to cycle (must match KR's goal cycle) |
| `created_by` | VARCHAR | No | Username of creator |
| `hypothesis` | VARCHAR | No | "If we do X, then Y will happen" |
| `change_description` | VARCHAR | No | What specific change will be made |
| `start_at` | DATETIME | No | When experiment begins |
| `end_at` | DATETIME | Yes | When experiment concludes |
| `status` | VARCHAR | No | PLANNED/RUNNING/DECIDED |
| `decision` | VARCHAR | Yes | ADOPT/REVERT/ITERATE/UNKNOWN |
| `decision_rationale` | VARCHAR | Yes | Why this decision was made |
| `expected_effect_direction` | VARCHAR | Yes | UP/DOWN |
| `expected_effect_size` | FLOAT | Yes | Expected magnitude |
| `created_at` | DATETIME | No | Timestamp |

**Indexes:**
- `ix_experiment_kr_status (key_result_id, status)`
- `ix_experiment_cycle_status (cycle_id, status)`

### 3.4 New RetroExperimentOutcome Table

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | No | Primary key |
| `retrospective_id` | INTEGER | No | FK to retrospective |
| `experiment_id` | INTEGER | No | FK to experiment |
| `decision` | VARCHAR | No | ADOPT/REVERT/ITERATE/UNKNOWN |
| `rationale` | VARCHAR | Yes | Explanation |
| `created_at` | DATETIME | No | Timestamp |

**Unique Constraint:** `ux_retro_experiment (retrospective_id, experiment_id)`

---

## 4. CRUD Layer Changes

### 4.1 Authorization

Added `_authorize_goal_scoped_access()` in `authorization.py`:

```python
def _authorize_goal_scoped_access(
    session: Session, goal: Optional[Goal], actor_username: Optional[str]
) -> None:
    """
    Enforce access to goal-scoped data (experiments, check-ins, etc.).
    Currently implements goal-scoped access where read equals mutation scope:
    - Goal owner can access
    - Manager of goal owner can access  
    - Admins can access
    
    If broader read visibility is needed in the future, implement a separate
    _authorize_goal_read with relaxed rules without modifying this function.
    """
    _authorize_goal_mutation(session, goal, actor_username)
```

### 4.2 New Functions

| Function | Description |
|----------|-------------|
| `create_experiment()` | Create experiment with cycle validation |
| `list_experiments_for_kr()` | List all experiments (authorized) |
| `get_active_experiments_for_kr()` | Get RUNNING experiments (authorized) |
| `update_experiment()` | Update experiment fields (authorized) |
| `close_experiment()` | Set status to DECIDED with decision |
| `upsert_retro_experiment_outcome()` | Attach outcome to retro (owner-only) |

### 4.3 Updated create_check_in

**Signature change:**
```python
def create_check_in(
    kr_id: int,
    value: float,
    confidence: int,
    comment: str,
    actor_username: str,  # Now required
    variation_type: Optional[VariationType] = None,
    special_cause_note: Optional[str] = None,
    experiment_id: Optional[int] = None,
) -> CheckIn:
```

**Validation rules:**

1. `variation_type` is required (enforced at CRUD level)
2. If `SPECIAL_CAUSE`:
   - `special_cause_note` must be ≥ 5 characters
   - `experiment_id` is cleared (ignored if provided)
3. If `COMMON_CAUSE`:
   - `special_cause_note` is cleared
   - If `experiment_id` provided, must belong to same KR
4. Removed manual `kr.progress` calculation (delegated to `refresh_hierarchy_progress`)

---

## 5. UI Integration

### 5.1 Weekly Ritual Changes

Location: `src/ui/dialogs.py` - `render_weekly_ritual_dialog()` Step 2

**Added elements:**

1. **Variation Classification Radio**
   - Options: "Common Cause" / "Special Cause"
   - Help text explaining each type

2. **Special Cause Flow**
   - Text input for note (required, min 5 chars, max 200 chars)

3. **Common Cause Flow**
   - Dropdown listing active experiments for KR
   - Option "None (no experiment this week)"
   - If no experiments exist, "Start New Experiment" button

4. **Inline Experiment Creation Form**
   - Hypothesis (required)
   - Change description (required)
   - Expected direction (UP/DOWN)
   - Expected effect size (numeric)
   - On submit: creates experiment and sets status to RUNNING

### 5.2 Caching Strategy

Experiment lists are cached in `st.session_state` per KR:
- Key: `active_exps_{kr_id}`
- Cleared on: experiment creation, check-in submission
- Prevents redundant DB queries on rerun

### 5.3 Retro Experiment Review (Step 1 of Weekly Ritual)

Added "Experiments Reviewed This Week" section in weekly ritual Step 1:

**UI Elements:**
1. Section header with caption explaining purpose
2. For each experiment in the week window:
   - Status badge (⚪ PLANNED, 🟢 RUNNING, 🔵 DECIDED)
   - Hypothesis text (truncated)
   - Decision dropdown: ADOPT/REVERT/ITERATE/UNKNOWN
   - Rationale text input (optional)
3. Empty state message if no experiments

**Backend Helper:**
```python
def list_experiments_for_retro_window(
    cycle_id: int,
    window_start: datetime,
    window_end: datetime,
    actor_username: str,
) -> List[Experiment]
```
Returns experiments that:
- Ended within `[window_start, window_end)`, OR
- Are still in RUNNING status
- User has goal-scoped access to

**On Submit:**
1. Retro content saved via `create_retrospective()`
2. For each experiment with a decision selected:
   - Call `upsert_retro_experiment_outcome()` to record outcome in retro
   - Call `close_experiment()` to update Experiment record (status → DECIDED, decision, rationale, end_at)
   - Exceptions caught per-experiment (won't fail retro save)
   - Warning shown if outcome save fails

---

## 6. Testing

### 6.1 Test File

`tests/test_learning_loop.py`

### 6.2 Test Coverage

| Test | Purpose |
|------|---------|
| `test_check_in_requires_variation_type` | Enforce CRUD-level requirement |
| `test_check_in_rejects_cross_kr_experiment_link` | Prevent data corruption |
| `test_special_cause_requires_note` | Validate note length |
| `test_experiment_list_requires_authorization` | Read access enforcement |
| `test_experiment_mutation_requires_authorization` | Write access enforcement |
| `test_experiment_cycle_must_match_goal_cycle` | Cross-cycle prevention |
| `test_special_cause_clears_experiment_link` | Mutual exclusivity |
| `test_retro_outcome_only_owner_can_modify` | Retro owner policy |

### 6.3 Test Results

```
tests/test_learning_loop.py::test_check_in_requires_variation_type PASSED
tests/test_learning_loop.py::test_check_in_rejects_cross_kr_experiment_link PASSED
tests/test_learning_loop.py::test_special_cause_requires_note PASSED
tests/test_learning_loop.py::test_experiment_list_requires_authorization PASSED
tests/test_learning_loop.py::test_experiment_mutation_requires_authorization PASSED
tests/test_learning_loop.py::test_experiment_cycle_must_match_goal_cycle PASSED
tests/test_learning_loop.py::test_special_cause_clears_experiment_link PASSED
tests/test_learning_loop.py::test_retro_outcome_only_owner_can_modify PASSED

8 passed in 13.55s
```

### 6.4 Post-Implementation Test Fixes

After implementation, two existing test files required updates to pass `variation_type`:

| File | Changes |
|------|---------|
| `tests/test_progress_rollup.py` | Added `VariationType` import, added `variation_type=VariationType.COMMON_CAUSE` to 4 calls |
| `tests/test_performance_hotpaths.py` | Added `VariationType` import, added `variation_type=VariationType.COMMON_CAUSE` to 5 calls |

Final test run:
```
15 passed in 17.41s
```

---

## 7. Database Migration

### 7.1 Migration File

`streamlit_app/alembic/versions/f7a8b9c0d1e2_add_learning_loop.py`

### 7.2 Migration Steps

1. Create `experiment` table with indexes
2. Create `retro_experiment_outcome` table with unique constraint
3. Add columns to `check_in`: `variation_type`, `special_cause_note`, `experiment_id`
4. Add FK constraint from `check_in.experiment_id` to `experiment.id`
5. Add index `ix_check_in_kr_var_created`

### 7.3 Rollback

Downgrade removes all new columns and tables.

---

## 8. Security Considerations

### 8.1 Authorization Model

| Operation | Authorization |
|-----------|---------------|
| Create experiment | Goal mutation scope (owner/manager/admin) |
| Read experiments | Goal scoped access (same as mutation) |
| Update experiment | Goal mutation scope |
| Create check-in | Goal mutation scope |
| Attach retro outcome | Retro owner only |

### 8.2 Data Integrity

- Cross-KR experiment linking prevented at CRUD layer
- Cross-cycle experiments prevented via `cycle_id` validation
- Unique constraint prevents duplicate retro outcomes
- Race conditions handled via IntegrityError catch-and-retry

---

## 9. Performance Considerations

### 9.1 Indexes Added

| Table | Index | Purpose |
|-------|-------|---------|
| `check_in` | `ix_check_in_kr_var_created` | Weekly special-cause spike queries |
| `experiment` | `ix_experiment_kr_status` | KR-scoped experiment listing |
| `experiment` | `ix_experiment_cycle_status` | Cycle-scoped analytics |
| `retro_experiment_outcome` | `ux_retro_experiment` | Duplicate prevention |

### 9.2 Caching

- Experiment lists cached in Streamlit session state per KR
- Cache invalidated on experiment creation and check-in submission
- No additional caching added to Atlas snapshot (by design - keeps latency low)

---

## 10. Future Considerations

### 10.1 Potential Enhancements

1. **Quarterly Planning Integration**
   - Show "Top experiments adopted last cycle" during cycle creation
   - Allow promoting experiments to "standards" or "playbooks"

2. **Analytics Dashboard**
   - Special cause frequency by category
   - Experiment success rate by decision type
   - KR score correlation with experiment count

3. **Broader Read Visibility**
   - If needed, implement separate `_authorize_goal_read` with relaxed rules
   - Current implementation documents this possibility

### 10.2 Known Limitations

1. **No Experiment History in Atlas**
   - Deliberately omitted to maintain low-latency snapshot
   - Can be added as optional "experiment summary" fields if needed

2. **Manual Experiment Activation**
   - Experiments start as PLANNED, must be manually set to RUNNING
   - Future: auto-activate on first linked check-in

3. **No Experiment Templates**
   - Each experiment is created from scratch
   - Future: pre-defined experiment types with suggested hypotheses

---

## 11. Deployment Checklist

- [ ] Run `alembic upgrade head` to apply migration
- [ ] Verify new tables exist in database
- [ ] **Test migration on copy of real DB** (not just SQLite) - FK creation on `check_in.experiment_id` may fail if constraint already exists or schema drift occurred
- [ ] Run test suite: `pytest tests/test_learning_loop.py tests/test_progress_rollup.py tests/test_performance_hotpaths.py`
- [ ] **Run end-to-end smoke test for all check-in entry points** (weekly ritual UI, any API hooks, admin utilities)
- [ ] Deploy application code
- [ ] Monitor for any authorization errors in logs
- [ ] Train users on variation classification concepts

### 11.1 Known Breaking Changes

1. **`create_check_in` signature change**
   - `actor_username` is now required (was optional)
   - `variation_type` is now required (enforced at CRUD level)
   - All call sites in `tests/test_progress_rollup.py` and `tests/test_performance_hotpaths.py` were updated
   - If any external scripts or API hooks call `create_check_in`, they must be updated

2. **Migration FK constraint**
   - The migration uses defensive checks for table/column existence
   - FK constraint creation on `check_in.experiment_id` may fail if:
     - Constraint already exists from a partial/failed migration
     - Schema drift has occurred
   - **Recommendation:** Test migration on a copy of production DB before deploying

---

## 12. Files Changed

| File | Lines Changed | Type |
|------|---------------|------|
| `streamlit_app/src/models.py` | ~80 | Modified |
| `streamlit_app/src/domain/authorization.py` | ~20 | Modified |
| `streamlit_app/src/crud.py` | ~250 | Modified |
| `streamlit_app/src/ui/dialogs.py` | ~180 | Modified |
| `streamlit_app/alembic/versions/f7a8b9c0d1e2_*.py` | ~120 | Created |
| `tests/test_learning_loop.py` | ~200 | Created |

**Total:** ~850 lines of code

---

## Appendix A: API Reference

### create_experiment

```python
def create_experiment(
    key_result_id: int,
    cycle_id: int,
    hypothesis: str,
    change_description: str,
    actor_username: str,
    start_at: Optional[datetime] = None,
    expected_effect_direction: Optional[ExpectedEffectDirection] = None,
    expected_effect_size: Optional[float] = None,
) -> Experiment
```

**Raises:**
- `PermissionError`: If actor lacks goal mutation scope
- `ValueError`: If cycle_id doesn't match KR's goal cycle

### create_check_in

```python
def create_check_in(
    kr_id: int,
    value: float,
    confidence: int,
    comment: str,
    actor_username: str,
    variation_type: Optional[VariationType] = None,
    special_cause_note: Optional[str] = None,
    experiment_id: Optional[int] = None,
) -> CheckIn
```

**Raises:**
- `ValueError`: If variation_type is None
- `ValueError`: If SPECIAL_CAUSE and note < 5 chars
- `ValueError`: If experiment_id belongs to different KR
- `PermissionError`: If actor lacks goal mutation scope

### upsert_retro_experiment_outcome

```python
def upsert_retro_experiment_outcome(
    retrospective_id: int,
    experiment_id: int,
    decision: ExperimentDecision,
    rationale: Optional[str],
    actor_username: str,
) -> RetroExperimentOutcome
```

**Raises:**
- `ValueError`: If retrospective or experiment not found
- `PermissionError`: If actor is not retro owner

### list_experiments_for_retro_window

```python
def list_experiments_for_retro_window(
    cycle_id: int,
    window_start: datetime,
    window_end: datetime,
    actor_username: str,
) -> List[Experiment]
```

**Returns:** Experiments that ended in the window OR are still running, filtered by goal-scoped access.

**Raises:**
- `PermissionError`: Per-experiment if actor lacks access (caught internally, experiment excluded from results)

### close_experiment

```python
def close_experiment(
    experiment_id: int,
    decision: ExperimentDecision,
    rationale: str,
    actor_username: str,
) -> Optional[Experiment]
```

**Description:** Closes an experiment by setting status to DECIDED, recording the decision and rationale, and setting `end_at` to current time.

**Raises:**
- `PermissionError`: If actor lacks goal mutation scope

---

## Appendix B: Enum Values Quick Reference

| Enum | Values |
|------|--------|
| `VariationType` | `COMMON_CAUSE`, `SPECIAL_CAUSE` |
| `ExperimentStatus` | `PLANNED`, `RUNNING`, `DECIDED` |
| `ExperimentDecision` | `ADOPT`, `REVERT`, `ITERATE`, `UNKNOWN` |
| `ExpectedEffectDirection` | `UP`, `DOWN` |

---
latest update:

## Summary of Changes

### 1. New CRUD Function (`crud.py`)
```python
def list_experiments_for_retro_window(
    cycle_id, window_start, window_end, actor_username
) -> List[Experiment]
```
- Returns experiments that ended in the week window OR are still RUNNING
- Enforces goal-scoped access per experiment
- Experiments without access are silently excluded

### 2. Weekly Ritual Step 1 (`dialogs.py`)
Added "🔬 Experiments Reviewed This Week" section:
- Lists experiments from `list_experiments_for_retro_window()`
- For each: status badge, hypothesis, decision dropdown, rationale input
- On submit:
  - Calls `upsert_retro_experiment_outcome()` to record outcome linked to retro
  - Calls `close_experiment()` to update Experiment record (status → DECIDED)
- Exceptions caught per-experiment (won't fail retro save)

### 3. Updated Imports
Added to `dialogs.py`:
- `list_experiments_for_retro_window`
- `upsert_retro_experiment_outcome`
- `close_experiment`
- `ExperimentDecision`

### 4. Technical Report Updated
- Section 5.3: Retro experiment review UI documentation
- Appendix A: New `list_experiments_for_retro_window` API reference

### Complete Learning Loop Flow

```
Weekly Ritual Step 1                    Weekly Ritual Step 2
       │                                       │
       │  Write retro content                  │  Update KRs with variation_type
       │  Review experiments                   │  Link to experiments
       │  Record decisions                     │
       ▼                                       ▼
┌─────────────────┐                    ┌─────────────────┐
│ Retrospective   │                    │ CheckIn         │
│ (content)       │                    │ (variation_type)│
└────────┬────────┘                    │ (experiment_id) │
         │                             └────────┬────────┘
         │                                      │
         ▼                                      │
┌─────────────────────────┐                     │
│ RetroExperimentOutcome  │                     │
│ (decision, rationale)   │                     │
└────────┬────────────────┘                     │
         │                                      │
         │ close_experiment()                   │
         ▼                                      ▼
┌─────────────────────────────────────────────────┐
│ Experiment                                      │
│ status=DECIDED, decision, decision_rationale    │
└─────────────────────────────────────────────────┘
```

**Note:** The retro UI calls both `upsert_retro_experiment_outcome()` (to record the outcome linked to the retro) and `close_experiment()` (to update the Experiment record itself). This ensures the learning loop is complete: the decision is captured for institutional memory AND the experiment's status is updated to DECIDED.
