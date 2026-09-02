# Deployment Operations Guide (Compatibility Redirect)
Documentation HQ: [README](../README.md)

This document was consolidated to reduce overlap across deployment docs.

Canonical references (EN):
- Enterprise deployment playbook: [../DEPLOYMENT.md](../DEPLOYMENT.md)
- Runtime policy and env keys: [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)
- Incident and troubleshooting: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Production operations observability and incident runbooks: [OBSERVABILITY_AND_RUNBOOKS.md](OBSERVABILITY_AND_RUNBOOKS.md)
- Retention/backup/recovery readiness and OPS-01 execution evidence: [OPS_READINESS_AND_RECOVERY_GUIDE.md](OPS_READINESS_AND_RECOVERY_GUIDE.md)

## Runtime logging and disposability contract

The API, worker, and BFF write structured JSON lifecycle and error events to
stdout or stderr. The audit and error helpers use process stream handlers only;
they do not create or write operational log files. Events include an event name
and UTC timestamp; request events carry correlation/request identifiers where
available.

Operational logs are metadata-only. Audit events are also persisted in the
database for application audit queries; this durable audit record is separate
from operational log transport. Never log request headers, cookies, request
bodies, passwords, authorization values, service tokens, or signing/session
secrets. Error events use error type/code and sanitized context instead of raw
credentials.

Run the repository gate before release:

```text
python scripts/verify_logging_contract.py
```

The process model is disposable: health checks and orchestrator restart behavior
must be able to replace API, worker, and BFF processes without relying on local
process state. Durable state belongs in configured backing services.
