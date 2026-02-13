from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .planner_output import validate_planner_output


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate GateForge planner output JSON")
    parser.add_argument("--in", dest="in_path", required=True, help="Planner output JSON path")
    parser.add_argument("--strict-top-level", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    try:
        validate_planner_output(payload, strict_top_level=args.strict_top_level)
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}))
        raise SystemExit(1) from exc
    print(json.dumps({"status": "PASS", "path": args.in_path}))


if __name__ == "__main__":
    main()
