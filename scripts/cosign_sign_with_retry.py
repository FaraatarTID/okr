#!/usr/bin/env python3
"""Sign an image digest with Cosign keyless, retrying transient failures.

Run 36634157007 failed because the runner could not reach the GitHub OIDC token endpoint
(`dial tcp ...: i/o timeout`). Cosign then fell back to an interactive device flow that a CI job
cannot complete, waited out its 300 second code, and failed with `expired_token`. The other two
images in the same run signed fine, and a rerun passed, so the failure was transient and cost a
manual rerun.

Signing the same digest twice only adds another signature, so retrying is safe. Each attempt is
bounded by a timeout so a stuck device flow is cut off instead of waiting five minutes. A failure
on every attempt still fails the job: this never turns a signing failure into a pass.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence

DEFAULT_ATTEMPTS = 3
DEFAULT_ATTEMPT_TIMEOUT_SECONDS = 150.0
DEFAULT_BACKOFF_SECONDS = 20.0


def _run_cosign(argv: Sequence[str], timeout: float) -> int:
    """Return cosign's exit code, or 124 when the attempt timed out."""
    executable = shutil.which(argv[0]) or argv[0]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, image ref passed as one element, no shell
            [executable, *argv[1:]], check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return 124
    return completed.returncode


def sign_with_retry(
    image_ref: str,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    attempt_timeout: float = DEFAULT_ATTEMPT_TIMEOUT_SECONDS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    run: Callable[[Sequence[str], float], int] = _run_cosign,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> int:
    """Sign `image_ref` (name@sha256:digest). Return 0 on success, else the last exit code."""
    if "@sha256:" not in image_ref:
        log(
            f"refusing to sign {image_ref!r}: a digest reference (name@sha256:...) is required"
        )
        return 2
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    code = 1
    for attempt in range(1, attempts + 1):
        code = run(["cosign", "sign", "--yes", image_ref], attempt_timeout)
        if code == 0:
            if attempt > 1:
                log(f"signed on attempt {attempt} of {attempts}")
            return 0
        log(f"cosign sign attempt {attempt} of {attempts} failed with exit code {code}")
        if attempt < attempts:
            sleep(backoff_seconds * attempt)
    log(f"cosign sign failed on all {attempts} attempts")
    return code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "image_ref", help="image reference with digest: name@sha256:..."
    )
    parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    parser.add_argument(
        "--attempt-timeout", type=float, default=DEFAULT_ATTEMPT_TIMEOUT_SECONDS
    )
    parser.add_argument("--backoff", type=float, default=DEFAULT_BACKOFF_SECONDS)
    args = parser.parse_args(argv)
    return sign_with_retry(
        args.image_ref,
        attempts=args.attempts,
        attempt_timeout=args.attempt_timeout,
        backoff_seconds=args.backoff,
    )


if __name__ == "__main__":
    sys.exit(main())
