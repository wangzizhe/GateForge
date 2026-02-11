from __future__ import annotations

import argparse
import json
import sys

from .proposal import load_proposal, validate_proposal


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate GateForge proposal JSON")
    parser.add_argument("--in", dest="input_path", required=True, help="Path to proposal JSON")
    parser.add_argument("--out", default=None, help="Optional path to write validation result JSON")
    args = parser.parse_args()

    try:
        proposal = load_proposal(args.input_path)
        validate_proposal(proposal)
        result = {"valid": True, "proposal_id": proposal["proposal_id"]}
        exit_code = 0
    except Exception as exc:  # noqa: BLE001
        result = {"valid": False, "error": str(exc)}
        exit_code = 1

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(json.dumps(result, indent=2))
    print(json.dumps(result))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
