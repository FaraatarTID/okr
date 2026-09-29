#!/usr/bin/env python3
"""Observe the six BFF-boundary security controls on a live stack and record them.

The security-parity evidence (`docs/evidence/security-parity*.json`) is only worth
anything if each `passed` comes from a request that was actually sent to a running
release. This probe sends those requests and derives every status and every
`observed` sentence from the responses. Nothing here is typed in by hand.

What it needs:
    --web-url      the browser-facing origin (spa-web). Required.
    --username / password  a real account, to obtain a session. Required.
    --bff-url      the BFF's own port. Optional: X-OKR-Actor is not forwarded by
                   spa-web, so actor binding can only be observed here. Without it
                   the control is recorded as `not_observed`, never `passed`.
    --backend-url  the backend's own port. Optional, same rule for request signing.
    --service-token  optional. With it, the probe also shows that a valid token with a
                   missing or wrong signature is refused. Without it, only the token
                   check is observed.

The probe never writes a credential, cookie or response body. It records status
codes, error codes and header attributes.

Exit code: 0 when every control passed, 1 when any control failed or was not
observed, 2 for a setup problem.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CONTROL_NAMES = (
    "session_cookie_protection",
    "csrf_and_origin_controls",
    "actor_binding",
    "request_signing",
    "route_allowlisting",
    "rate_limiting",
)
ARTIFACT_NAMES = {
    "session_cookie_protection": "session-cookie.json",
    "csrf_and_origin_controls": "csrf-origin.json",
    "actor_binding": "actor-binding.json",
    "request_signing": "request-signing.json",
    "route_allowlisting": "route-allowlist.json",
    "rate_limiting": "rate-limit.json",
}
SESSION_COOKIE = "okr_spa_session"
CSRF_COOKIE = "okr_csrf_token"
MUTATION_PATH = "/api/backend/v1/weekly-plans"
BACKEND_QUERY = {"kind": "cycles.active", "params": {}, "actor_username": "admin"}


@dataclass
class Response:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    set_cookies: list[str] = field(default_factory=list)
    body: Any = None

    @property
    def code(self) -> str:
        if isinstance(self.body, dict):
            value = self.body.get("code") or self.body.get("error_code")
            if isinstance(value, str):
                return value
        return ""

    @property
    def detail(self) -> str:
        if isinstance(self.body, dict):
            value = self.body.get("detail") or self.body.get("message")
            if isinstance(value, str):
                return value
        return ""


Transport = Callable[[str, str, dict[str, str], bytes | None], Response]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        return None


def http_transport(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> Response:
    """Send one request. Redirects are not followed, so a 3xx is reported as sent."""
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(request, timeout=30) as reply:
            status, message, raw = int(reply.status), reply.headers, reply.read()
    except urllib.error.HTTPError as exc:
        status, message, raw = int(exc.code), exc.headers, exc.read()
    try:
        parsed: Any = json.loads(raw.decode("utf-8")) if raw.strip() else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    return Response(
        status=status,
        headers={key.lower(): value for key, value in message.items()},
        set_cookies=list(message.get_all("Set-Cookie") or []),
        body=parsed,
    )


@dataclass
class Check:
    name: str
    expected: str
    actual: str
    passed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.name,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
        }


def _describe(response: Response) -> str:
    return f"{response.status} {response.code}".strip()


def _expect(
    name: str, response: Response, *, status: int, code: str | None = None
) -> Check:
    expected = f"{status} {code}".strip() if code else str(status)
    ok = response.status == status and (code is None or response.code == code)
    return Check(name, expected, _describe(response), ok)


def _refuse(name: str, response: Response, *, not_code: str) -> Check:
    """The request got past a gate: anything except that gate's own refusal."""
    ok = response.code != not_code and response.status != 502
    return Check(name, f"not {not_code}", _describe(response), ok)


@dataclass
class Target:
    web_url: str
    username: str
    password: str
    bff_url: str = ""
    backend_url: str = ""
    service_token: str = ""
    max_burst: int = 200


def _json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _post(
    send: Transport, url: str, payload: dict[str, Any], headers: dict[str, str]
) -> Response:
    merged = {"Content-Type": "application/json", **headers}
    return send("POST", url, merged, _json(payload))


