from __future__ import annotations

import argparse
import json

from .core import run_pipeline
from .proposal import execution_target_from_proposal, load_proposal


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
    parser.add_argument(
        "--proposal",
        default=None,
        help="Optional proposal JSON path. If set, backend/script are taken from proposal.",
    )
    args = parser.parse_args()

    backend = args.backend
    script_path = None
    proposal_id = None
    if args.proposal:
        proposal = load_proposal(args.proposal)
        proposal_id = proposal.get("proposal_id")
        backend, script_path = execution_target_from_proposal(proposal)

    evidence = run_pipeline(
        backend=backend,
        out_path=args.out,
        report_path=args.report,
        script_path=script_path,
        proposal_id=proposal_id,
    )
    print(json.dumps({"gate": evidence["gate"], "status": evidence["status"]}))


if __name__ == "__main__":
    main()
