from __future__ import annotations

import argparse
import json

from .core import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GateForge minimal smoke pipeline")
    parser.add_argument(
        "--backend",
        default="mock",
        choices=["mock", "openmodelica"],
        help="Execution backend for smoke run",
    )
    parser.add_argument(
        "--out",
        default="artifacts/evidence.json",
        help="Where to write evidence JSON",
    )
    args = parser.parse_args()

    evidence = run_pipeline(backend=args.backend, out_path=args.out)
    print(json.dumps({"gate": evidence["gate"], "status": evidence["status"]}))


if __name__ == "__main__":
    main()

