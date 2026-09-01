"""Write a strict, sanitized GitHub + Darkube pre-release evidence record."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Mapping


SCHEMA_VERSION = 1
BUILD_COMPONENTS = ("web", "bff", "api", "worker")
CHECK_STATUSES = ("passed", "failed", "not_run")
TOP_LEVEL_FIELDS = frozenset(
    {
        "commit",
        "namespace",
        "darkube_build_ids",
        "database_resource_id",
        "migration_head",
        "health_result",
        "smoke_result",
        "rollback_result",
        "operator",
        "timestamp",
    }
)

URL_PATTERN = re.compile(r"(?:https?|ftp|ssh)://|www\.|git@", re.IGNORECASE)
PLACEHOLDER_PATTERN = re.compile(
    r"(?:<[^>]+>|\$\{[^}]+\}|\b(?:TODO|TBD|CHANGEME|PLACEHOLDER|EXAMPLE|SAMPLE|FAKE|DUMMY|MOCK|FIXTURE|SYNTHETIC|UNASSIGNED|UNKNOWN|REDACTED|NOT[_ -]?RECORDED|NOT[_ -]?AVAILABLE)\b)",
    re.IGNORECASE,
)
SENSITIVE_PATTERN = re.compile(
    r"(?:\b(?:password|passwd|secret|token|authorization|bearer|api[_ -]?key|private[_ -]?key|database[_ -]?url)\b|-----BEGIN|\b[A-Z][A-Z0-9_]{2,}\s*=|\b(?:ghp_|glpat-|sk-|xox[bap]-)[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
JWT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")
NAMESPACE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
OPAQUE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
MIGRATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)


class EvidenceValidationError(ValueError):
    """Raised when an evidence payload is incomplete or unsafe to publish."""


def _require_string(value: object, field: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceValidationError(f"{field} must be a non-empty string")
    text = value.strip()
    if _contains_forbidden_content(text):
        raise EvidenceValidationError(f"{field} contains a URL, credential, token, or placeholder")
    if pattern is not None and pattern.fullmatch(text) is None:
        raise EvidenceValidationError(f"{field} has an invalid format")
    return text


def _contains_forbidden_content(text: str) -> bool:
    return bool(URL_PATTERN.search(text) or PLACEHOLDER_PATTERN.search(text) or SENSITIVE_PATTERN.search(text) or JWT_PATTERN.fullmatch(text))


def _require_result(value: object, field: str) -> str:
    if not isinstance(value, str) or value not in CHECK_STATUSES:
        raise EvidenceValidationError(f"{field} must be one of: {', '.join(CHECK_STATUSES)}")
    return value


def _parse_timestamp(value: object) -> str:
    timestamp = _require_string(value, "timestamp", pattern=TIMESTAMP_PATTERN)
    try:
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        if "." not in timestamp:
            raise EvidenceValidationError("timestamp is not a valid UTC timestamp") from error
        try:
            datetime.fromisoformat(timestamp[:-1])
        except ValueError as fractional_error:
            raise EvidenceValidationError("timestamp is not a valid UTC timestamp") from fractional_error
    return timestamp


@dataclass(frozen=True)
class PreReleaseEvidence:
    commit: str
    namespace: str
    darkube_build_ids: Mapping[str, str]
    database_resource_id: str
    migration_head: str
    health_result: str
    smoke_result: str
    rollback_result: str
    operator: str
    timestamp: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "commit", _require_string(self.commit, "commit", pattern=COMMIT_PATTERN))
        object.__setattr__(self, "namespace", _require_string(self.namespace, "namespace", pattern=NAMESPACE_PATTERN))
        if not isinstance(self.darkube_build_ids, Mapping):
            raise EvidenceValidationError("darkube_build_ids must be an object")
        if set(self.darkube_build_ids) != set(BUILD_COMPONENTS):
            raise EvidenceValidationError("darkube_build_ids must contain exactly web, bff, api, and worker")
        build_ids = {
            component: _require_string(
                self.darkube_build_ids[component],
                f"darkube_build_ids.{component}",
                pattern=OPAQUE_ID_PATTERN,
            )
            for component in BUILD_COMPONENTS
        }
        object.__setattr__(self, "darkube_build_ids", build_ids)
        object.__setattr__(
            self,
            "database_resource_id",
            _require_string(self.database_resource_id, "database_resource_id", pattern=OPAQUE_ID_PATTERN),
        )
        object.__setattr__(self, "migration_head", _require_string(self.migration_head, "migration_head", pattern=MIGRATION_PATTERN))
        for field in ("health_result", "smoke_result", "rollback_result"):
            object.__setattr__(self, field, _require_result(getattr(self, field), field))
        object.__setattr__(self, "operator", _require_string(self.operator, "operator"))
        object.__setattr__(self, "timestamp", _parse_timestamp(self.timestamp))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PreReleaseEvidence":
        if not isinstance(payload, Mapping):
            raise EvidenceValidationError("evidence payload must be an object")
        if set(payload) != TOP_LEVEL_FIELDS:
            missing = sorted(TOP_LEVEL_FIELDS - set(payload))
            extra = sorted(set(payload) - TOP_LEVEL_FIELDS)
            parts = []
            if missing:
                parts.append(f"missing fields: {', '.join(missing)}")
            if extra:
                parts.append(f"unknown fields: {', '.join(extra)}")
            raise EvidenceValidationError("; ".join(parts))
        return cls(**{field: payload[field] for field in TOP_LEVEL_FIELDS})

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "commit": self.commit,
            "namespace": self.namespace,
            "darkube_build_ids": dict(self.darkube_build_ids),
            "database_resource_id": self.database_resource_id,
            "migration_head": self.migration_head,
            "health_result": self.health_result,
            "smoke_result": self.smoke_result,
            "rollback_result": self.rollback_result,
            "operator": self.operator,
            "timestamp": self.timestamp,
            "overall_result": "passed"
            if all(getattr(self, field) == "passed" for field in ("health_result", "smoke_result", "rollback_result"))
            else "not_passed",
        }


def render_markdown(evidence: PreReleaseEvidence) -> str:
    payload = json.dumps(evidence.to_dict(), indent=2, sort_keys=False)
    return (
        "# GitHub + Darkube Pre-release Evidence\n\n"
        "**Status:** Recorded from supplied operator inputs; this document is not a production approval.\n\n"
        "The record contains identifiers and check outcomes only. It intentionally excludes URLs, credentials, tokens, and raw environment data.\n\n"
        "```json\n"
        f"{payload}\n"
        "```\n"
    )


def write_evidence(evidence: PreReleaseEvidence, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(evidence), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing the sanitized evidence fields")
    parser.add_argument("output", type=Path, help="Markdown path to write")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        evidence = PreReleaseEvidence.from_dict(payload)
        write_evidence(evidence, args.output)
    except (OSError, json.JSONDecodeError, EvidenceValidationError) as error:
        print(f"Pre-release evidence was not written: {error}")
        return 2
    print(f"Wrote sanitized pre-release evidence to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
