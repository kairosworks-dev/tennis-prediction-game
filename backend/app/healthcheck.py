"""Container health probe: `python -m app.healthcheck`.

Does GET /health on the local port and exits 0 on HTTP 200, 1 on anything else.
The deployment platform's command-type health check accepts only letters,
digits, space and `-_./:=@,+`, so an inline `python -c "..."` probe cannot be
configured there. This module has no such characters to escape: the image
HEALTHCHECK and the platform's check run the same command.

Standard library only, and no import from the app: the probe must not depend on
what it is probing.
"""

from __future__ import annotations

import sys
import urllib.request

HEALTH_URL = "http://127.0.0.1:8000/health"


def main(url: str = HEALTH_URL, timeout: float = 3.0) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 0 if response.status == 200 else 1
    except Exception:
        # HTTPError (non-2xx), URLError, timeout, refused connection: all unhealthy.
        return 1


if __name__ == "__main__":
    sys.exit(main())
