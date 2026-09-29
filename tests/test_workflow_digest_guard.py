"""The digest guard in the signature-verification workflows must accept a real digest.

Four steps in three `workflow_dispatch`-only workflows guarded each image digest with
`test "$digest" = sha256:*`. Inside `test`, the right-hand side is a literal string, not a
glob, so the comparison was false for every real digest and each step failed before it
reached `cosign verify`. Nothing noticed: the workflows never ran, and the wiring tests
read the workflow text without executing any of it.

This test executes the guard lines that the workflows actually contain, so it fails on the
defect and not merely on a change of wording. It accepts a well-formed digest and
rejects every malformed shape the Python verifier (`_DIGEST_RE`) also rejects.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

GUARDED = (
    "promote-production.yml",
    "rollback-production.yml",
    "verify-ghcr-signatures.yml",
)

GOOD_DIGEST = "sha256:" + "0123456789abcdef" * 4
RELEASE_SHA = "a" * 40
GOOD_IMAGE = f"ghcr.io/example/okr-web:{RELEASE_SHA}"

BAD_DIGESTS = {
    "another algorithm": "md5:" + "a" * 64,
    "no prefix": "0123456789abcdef" * 4,
    "empty": "",
    "prefix only": "sha256:",
    "too short": "sha256:" + "a" * 63,
    "too long": "sha256:" + "a" * 65,
    "upper case hex": "sha256:" + "A" * 64,
    "trailing junk": GOOD_DIGEST + "; echo pwned",
    "embedded newline": GOOD_DIGEST + "\nsha256:" + "b" * 64,
}


def _bash() -> str | None:
    """A real POSIX bash. On Windows `bash` on PATH is often the WSL launcher, so prefer Git's."""
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ]
    for candidate in candidates:
        if os.name == "nt" and Path(candidate).is_file():
            return candidate
    return shutil.which("bash") if os.name != "nt" else None


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="a POSIX bash is required")


def _bash_path() -> str:
    """The bash to run. The skip marker guarantees it exists; this narrows the type."""
    assert BASH is not None, "a POSIX bash is required"
    return BASH


def _guard_scripts(workflow: str) -> list[str]:
    """Return, for each verification loop in `workflow`, the guard lines before `cosign verify`."""
    yaml = pytest.importorskip("yaml")
    document = yaml.load(
        (WORKFLOWS / workflow).read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    guards: list[str] = []
    for job in (document.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            script = step.get("run") or ""
            if "cosign verify" not in script:
                continue
            match = re.search(
                r"read -r image digest; do\n(?P<body>.*?)\n\s*cosign verify",
                script,
                re.S,
            )
            assert match, (
                f"{workflow}: could not find the guard lines before cosign verify"
            )
            guards.append(match.group("body"))
    return guards


def _run_guard(
    body: str, *, image: str, digest: str
) -> subprocess.CompletedProcess[str]:
    script = "set -euo pipefail\n" + body + "\necho GUARD_PASSED\n"
    return subprocess.run(
        [_bash_path(), "-c", script],
        env={
            "PATH": os.environ.get("PATH", ""),
            "RELEASE_SHA": RELEASE_SHA,
            "image": image,
            "digest": digest,
        },
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_every_signature_verification_loop_is_found() -> None:
    """A guard that silently matches nothing would pass everything below."""
    assert sum(len(_guard_scripts(name)) for name in GUARDED) == 4


@pytest.mark.parametrize("workflow", GUARDED)
def test_a_well_formed_digest_reaches_cosign(workflow: str) -> None:
    for body in _guard_scripts(workflow):
        result = _run_guard(body, image=GOOD_IMAGE, digest=GOOD_DIGEST)
        assert result.returncode == 0 and "GUARD_PASSED" in result.stdout, (
            f"{workflow}: a valid digest was refused before cosign verify\n"
            f"guard:\n{body}\nstderr: {result.stderr}"
        )


@pytest.mark.parametrize("workflow", GUARDED)
@pytest.mark.parametrize("label", sorted(BAD_DIGESTS))
def test_a_malformed_digest_is_refused_before_cosign(workflow: str, label: str) -> None:
    for body in _guard_scripts(workflow):
        result = _run_guard(body, image=GOOD_IMAGE, digest=BAD_DIGESTS[label])
        assert result.returncode != 0 and "GUARD_PASSED" not in result.stdout, (
            f"{workflow}: a {label} digest passed the guard\nguard:\n{body}"
        )


@pytest.mark.parametrize("workflow", GUARDED)
def test_every_image_the_real_manifest_producer_emits_passes_the_guard(
    workflow: str, tmp_path: Path
) -> None:
    """Tie the guard to the producer, not to digests invented in this file.

    `create_release_manifest.build_manifest` is what writes the manifest these workflows
    read, so its output is the input the guard meets in production.
    """
    import hashlib
    import json

    from scripts.create_release_manifest import build_manifest

    commit = "0123456789abcdef0123456789abcdef01234567"
    for name in ("web", "bff", "backend"):
        (tmp_path / f"{name}.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "commit_sha": commit,
                    "image": f"ghcr.io/faraatartid/okr/{name}:{commit}",
                    "digest": f"sha256:{hashlib.sha256(name.encode()).hexdigest()}",
                }
            ),
            encoding="utf-8",
        )
    manifest = build_manifest(tmp_path, "FaraatarTID/okr", commit)

    guards = _guard_scripts(workflow)
    assert guards
    for entry in manifest["images"].values():
        for body in guards:
            result = subprocess.run(
                [
                    _bash_path(),
                    "-c",
                    "set -euo pipefail\n" + body + "\necho GUARD_PASSED\n",
                ],
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "RELEASE_SHA": commit,
                    "image": entry["image"],
                    "digest": entry["digest"],
                },
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0 and "GUARD_PASSED" in result.stdout, (
                f"{workflow}: the producer's own output was refused: {entry}\n{result.stderr}"
            )


@pytest.mark.parametrize("workflow", GUARDED)
def test_an_image_not_tagged_with_the_release_sha_is_refused(workflow: str) -> None:
    for body in _guard_scripts(workflow):
        result = _run_guard(
            body, image="ghcr.io/example/okr-web:" + "b" * 40, digest=GOOD_DIGEST
        )
        assert result.returncode != 0 and "GUARD_PASSED" not in result.stdout