def _cookie_attributes(raw: str) -> tuple[str, dict[str, str]]:
    parts = [part.strip() for part in raw.split(";")]
    name, _, _ = parts[0].partition("=")
    attributes: dict[str, str] = {}
    for part in parts[1:]:
        key, _, value = part.partition("=")
        attributes[key.strip().lower()] = value.strip()
    return name.strip(), attributes


@dataclass
class Session:
    cookie_header: str
    csrf_token: str
    username: str


def probe_session_cookie(
    send: Transport, target: Target
) -> tuple[list[Check], Session | None]:
    same_origin = {"Sec-Fetch-Site": "same-origin"}
    reply = _post(
        send,
        f"{target.web_url}/api/session/login",
        {"username": target.username, "password": target.password},
        same_origin,
    )
    checks = [_expect("login succeeds", reply, status=200)]
    cookies = dict(_cookie_attributes(raw) for raw in reply.set_cookies)
    values = {
        raw.split("=", 1)[0].strip(): raw.split(";", 1)[0].split("=", 1)[1].strip()
        for raw in reply.set_cookies
        if "=" in raw.split(";", 1)[0]
    }
    session_attrs = cookies.get(SESSION_COOKIE)
    checks.append(
        Check(
            "session cookie is issued",
            f"{SESSION_COOKIE} present",
            "present" if session_attrs is not None else "absent",
            session_attrs is not None,
        )
    )
    attrs = session_attrs or {}
    checks.append(
        Check(
            "session cookie is HttpOnly",
            "HttpOnly",
            "HttpOnly" if "httponly" in attrs else "missing",
            "httponly" in attrs,
        )
    )
    same_site = attrs.get("samesite", "")
    checks.append(
        Check(
            "session cookie is SameSite=Lax or Strict",
            "SameSite=Lax|Strict",
            f"SameSite={same_site}" if same_site else "missing",
            same_site.lower() in {"lax", "strict"},
        )
    )
    max_age = attrs.get("max-age", "")
    checks.append(
        Check(
            "session cookie has a bounded lifetime",
            "Max-Age > 0",
            f"Max-Age={max_age}" if max_age else "missing",
            max_age.isdigit() and int(max_age) > 0,
        )
    )
    if target.web_url.lower().startswith("https://"):
        checks.append(
            Check(
                "session cookie is Secure over HTTPS",
                "Secure",
                "Secure" if "secure" in attrs else "missing",
                "secure" in attrs,
            )
        )
    csrf = values.get(CSRF_COOKIE, "")
    checks.append(
        Check(
            "CSRF cookie is issued",
            f"{CSRF_COOKIE} present",
            "present" if csrf else "absent",
            bool(csrf),
        )
    )
    if not session_attrs or not csrf:
        return checks, None
    return checks, Session(
        cookie_header=f"{SESSION_COOKIE}={values[SESSION_COOKIE]}; "
        f"{CSRF_COOKIE}={csrf}",
        csrf_token=csrf,
        username=target.username,
    )


def probe_csrf_and_origin(
    send: Transport, target: Target, session: Session | None
) -> list[Check]:
    login = f"{target.web_url}/api/session/login"
    ghost = {"username": "no-such-user", "password": secrets.token_hex(8)}
    checks = [
        _expect(
            "cross-site login is refused",
            _post(send, login, ghost, {"Sec-Fetch-Site": "cross-site"}),
            status=403,
            code="INVALID_ORIGIN",
        ),
        _expect(
            "login from a foreign Origin is refused",
            _post(send, login, ghost, {"Origin": "http://evil.invalid"}),
            status=403,
            code="INVALID_ORIGIN",
        ),
        _refuse(
            "same-origin login passes the origin guard",
            _post(send, login, ghost, {"Sec-Fetch-Site": "same-origin"}),
            not_code="INVALID_ORIGIN",
        ),
    ]
    if session is None:
        return checks + [
            Check("CSRF checks need a session", "session", "no session", False)
        ]
    url = f"{target.web_url}{MUTATION_PATH}"
    base = {"Cookie": session.cookie_header}
    checks += [
        _expect(
            "cross-site state change with a valid session is refused",
            _post(
                send,
                url,
                {},
                {
                    **base,
                    "Sec-Fetch-Site": "cross-site",
                    "X-XSRF-TOKEN": session.csrf_token,
                },
            ),
            status=403,
            code="INVALID_ORIGIN",
        ),
        _expect(
            "state change without the CSRF header is refused",
            _post(send, url, {}, {**base, "Sec-Fetch-Site": "same-origin"}),
            status=403,
            code="INVALID_CSRF_TOKEN",
        ),
        _expect(
            "state change with a wrong CSRF header is refused",
            _post(
                send,
                url,
                {},
                {
                    **base,
                    "Sec-Fetch-Site": "same-origin",
                    "X-XSRF-TOKEN": "not-the-token",
                },
            ),
            status=403,
            code="INVALID_CSRF_TOKEN",
        ),
        _refuse(
            "state change with the matching CSRF header passes the CSRF gate",
            _post(
                send,
                url,
                {},
                {
                    **base,
                    "Sec-Fetch-Site": "same-origin",
                    "X-XSRF-TOKEN": session.csrf_token,
                },
            ),
            not_code="INVALID_CSRF_TOKEN",
        ),
    ]
    return checks


