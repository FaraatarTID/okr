"""Compatibility launcher that delegates to the canonical app entrypoint.

Keep this file thin so login/auth logic only lives in `app.py` + auth helpers.
"""

from __future__ import annotations

import app


def main() -> None:
    app.main()


if __name__ == "__main__":
    main()
