from __future__ import annotations

import re
from pathlib import Path


LOG_PATHS = [
    Path("/Users/ethanjmathew/macro-tracker/var/log/cloudflared.out.log"),
    Path("/Users/ethanjmathew/macro-tracker/var/log/cloudflared.err.log"),
]
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def extract_tunnel_urls() -> list[str]:
    matches: list[str] = []
    for path in LOG_PATHS:
        if path.exists():
            matches.extend(URL_PATTERN.findall(path.read_text()))
    return matches


def latest_tunnel_url() -> str | None:
    matches = extract_tunnel_urls()
    return matches[-1] if matches else None


def main() -> int:
    current_url = latest_tunnel_url()

    if current_url is None:
        print("No tunnel URL found in the log yet.")
        return 1

    print(current_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
