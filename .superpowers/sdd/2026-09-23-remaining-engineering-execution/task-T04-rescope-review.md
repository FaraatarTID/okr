# T04 re-scope independent review

Verdict: **PASS**

Reviewed `task-T04-rescope-report.md`, the current execution plan and progress ledger, canonical A3/F6, promotion/PR workflows, the existing placement tests and blocked evidence bundle. This is a read-only plan review; the only file written is this report. No behavioral test or remote CI result is claimed.

## Findings

No blocking or minor findings in the requested re-scope.

- Canonical `docs/REMAINING_ENGINEERING_PLAN.md:226` explicitly records A3 as Done: PR `backend-quality` executes the pytest fixture suite, and the real evidence check belongs at production promotion. Current `.github/workflows/promote-production.yml:118-145` has `phase-1-evidence`, invokes the checker with the attestation-secret environment variable, and makes production approval depend on that job. `.github/workflows/ci.yml:175,341,349` contains the backend-quality job and pytest execution. `tests/test_phase1_promotion_gate.py:48-103` pins the existing placement, secret reference, approval dependency, absence from PR CI, and fixture-suite invocation.
- F6 remains an external evidence requirement. The canonical F6 row is Open and the evidence document still records BLOCKED, UNSELECTED provider/backup/restore IDs, false real-data approval, and UNSET signature. Its older statement about missing CI wiring is superseded by the later A3 progress evidence for placement; it does not justify another gate. The revised T04 correctly preserves genuine provider records, measured recovery results, attestation, named owners and approval as prerequisites.
- T04 now refreshes existing acceptance evidence and records disposition. An observed contract regression must be reported precisely for a scoped plan update before code changes. It neither duplicates the production gate nor moves the real bundle into PR CI or treats fixtures as provider proof.
- The plan packet and self-consistency row, ledger checklist and self-consistency row, and both conflict matrices agree. T04 is verification work and no longer reserves workflow/test edit ownership. The matrices explicitly require a proven regression and scoped update before edits. The ledger retains T04 unchecked and records its rationale and risk; prior baseline cross-signoff is qualified as local.
- Independently parsed the packet table, the scoped plan self-consistency table, the ledger checklist and the ledger self-consistency table: each contains exactly 36 IDs, in the exact sequence T00 through T35. A whole-file table-row regex also matches the separate T06 dependency row; the scoped self-consistency table itself has no duplicate.
- Inspected `git diff -- docs/REMAINING_ENGINEERING_PLAN.md`: its existing changes concern F1/F3 wording, D4 client-IP policy, authoritative status routing and the OIDC baseline, consistent with prior reviewed corrections. There is no A3/F6 hunk. Git status shows no application, workflow, test or evidence-bundle modification. The older full-plan review package predates the already-reviewed Origin/P0 fixes, so its other deltas are not attributable to this T04 re-scope; T04 changes are confined to its packet, matrix controls and self-consistency row. No unintended scope change was found in current artifacts.

## Acceptance boundary

PASS accepts the T04 plan correction. It does not mark T04 execution complete, close F6, establish fresh remote CI, or prove provider/deployment facts. The next T04 verification packet should record its focused local acceptance results and preserve the external evidence block.
