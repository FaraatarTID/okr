# BFF topology evidence runbook

Documentation HQ: [README](../README.md)

Use this runbook before approving any change that removes, merges, or thins the
BFF. The evidence must be collected for equivalent traffic and the same release
identity.

Use the [external execution matrix](topology-external-execution-matrix.md) for
the exact command, expected result, evidence, and failure action for each
external check.

## Capture

The operator-controlled GitHub Actions workflow
`.github/workflows/topology-evidence.yml` can capture the SLO artifact for a
configured environment. It requires `TOPOLOGY_BASE_URL`,
`TOPOLOGY_USERNAME`, and `TOPOLOGY_PASSWORD` secrets and uploads only the
sanitized JSON result. The workflow filename prefix accepts only letters,
numbers, underscores, and hyphens. The workflow passes the password through an
environment variable rather than a command-line argument.

1. Capture the current separate-service topology:

   `python scripts/slo_probe.py --base-url <origin> --username <synthetic-user> --password-env <ENV> --release-id <commit-sha> --operator <operator-id> --topology <topology-name> --output evidence/bff-slo.json`

2. Capture a resource snapshot during the probe window:

   `just topology-resources-sampled evidence/bff-resources.json 10 1 <commit-sha> <operator-id> bff`

   The sampled command records peak CPU, latest memory, and sample count per
   container. Use the one-shot `just topology-resources` command only for a
   quick diagnostic.

3. Repeat both steps for the candidate topology, using separate output files.

4. Rehearse the three restart scenarios and record the observations using
   [failure-isolation.example.json](templates/failure-isolation.example.json).
   Validate the completed manifest with:

   `just topology-failure-review evidence/failure-isolation.json`

## Compare and review

Compare the SLO artifacts:

`just topology-compare evidence/bff-slo.json evidence/direct-api-slo.json evidence/topology-comparison.json`

Include resource deltas with:

`just topology-compare-resources evidence/bff-slo.json evidence/direct-api-slo.json evidence/bff-resources.json evidence/direct-api-resources.json evidence/topology-comparison.json`

If container names differ, add a logical mapping file and use
`just topology-compare-mapped` with the same arguments plus
`evidence/resource-map.json`. Start from
[resource-map.example.json](templates/resource-map.example.json) and map only
equivalent logical roles.

Copy
[topology-review.example.json](templates/topology-review.example.json), link
all four evidence categories, and mark each category `passed` only after the
evidence has been reviewed.

Validate the final manifest:

`just topology-review evidence/topology-review.json`

## Approval criteria

A topology change is ready for approval only when:

- the comparison uses matching SLOs and equivalent traffic;
- security parity is explicitly reviewed;
- all required failure-isolation scenarios pass;
- resource overhead is recorded for both candidates;
- a last-known-good rollback has been rehearsed and linked; and
- the final manifest passes `topology-review` validation.

Use [rollback-rehearsal.example.json](templates/rollback-rehearsal.example.json)
and validate it with `just topology-rollback-review` before marking the
`rollback_rehearsal` category as passed.

Do not treat lower latency or lower resource use by itself as approval to
remove the BFF.
