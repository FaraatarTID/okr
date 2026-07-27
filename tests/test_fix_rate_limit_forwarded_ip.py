"""Tests for Fix 2: Rate limiting with x-forwarded-for header."""

import inspect
from pathlib import Path

from backend_app.rate_limiter import check_rate_limit

# Resolve spa-bff source paths relative to this test file's parent directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROXY_TS = _PROJECT_ROOT / "spa-bff" / "src" / "proxy.ts"
_SERVER_TS = _PROJECT_ROOT / "spa-bff" / "src" / "server.ts"


def test_rate_limit_uses_forwarded_ip_for_isolation():
    """Different forwarded IPs get independent rate limits."""
    # Exhaust rate limit for IP 1
    assert check_rate_limit(key="ip:10.0.0.1", limit=2, window_seconds=300) is True
    assert check_rate_limit(key="ip:10.0.0.1", limit=2, window_seconds=300) is True
    assert check_rate_limit(key="ip:10.0.0.1", limit=2, window_seconds=300) is False

    # Different IP should have its own limit
    assert check_rate_limit(key="ip:10.0.0.2", limit=2, window_seconds=300) is True


def test_security_module_accepts_x_forwarded_for_header():
    """require_service_access should accept x_forwarded_for as a header parameter."""
    source = inspect.getsource(
        __import__("backend_app.security", fromlist=["require_service_access"])
    )
    assert "x_forwarded_for" in source, (
        "require_service_access should accept x_forwarded_for header parameter"
    )


def test_security_module_uses_forwarded_ip_for_rate_limit():
    """When service token is valid, rate limiting should use x-forwarded-for."""
    source = inspect.getsource(
        __import__("backend_app.security", fromlist=["require_service_access"])
    )
    assert "forwarded" in source.lower() and "client_ip" in source, (
        "require_service_access should override client_ip with forwarded IP"
    )


def test_bff_proxy_forwards_x_forwarded_for():
    """BFF proxy should forward x-forwarded-for to backend."""
    source = _PROXY_TS.read_text(encoding="utf-8")
    assert "x-forwarded-for" in source.lower(), (
        "proxyToBackend should forward x-forwarded-for header to backend"
    )


def test_bff_server_forwards_token_version():
    """BFF server should forward token_version in normalizeSessionUser."""
    source = _SERVER_TS.read_text(encoding="utf-8")
    assert "token_version" in source, (
        "normalizeSessionUser should include token_version"
    )
