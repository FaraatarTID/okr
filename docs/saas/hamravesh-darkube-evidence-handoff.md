# Hamravesh/Darkube provider evidence handoff

Documentation HQ: [README](../../README.md)

**Status:** operator handoff; not production approval

This is the next operational step for the dedicated single-tenant SaaS path.
It converts one disposable or pilot Hamravesh/Darkube environment's observed
backup, restore, rollback, and ownership results into sanitized evidence for the
repository gate. Do not use customer data until this handoff is complete and
approved.

## Preconditions

- The target environment and customer identity are explicitly approved.
- The database is a dedicated private managed PostgreSQL resource in
  Hamravesh, with application workloads deployed through Darkube.
- Two immutable application release artifacts are available and their digests
  are recorded.
- A named decision owner, platform/operations owner, and recovery operator are
  assigned.
- The attestation secret is available through the approved secret manager; it
  must not be committed, pasted into evidence, or printed in logs.

## Collection sequence

1. Record the environment ID, customer ID, provider database resource identity, current
   release identity, and operator. Record identifiers only; never record the
   endpoint, credentials, or secrets.
2. Create or wait for a completed provider-supported PostgreSQL backup. Capture the
   provider backup identifier, source resource identity, status, creation and
   verification timestamps, retention policy, encryption state, and provider
   integrity/checksum result.
3. Restore into a separate private PostgreSQL rehearsal target. The target must have
   a different provider identity, production access disabled, and no customer
   traffic route.
4. Capture the provider restore identifier, source/target identities, start and
   completion timestamps, integrity result, migration revision, and cleanup
   record. Measure RPO and RTO from observed timestamps, not estimates.
5. Rehearse application rollback as a paired release operation for web, BFF,
   API, and worker. Record old/new immutable artifact digests, deployment
   events, health checks, synthetic login/smoke results, and rollback duration.
6. Verify that the backup and restore evidence belongs to the same environment
   and customer identity as the release and provisioning evidence.
7. Sanitize the evidence and validate it locally:

```powershell
python scripts/verify_recovery_evidence.py --evidence <recovery-evidence.json>
python scripts/validate_rollback_rehearsal.py <rollback-evidence.json>
python scripts/check_saas_phase1_evidence.py
```

The final command requires `OKR_SAAS_ATTESTATION_SECRET` in the environment.
The secret value must never appear in command history, CI output, or evidence.

## Evidence mapping

| Observation | Gate field or artifact |
| --- | --- |
| Hamravesh provider and backup identifier | `backup.provider`, `backup.backup_id`, attestation fields |
| Backup verification/integrity | `backup.verified` and provider record |
| Isolated restore target and restore identifier | `restore.target`, `restore.restore_id` |
| Numeric recovery measurements | `rpo_rto.measured_*` |
| Paired release rollback | `release.artifacts`, `release.rollback_result`, `release.measured_rollback_seconds` |
| Accountability | `owners.decision`, `owners.operations`, operator record |
| Approval | `real_data_approval` and signed attestation |

## No-go conditions

Stop and leave the gate blocked if any item is missing or cannot be verified:

- backup or restore is a disk snapshot rather than a database recovery;
- provider-issued IDs, source/target identity, status, timestamps, or integrity
  evidence are unavailable;
- restore targets the live database or is publicly reachable;
- rollback uses mutable tags, a rebuild, or only one application component;
- RPO/RTO is estimated rather than measured;
- ownership or explicit real-data approval is absent;
- the signed attestation cannot be verified with the approved secret.

The repository checker validates consistency and signature correctness; it does
not prove that Hamravesh performed an operation. Retain access-controlled
Hamravesh/Darkube console records or provider exports for independent review, while placing only the
sanitized metadata in the repository evidence bundle.