def probe_actor_binding(
    send: Transport, target: Target, session: Session | None
) -> list[Check] | None:
    if not target.bff_url or session is None:
        return None
    url = f"{target.bff_url}{MUTATION_PATH}"
    base = {"Cookie": session.cookie_header, "X-XSRF-TOKEN": session.csrf_token}
    return [
        _expect(
            "a client-supplied X-OKR-Actor that is not the session actor is refused",
            _post(send, url, {}, {**base, "X-OKR-Actor": "someone-else"}),
            status=403,
            code="INVALID_ACTOR_HEADER",
        ),
        _refuse(
            "X-OKR-Actor equal to the session actor is accepted",
            _post(send, url, {}, {**base, "X-OKR-Actor": session.username}),
            not_code="INVALID_ACTOR_HEADER",
        ),
    ]


def probe_request_signing(send: Transport, target: Target) -> list[Check] | None:
    if not target.backend_url:
        return None
    url = f"{target.backend_url}/v1/read/query"
    checks = [
        _expect(
            "backend refuses a request with no service token",
            _post(send, url, BACKEND_QUERY, {}),
            status=401,
        ),
        _expect(
            "backend refuses a wrong service token",
            _post(send, url, BACKEND_QUERY, {"X-OKR-Service-Token": "wrong"}),
            status=401,
        ),
    ]
    if target.service_token:
        token = {"X-OKR-Service-Token": target.service_token}
        unsigned = _post(send, url, BACKEND_QUERY, token)
        checks.append(
            Check(
                "a valid token without signature headers is refused",
                "401 Missing signed request headers",
                f"{unsigned.status} {unsigned.detail}".strip(),
                unsigned.status == 401 and "signed request headers" in unsigned.detail,
            )
        )
        forged = _post(
            send,
            url,
            BACKEND_QUERY,
            {
                **token,
                "X-OKR-Signature": "0" * 64,
                "X-OKR-Timestamp": str(int(datetime.now(UTC).timestamp())),
                "X-OKR-Nonce": secrets.token_hex(8),
            },
        )
        checks.append(
            Check(
                "a valid token with a forged signature is refused",
                "401 Invalid request signature",
                f"{forged.status} {forged.detail}".strip(),
                forged.status == 401 and "Invalid request signature" in forged.detail,
            )
        )
    return checks


def probe_route_allowlisting(send: Transport, target: Target) -> list[Check]:
    same_origin = {"Sec-Fetch-Site": "same-origin"}
    base = f"{target.web_url}/api/backend"
    return [
        _expect(
            "an unlisted GET route is refused",
            send("GET", f"{base}/v1/not-a-route", same_origin, None),
            status=403,
            code="ROUTE_NOT_ALLOWLISTED",
        ),
        _expect(
            "an unlisted POST route is refused",
            _post(send, f"{base}/v1/not-a-route", {}, same_origin),
            status=403,
            code="ROUTE_NOT_ALLOWLISTED",
        ),
        _expect(
            "the removed /v1/state/{key} route is refused",
            send("GET", f"{base}/v1/state/anything", same_origin, None),
            status=403,
            code="ROUTE_NOT_ALLOWLISTED",
        ),
    ]


