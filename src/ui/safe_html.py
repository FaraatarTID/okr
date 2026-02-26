"""Utilities for safely embedding dynamic text inside HTML snippets."""

from html import escape
from typing import Any


def escape_html(value: Any) -> str:
    """Return HTML-escaped string for untrusted content."""
    if value is None:
        return ""
    return escape(str(value), quote=True)
