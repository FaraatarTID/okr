Documentation HQ: [README](../../../README.md)

# T04 — Phase 1 evidence gate verification

## Scope and disposition

Verified the re-scoped T04 contract against the existing production promotion and PR workflows. `phase-1-evidence` in `.github/workflows/promote-production.yml:118-140` runs `scripts/check_saas_phase1_evidence.py` with `OKR_SAAS_ATTESTATION_SECRET`. The production `approve-and-prepare` job at lines 142-146 requires `phase-1-evidence`. `.github/workflows/ci.yml:175,346-353` runs the full Python pytest suite under `backend-quality`; the real-bundle checker is absent from PR CI. `tests/test_phase1_promotion_gate.py` asserts that placement, the secret binding, the dependency, and the PR fixture-suite invocation.

**A3: no local repository wiring gap found.** No workflow, application, test, or evidence-bundle source was edited. This is local verification, not remote CI or a promotion run.

**F6: externally blocked.** `docs/saas/phase-1-entry-evidence.md` declares BLOCKED and contains `UNSELECTED` provider/backup/restore IDs, `UNASSIGNED` operations owner, `false` real-data approval, and `UNSET` attestation. Actual provider-issued records, measured recovery and rollback results, provider attestation and secret, named accountable owners, and real-data approval are still required. Existing template numbers and digests do not establish a provider rehearsal.

## Commands and results

From the repository root:

```text
.venv\Scripts\python.exe -m pytest -q tests/test_phase1_promotion_gate.py tests/test_documented_evidence_schema.py tests/test_production_persistence_gate_contract.py tests/test_saas_integration_fix_wave.py tests/test_recovery_evidence.py tests/test_validate_rollback_rehearsal.py tests/test_release_pair.py
71 passed in 0.95s (exit 0)
```

These focused tests cover promotion placement, positive and negative Phase 1 bundle fixtures, recovery signature and evidence rejection, rollback rehearsal integrity/duration fixtures, and release-pair Cosign-reference validation. The full pytest suite was already run for the execution baseline; this packet did not rerun it.

```text
.venv\Scripts\python.exe scripts/check_saas_phase1_evidence.py docs/saas/phase-1-entry-evidence.md
SaaS Phase 1 evidence check failed.
ERROR: decision approval and named owner are required
ERROR: successful isolated restore evidence is required
ERROR: named decision and operations owners are required
ERROR: explicit real-data approval is required
ERROR: attested named decision and operations owners are required
ERROR: attestation signature verification secret is required
exit 1 (expected for the intentionally BLOCKED bundle)
```

The fail-closed output is consistent with the template's explicit BLOCKED decision, absent isolated restore, unassigned operations owner, missing real-data approval, and unset attestation. `git status --short --` on the two workflows, placement test, and evidence bundle showed no changes (Git emitted only a user-config ignore permission warning).

No exact A3 regression was observed. F6 cannot close from local fixtures or repository wiring.
