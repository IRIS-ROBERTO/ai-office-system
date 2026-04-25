"""
Backfill and sanitize delivery runtime artifacts.

Repairs malformed historical manifest evidence and generates deterministic
retrospectives for every manifest already persisted in .runtime.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.delivery_retrospective import backfill_retrospectives_from_manifests


def main() -> int:
    result = backfill_retrospectives_from_manifests(write_manifest_repairs=True)
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
