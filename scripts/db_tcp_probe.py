"""Return DB connectivity status for OKR_DATABASE_URL.

Outputs one token:
- ok
- invalid
- dns_fail
- tcp_fail
"""

from __future__ import annotations

import os
import socket
import sys
from urllib.parse import urlparse


def main() -> int:
    raw = str(os.environ.get("OKR_DATABASE_URL", "")).strip()
    if not raw:
        print("invalid")
        return 0

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme == "sqlite":
        print("ok")
        return 0

    host = (parsed.hostname or "").strip()
    if not host:
        print("invalid")
        return 0

    port = int(parsed.port or 5432)
    try:
        entries = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except Exception:
        print("dns_fail")
        return 0

    seen: set[tuple[str, int]] = set()
    for entry in entries:
        sockaddr = entry[4]
        ip = str(sockaddr[0])
        key = (ip, port)
        if key in seen:
            continue
        seen.add(key)
        try:
            with socket.create_connection((ip, port), timeout=2.0):
                print("ok")
                return 0
        except Exception:
            continue

    print("tcp_fail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
