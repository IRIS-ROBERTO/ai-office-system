"""
Premium local quality gate for IRIS.

Runs deterministic checks that catch the highest-risk local regressions:
Python syntax/import readiness, frontend production build, and optional live
API readiness against the running backend.
"""
from __future__ import annotations

import argparse
import json
import py_compile
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run IRIS premium local quality gate.")
    parser.add_argument("--api", default="http://127.0.0.1:8124", help="Running IRIS API base URL")
    parser.add_argument("--skip-api", action="store_true", help="Skip live API checks")
    args = parser.parse_args()

    checks = [
        ("python_compile", compile_python),
        ("frontend_build", build_frontend),
    ]
    if not args.skip_api:
        checks.append(("live_api", lambda: validate_live_api(args.api)))

    failures: list[str] = []
    print("IRIS PREMIUM QUALITY GATE")
    for name, check in checks:
        try:
            check()
            print(f"[OK] {name}")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"[FAIL] {name}: {exc}")

    if failures:
        print("\nGate blocked:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nGate passed.")
    return 0


def compile_python() -> None:
    files = sorted((ROOT / "backend").rglob("*.py")) + sorted((ROOT / "scripts").rglob("*.py"))
    if not files:
        raise RuntimeError("no Python files found")
    for path in files:
        py_compile.compile(str(path), doraise=True)


def build_frontend() -> None:
    npm = "npm.cmd" if sys.platform.startswith("win") else "npm"
    result = subprocess.run(
        [npm, "--prefix", "frontend", "run", "build"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError("frontend build failed")


def validate_live_api(api_base: str) -> None:
    api = api_base.rstrip("/")
    health = _get_json(f"{api}/health", timeout=20)
    readiness = _get_json(f"{api}/production-readiness", timeout=30)
    memory = _get_json(f"{api}/integrations/memory-gateway", timeout=10)

    if health.get("api") != "online":
        raise RuntimeError("API health is not online")
    if health.get("redis") != "online":
        raise RuntimeError("Redis is not online")
    if not readiness.get("production_ready"):
        raise RuntimeError(f"production readiness blocked: {readiness.get('status')}")
    if memory.get("governance", {}).get("secret_screening") is not True:
        raise RuntimeError("memory gateway secret screening is not enabled")


def _get_json(url: str, *, timeout: int) -> dict:
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"request failed for {url}: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
