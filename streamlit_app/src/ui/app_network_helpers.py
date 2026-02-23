"""Network and request transport helpers extracted from app.py."""

from __future__ import annotations


def get_client_ip_from_streamlit(*, st_module) -> str | None:
    """Best-effort client IP extraction from Streamlit request headers."""
    try:
        context = getattr(st_module, "context", None)
        headers = getattr(context, "headers", None) if context is not None else None
        if headers is None:
            return None

        header_map = {
            str(key).lower(): str(value) for key, value in dict(headers).items()
        }
        for key in [
            "x-forwarded-for",
            "x-real-ip",
            "cf-connecting-ip",
            "x-client-ip",
            "x-cluster-client-ip",
        ]:
            value = header_map.get(key)
            if value:
                return value.split(",", 1)[0].strip() or None
    except Exception:
        return None
    return None