def probe_rate_limiting(send: Transport, target: Target) -> list[Check]:
    """Burst wrong-credential logins from one client key until the limiter answers.

    The username does not exist, so no real account can be locked out. The probe
    supplies X-OKR-Client-IP itself, standing in for the edge that sets it in a real
    deployment; that is recorded, not hidden.
    """
    url = f"{target.web_url}/api/session/login"
    octet = 1 + secrets.randbelow(250)
    key = f"198.51.100.{octet}"
    other = f"198.51.100.{1 + (octet % 250)}"
    headers = {"Sec-Fetch-Site": "same-origin", "X-OKR-Client-IP": key}
    body = {"username": "no-such-user", "password": secrets.token_hex(8)}
    first_limited: Response | None = None
    accepted = 0
    for _ in range(target.max_burst):
        reply = _post(send, url, body, headers)
        if reply.status == 429:
            first_limited = reply
            break
        accepted += 1
    if first_limited is None:
        return [
            Check(
                f"the limiter answers within {target.max_burst} attempts",
                "429 RATE_LIMITED",
                f"no 429 after {accepted} attempts",
                False,
            )
        ]
    retry_after = first_limited.headers.get("retry-after", "")
    neighbour = _post(send, url, body, {**headers, "X-OKR-Client-IP": other})
    return [
        Check(
            "the limiter refuses an over-budget client",
            "429 RATE_LIMITED",
            _describe(first_limited),
            first_limited.code == "RATE_LIMITED",
        ),
        Check(
            "the refusal carries Retry-After",
            "Retry-After > 0",
            f"Retry-After={retry_after}" if retry_after else "missing",
            retry_after.isdigit() and int(retry_after) > 0,
        ),
        Check(
            "attempts accepted before the first refusal",
            ">= 1",
            str(accepted),
            accepted >= 1,
        ),
        Check(
            "a different client key is not throttled by that burst",
            "not 429",
            _describe(neighbour),
            neighbour.status != 429,
        ),
    ]


def _control(name: str, checks: list[Check] | None) -> dict[str, Any]:
    if checks is None:
        return {
            "name": name,
            "status": "not_observed",
            "observed": (
                "Not observed: the target this control needs was not supplied "
                "to the probe."
            ),
            "checks": [],
        }
    passed = all(check.passed for check in checks)
    summary = "; ".join(
        f"{check.name} -> {check.actual}" + ("" if check.passed else " (FAILED)")
        for check in checks
    )
    passed_count = sum(1 for check in checks if check.passed)
    return {
        "name": name,
        "status": "passed" if passed and checks else "failed",
        "observed": f"{passed_count} of {len(checks)} checks passed. {summary}.",
        "checks": [check.as_dict() for check in checks],
    }


def run_probe(target: Target, send: Transport = http_transport) -> list[dict[str, Any]]:
    cookie_checks, session = probe_session_cookie(send, target)
    results = {
        "session_cookie_protection": _control(
            "session_cookie_protection", cookie_checks
        ),
        "csrf_and_origin_controls": _control(
            "csrf_and_origin_controls", probe_csrf_and_origin(send, target, session)
        ),
        "actor_binding": _control(
            "actor_binding", probe_actor_binding(send, target, session)
        ),
        "request_signing": _control(
            "request_signing", probe_request_signing(send, target)
        ),
        "route_allowlisting": _control(
            "route_allowlisting", probe_route_allowlisting(send, target)
        ),
        # Last, because it spends a login budget.
        "rate_limiting": _control("rate_limiting", probe_rate_limiting(send, target)),
    }
    return [results[name] for name in CONTROL_NAMES]


def build_document(
    controls: list[dict[str, Any]],
    *,
    release_id: str,
    operator: str,
    topology: str,
    notes: list[str],
    captured_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "release_id": release_id,
        "captured_at": captured_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "operator": operator,
        "topology": topology,
        "capture_notes": notes,
        "controls": controls,
    }


