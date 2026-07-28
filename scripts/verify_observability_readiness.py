#!/usr/bin/env python3
"""Verify OBS-02 operational observability/runbook documentation completeness."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    doc_path = Path("docs/OBSERVABILITY_AND_RUNBOOKS.md")
    if not doc_path.exists():
        print(f"MISSING: {doc_path}")
        return 1

    content = doc_path.read_text(encoding="utf-8")
    required_sections = [
        "API Service Health Dashboard",
        "BFF Boundary Dashboard",
        "Worker Health and Queue Dashboard",
        "Data Layer and Migration Dashboard",
        "Auth and Security Control Dashboard",
        "Audit and User-impact Dashboard",
        "API and BFF reliability",
        "Worker and queue safety",
        "DB and migration integrity",
        "Migration rollback",
        "Credential rotation",
        "Worker dead-letter/retry recovery",
        "Operational simulation evidence checklist",
    ]
    missing = [section for section in required_sections if section not in content]
    if missing:
        for section in missing:
            print(f"MISSING_SECTION: {section}")
        return 1

    required_links = [
        "TROUBLESHOOTING.md",
        "DEPLOYMENT_OPERATIONS_GUIDE.md",
    ]
    for link in required_links:
        if link not in content:
            # Link presence is optional for this contract; fail only on explicit absence.
            print(f"MISSING_LINK: {link}")
            return 1

    print("OBSERVABILITY READINESS CHECK PASSED")
    print("Sections:", len(required_sections), "links:", len(required_links))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
