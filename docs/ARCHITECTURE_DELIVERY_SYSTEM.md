# Architecture Delivery System — Operating Guide

Documentation HQ: [README](README.md)

This document defines the system used to track execution of
[ARCHITECTURE_BACKLOG.md](../ARCHITECTURE_BACKLOG.md) — not just marking items
done, but verifying each fix actually fulfills its purpose in the running
system.

## Why this exists

Backlogs fail in two ways: work is marked done without evidence, or work is
completed but never validated against the problem it was meant to solve. This
system closes both gaps with a **status ledger** (where things stand) and a
**verification loop** (proof each fix works as intended).

## File layout

| File | Purpose | Lifetime |
|---|---|---|
| `ARCHITECTURE_BACKLOG.md` | The plan: what/why/DoD per item | Permanent |
| `docs/architecture-status.md` | The ledger: per-item status, evidence links, verification results | Permanent (living) |
| `docs/WORKLOG.md` | The journal: dated entries of what was done each session | Append-only (gitignored) |

## Item lifecycle

Each backlog item moves through five states, tracked in the status ledger:

```
PLANNED → IN-PROGRESS → IMPLEMENTED → VERIFIED → CLOSED
                              │
                              └── BLOCKED (with reason + unblock condition)
```

- **IMPLEMENTED** means code merged and CI green.
- **VERIFIED** means the item's *purpose* was confirmed against the running
  system — not just tests passing. Each P0 item has a defined verification
  drill below.
- **CLOSED** requires both, plus a one-line "did it solve the problem?"
  retrospective note.

An item may only move to CLOSED by the verification drill, never by test suite
green alone.

## Status ledger format (`docs/architecture-status.md`)

One table row per backlog item:

```markdown
| Item | Status | Evidence | Verified | Retro note |
|---|---|---|---|---|
| Key rotation playbook | VERIFIED | PR #x; tests/test_signing_rotation.py | 2026-08-24 drill #1 | Overlap window worked; unknown-ID rejection clear |
```

Rules:
1. **Evidence** links to PR/commit and the test file(s) added.
2. **Verified** records the date the purpose-drill ran and its outcome.
3. **Retro note** is one line written at closure: did it solve the original
   finding? Any surprise?

## Verification drills (the loop)

Each P0 item defines how to prove it fulfills its purpose on the live system:

### 1. OpenAPI codegen drift gate
- **Drill**: Make a deliberate breaking change to a read-kind payload shape on
  a scratch branch. Confirm CI fails at the drift gate with an actionable diff.
  Revert. Confirm CI passes.
- **Passes when**: The gate catches the break without manual triage.
- **Cadence**: Once at implementation; re-run if codegen tooling changes.

### 2. Signing key rotation
- **Drill**: Execute the full runbook end-to-end locally: generate key v2 →
  deploy verify-only → switch signing to v2 → confirm zero rejected requests in
  logs during overlap → retire v1 → confirm old-key rejection after retirement.
- **Passes when**: Zero valid-request rejections during overlap; clean
  rejection after retirement.
- **Cadence**: Once at implementation; rehearsed every quarter thereafter.

### 3. SLO definitions
- **Drill**: Run the SLO measurement script against the live stack for one full
  day. Confirm every metric produces a value, thresholds trigger correctly
  (unit-tested), and the runbook's corrective action for a breach is actionable.
- **Passes when**: One day of real data maps cleanly onto targets with no
  ambiguous metrics.
- **Cadence**: Weekly during the first month, then monthly.

### 4. Dead-letter job visibility
- **Drill**: Inject a deliberately failing job (scratch kind or bad payload).
  Confirm it appears in `GET /v1/jobs/dead`, healthz count increments, admin
  retry re-runs it, and non-admin access is denied.
- **Passes when**: Full inject → discover → retry → resolve cycle completes
  without SQL access.
- **Cadence**: Once at implementation; included in quarterly ops rehearsal.

## Worklog discipline

Each working session appends to `docs/WORKLOG.md`:

```markdown
## 2026-08-24 — Key rotation: key-ID header
- Added x-okr-key-id parsing to backend_app/security.py
- Tests: 4 new cases in tests/test_signing_rotation.py
- Next: overlap-window verification path
- Blockers: none
```

Rules:
1. One entry per session, newest first.
2. Always include a **Next** line — this is what makes the loop resumable.
3. Blockers are stated even when "none" so stalls become visible.

## Review cadence

- **Per session**: update worklog; move ledger statuses honestly.
- **Biweekly**: review the ledger — anything stuck in IN-PROGRESS >2 weeks gets
  a blocker reason or is descoped. Re-check P2 promotion triggers.
- **Quarterly**: re-run all four verification drills; re-assess whether closed
  items still fulfill their purpose after intervening changes. Record outcomes
  in the ledger's retro column.

## Anti-goals

- No status meetings or ceremony beyond the biweekly self-review.
- No separate tracking tools — git + these three files are the system.
- No "done" without a dated verification entry.
