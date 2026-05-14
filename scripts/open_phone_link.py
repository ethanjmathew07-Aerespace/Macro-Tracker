from __future__ import annotations

import ssl
import sys
import urllib.error
import urllib.request

from show_tunnel_url import latest_tunnel_url


def check_url(url: str) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="HEAD")
    context = ssl.create_default_context()

    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # pragma: no cover - network failure messaging
        return False, str(exc)


def main() -> int:
    url = latest_tunnel_url()
    if url is None:
        print("No tunnel URL found in the log yet.")
        return 1

    ok, detail = check_url(url)
    print(f"URL: {url}")
    print(f"Status: {detail}")

    if not ok:
        print("The current tunnel URL is not reachable right now.")
        return 1

    print("The current tunnel URL is reachable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
