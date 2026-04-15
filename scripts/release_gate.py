"""
Command-line release gate for IRIS.

Usage:
  python scripts/release_gate.py
  python scripts/release_gate.py --api http://127.0.0.1:8124

Exit code:
  0 = production_ready true
  1 = blocked or API unavailable
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="Run IRIS production readiness gate.")
    parser.add_argument("--api", default="http://127.0.0.1:8124", help="IRIS API base URL")
    args = parser.parse_args()

    url = args.api.rstrip("/") + "/production-readiness"
    try:
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"RELEASE GATE: BLOCKED - API unavailable or invalid response: {exc}")
        return 1

    print(f"RELEASE GATE: {payload.get('status', 'unknown').upper()} score={payload.get('score')}")
    print(f"production_ready={payload.get('production_ready')}")

    blockers = payload.get("blockers") or []
    warnings = payload.get("warnings") or []
    if blockers:
        print("\nBlockers:")
        for item in blockers:
            print(f"- {item.get('code')}: {item.get('message')}")
    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"- {item.get('code')}: {item.get('message')}")

    print("\nNext actions:")
    for action in payload.get("next_actions") or []:
        print(f"- {action}")

    return 0 if payload.get("production_ready") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