def write_evidence(
    document: dict[str, Any], *, evidence_dir: Path, artifact_dir: str, summary: str
) -> list[Path]:
    """Write one artifact per control plus the summary that points at them."""
    metadata = {
        key: document[key]
        for key in ("release_id", "captured_at", "operator", "topology")
    }
    written: list[Path] = []
    summary_controls = []
    target_dir = evidence_dir / artifact_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    for control in document["controls"]:
        artifact = f"{artifact_dir}/{ARTIFACT_NAMES[control['name']]}"
        payload = {
            "schema_version": SCHEMA_VERSION,
            **metadata,
            "control": control["name"],
            "status": control["status"],
            "observed": control["observed"],
            "checks": control["checks"],
            "capture_notes": document["capture_notes"],
        }
        path = evidence_dir / artifact
        path.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        written.append(path)
        summary_controls.append(
            {
                "name": control["name"],
                "status": control["status"],
                "observed": control["observed"],
                "artifact": artifact,
            }
        )
    summary_payload = {
        "schema_version": SCHEMA_VERSION,
        **metadata,
        "capture_notes": document["capture_notes"],
        "controls": summary_controls,
    }
    summary_path = evidence_dir / summary
    summary_path.write_text(
        json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    written.append(summary_path)
    return written


def capture_notes(target: Target, extra: list[str]) -> list[str]:
    """Limits of this capture that the checks themselves cannot show."""
    notes = list(extra)
    if not target.web_url.lower().startswith("https://"):
        notes.append(
            "The web origin was plain HTTP, so the Secure cookie attribute was not "
            "observed. session_cookie_protection covers HttpOnly, SameSite and a "
            "bounded lifetime only."
        )
    if not target.bff_url:
        notes.append("No BFF address was given: actor_binding was not observed.")
    if not target.backend_url:
        notes.append("No backend address was given: request_signing was not observed.")
    elif not target.service_token:
        notes.append(
            "No service token was given: only the service-token check of request "
            "signing was observed, not the signature check."
        )
    notes.append(
        "rate_limiting supplies its own X-OKR-Client-IP, standing in for the edge "
        "that sets it in a real deployment."
    )
    return notes


def _read_password(args: argparse.Namespace) -> str:
    if args.password_file:
        return Path(args.password_file).read_text(encoding="utf-8").strip()
    return os.environ.get("OKR_PROBE_PASSWORD", "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-url", required=True)
    parser.add_argument("--bff-url", default="")
    parser.add_argument("--backend-url", default="")
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--password-file", help="File holding the password; else $OKR_PROBE_PASSWORD."
    )
    parser.add_argument("--service-token-file", default="")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--topology", default="bff")
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--max-burst", type=int, default=200)
    parser.add_argument("--output", type=Path, help="Write the raw result here.")
    parser.add_argument("--write-evidence", type=Path, metavar="EVIDENCE_DIR")
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--summary-name", default="")
    args = parser.parse_args(argv)

    password = _read_password(args)
    if not password:
        print("A password is required (--password-file or $OKR_PROBE_PASSWORD).")
        return 2
    if args.write_evidence and not (args.artifact_dir and args.summary_name):
        print("--write-evidence needs --artifact-dir and --summary-name.")
        return 2
    token = ""
    if args.service_token_file:
        token = Path(args.service_token_file).read_text(encoding="utf-8").strip()
    target = Target(
        web_url=args.web_url.rstrip("/"),
        username=args.username,
        password=password,
        bff_url=args.bff_url.rstrip("/"),
        backend_url=args.backend_url.rstrip("/"),
        service_token=token,
        max_burst=args.max_burst,
    )
    document = build_document(
        run_probe(target),
        release_id=args.release_id,
        operator=args.operator,
        topology=args.topology,
        notes=capture_notes(target, list(args.note)),
    )
    for control in document["controls"]:
        print(f"{control['name']}: {control['status']}")
        for check in control["checks"]:
            mark = "ok  " if check["passed"] else "FAIL"
            print(f"  {mark} {check['check']} -> {check['actual']}")
    if args.output:
        args.output.write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    if args.write_evidence:
        write_evidence(
            document,
            evidence_dir=args.write_evidence,
            artifact_dir=args.artifact_dir,
            summary=args.summary_name,
        )
    return 0 if all(c["status"] == "passed" for c in document["controls"]) else 1


if __name__ == "__main__":
    sys.exit(main())
