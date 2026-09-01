# GitHub + Darkube Pre-release Evidence Template

Documentation HQ: [README](../../README.md)

**Status:** NOT RECORDED

This checked-in file is a template only. It is not evidence, does not claim that a pre-release passed, and must not be used as production approval. Replace it only with output produced from actual operator observations by:

```text
python scripts/write_prerelease_evidence.py <sanitized-input.json> docs/saas/prerelease-evidence.md
```

The writer accepts only the exact fields below. `null` values are intentionally invalid and indicate that evidence has not been supplied. Do not add URLs, credentials, tokens, secrets, or raw environment dumps.

```json
{
  "commit": null,
  "namespace": null,
  "darkube_build_ids": {
    "web": null,
    "bff": null,
    "api": null,
    "worker": null
  },
  "database_resource_id": null,
  "migration_head": null,
  "health_result": null,
  "smoke_result": null,
  "rollback_result": null,
  "operator": null,
  "timestamp": null
}
```

Allowed check results are `passed`, `failed`, and `not_run`. The writer derives the overall result from those supplied outcomes; it never invents a passing result. Keep this record sanitized and limited to the commit, Darkube namespace/build identifiers, opaque database resource identifier, migration head, check outcomes, operator, and UTC timestamp.
