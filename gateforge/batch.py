from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .core import run_pipeline
from .proposal import execution_target_from_proposal, load_proposal


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", s)


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Batch Report",
        "",
        f"- backend: `{summary['backend']}`",
        f"- total_runs: `{summary['total_runs']}`",
        f"- pass_count: `{summary['pass_count']}`",
        f"- fail_count: `{summary['fail_count']}`",
        "",
        "## Runs",
        "",
    ]
    for item in summary["runs"]:
        lines.append(
            f"- `{item['name']}`: gate=`{item['gate']}` status=`{item['status']}` "
            f"failure_type=`{item['failure_type']}` json=`{item['json_path']}`"
        )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _load_pack(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Pack file must be a JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GateForge pipeline in batch mode")
    parser.add_argument(
        "--backend",
        default="mock",
        choices=["mock", "openmodelica", "openmodelica_docker"],
        help="Execution backend",
    )
    parser.add_argument(
        "--script",
        action="append",
        default=[],
        help="Script path(s) for openmodelica_docker backend; can be repeated",
    )
    parser.add_argument(
        "--pack",
        default=None,
        help="Path to a batch pack JSON (e.g., benchmarks/pack_v0.json)",
    )
    parser.add_argument(
        "--proposal",
        default=None,
        help="Optional proposal JSON path; uses proposal backend/model_script for single-run batch",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/batch",
        help="Output directory for per-run evidence files",
    )
    parser.add_argument(
        "--summary-out",
        default="artifacts/batch/summary.json",
        help="Where to write summary JSON",
    )
    parser.add_argument(
        "--report-out",
        default="artifacts/batch/summary.md",
        help="Where to write summary markdown",
    )
    parser.add_argument(
        "--continue-on-fail",
        action="store_true",
        help="Continue remaining runs after a failed run (default: stop on first failure)",
    )
    args = parser.parse_args()

    if args.proposal and (args.pack or args.script):
        parser.error("--proposal cannot be combined with --pack or --script")

    pack: dict = _load_pack(args.pack) if args.pack else {}
    backend = args.backend
    proposal_script = None
    if args.proposal:
        proposal = load_proposal(args.proposal)
        backend, proposal_script = execution_target_from_proposal(proposal)
    if args.pack and "backend" in pack and args.backend == parser.get_default("backend"):
        backend = pack["backend"]

    scripts = args.script or pack.get("scripts", [])
    if proposal_script is not None:
        scripts = [proposal_script]
    continue_on_fail = args.continue_on_fail or bool(pack.get("continue_on_fail", False))

    if backend == "openmodelica_docker" and not scripts:
        scripts = [None]
    if backend != "openmodelica_docker":
        scripts = [None]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict] = []

    for i, script in enumerate(scripts):
        name = _slug(script or f"{backend}_{i}")
        json_path = out_dir / f"{name}.json"
        md_path = out_dir / f"{name}.md"
        evidence = run_pipeline(
            backend=backend,
            out_path=str(json_path),
            report_path=str(md_path),
            script_path=script,
        )
        runs.append(
            {
                "name": name,
                "script": script,
                "status": evidence["status"],
                "gate": evidence["gate"],
                "failure_type": evidence["failure_type"],
                "runtime_seconds": evidence["metrics"]["runtime_seconds"],
                "json_path": str(json_path),
                "report_path": str(md_path),
            }
        )
        if evidence["gate"] != "PASS" and not continue_on_fail:
            break

    fail_count = sum(1 for r in runs if r["gate"] != "PASS")
    summary = {
        "backend": backend,
        "total_runs": len(runs),
        "pass_count": len(runs) - fail_count,
        "fail_count": fail_count,
        "runs": runs,
    }
    _write_json(args.summary_out, summary)
    _write_markdown(args.report_out, summary)
    print(json.dumps({"total_runs": summary["total_runs"], "fail_count": fail_count}))
    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
