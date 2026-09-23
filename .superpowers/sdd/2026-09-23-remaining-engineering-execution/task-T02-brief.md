Documentation HQ: [README](../../../README.md)

# T02 — Read-path payload parity

Status: implementation brief. T03 actor-presence audit is complete. T32 may edit the read-budget PostgreSQL harness but not the read visibility helpers or `tests/test_dual_mode_parity.py`; serialize any overlapping test edits.

## Decision before code changes

The non-admin task visibility predicate is the union of:

1. Task belongs to a goal whose owner is in `scope.owner_ids` (owner/self or a user the actor may manage); OR
2. Task `assignee_id` is in `scope.owner_ids`, even when its parent goal owner is outside that set.

Admins may see all tasks. This follows the existing TCP predicate in `backend_app/response_scope_helpers.py:_filter_tasks_for_scope` and the execution plan's explicit requirement to include an in-scope assignee on an out-of-scope goal. Preserve this predicate identically in TCP and HTTPS/PostgREST paths; do not widen other node/query kinds.

The user decided that an assignee-only task response includes **minimal parent context only**: key result, objective, and goal IDs and display titles. Omit all other out-of-scope parent metadata. TCP and HTTPS payloads must match under this contract.

Rationale: assignment is an independent visibility relationship already recognized by the TCP route. Omitting it in HTTPS loses authorized assigned work; narrowing to parent-goal visibility would break established behavior. Cost if this decision is wrong: task metadata for an in-scope assignee could cross parent-goal ownership boundaries. The behavioral tests must explicitly pin both directions.

## Owned surface

- `backend_app/response_scope_helpers.py` task visibility evaluation.
- `src/services/supabase_api_mode_read.py` `tasks.by_cycle` filter and fallback consistency.
- `tests/test_dual_mode_parity.py` plus narrowly scoped new tests as needed.
- No shared generated artifacts, workflows, actor-presence files, or T32 PostgreSQL budget harness.

## Acceptance

- TCP and HTTPS produce equivalent task payloads for owner-visible and assignee-visible cases.
- Include a task assigned to an in-scope user whose goal owner is out of scope; it remains visible.
- Include an out-of-scope assignee and an out-of-scope goal; the task is excluded.
- Preserve existing F3 closed filters with a negative case per removed filter; complete six-kind restricted non-admin payload parity.
- Remove broad `except Exception: continue` row loss. An injected attribute/query/evaluation failure yields a controlled explicit request error or a bounded behavior documented in code/tests; it must not silently drop the task. Do not expose internal exception text to clients.
- Cover admin positive control and no unauthorized extra metadata.
- Run focused dual-mode tests and relevant typing/lint checks. Update `task-T02` report/snapshot with exact commands/results.
