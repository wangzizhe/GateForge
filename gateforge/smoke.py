from __future__ import annotations

import argparse
import json

from .core import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GateForge minimal smoke pipeline")
    parser.add_argument(
        "--backend",
        default="mock",
        choices=["mock", "openmodelica", "openmodelica_docker"],
        help="Execution backend for smoke run",
    )
    parser.add_argument(
        "--out",
        default="artifacts/evidence.json",
        help="Where to write evidence JSON",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Where to write markdown report (default: same path as --out with .md)",
    )
    args = parser.parse_args()

    evidence = run_pipeline(backend=args.backend, out_path=args.out, report_path=args.report)
    print(json.dumps({"gate": evidence["gate"], "status": evidence["status"]}))


if __name__ == "__main__":
    main()
