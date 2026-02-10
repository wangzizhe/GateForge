from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .regression import compare_evidence, load_json, write_json, write_markdown


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline and candidate evidence")
    parser.add_argument("--baseline", required=True, help="Path to baseline evidence.json")
    parser.add_argument("--candidate", required=True, help="Path to candidate evidence.json")
    parser.add_argument(
        "--runtime-threshold",
        type=float,
        default=0.2,
        help="Allowed runtime regression ratio (0.2 = +20%%)",
    )
    parser.add_argument(
        "--out",
        default="artifacts/regression.json",
        help="Where to write regression decision JSON",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict comparability checks (schema_version/backend)",
    )
    parser.add_argument(
        "--strict-model-script",
        action="store_true",
        help="When strict mode is enabled, also require model_script to match",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Where to write regression markdown report",
    )
    args = parser.parse_args()

    baseline = load_json(args.baseline)
    candidate = load_json(args.candidate)
    result = compare_evidence(
        baseline=baseline,
        candidate=candidate,
        runtime_regression_threshold=args.runtime_threshold,
        strict=args.strict,
        strict_model_script=args.strict_model_script,
    )

    write_json(args.out, result)
    write_markdown(args.report or _default_md_path(args.out), result)
    print(json.dumps({"decision": result["decision"], "reasons": result["reasons"]}))

    if result["decision"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
