from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    steps = payload.get("steps", [])
    lines = [
        "# GateForge MVP Freeze Summary",
        "",
        f"- verdict: `{payload.get('verdict')}`",
        f"- blocking_step: `{payload.get('blocking_step')}`",
        f"- total_steps: `{len(steps)}`",
        "",
        "## Steps",
        "",
    ]
    for row in steps:
        lines.append(f"- `{row.get('name')}`: rc=`{row.get('exit_code')}` status=`{row.get('status')}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _step_status(exit_code: int, evidence_ok: bool) -> str:
    if exit_code == 0 and evidence_ok:
        return "PASS"
    return "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize MVP freeze run results into one verdict")
    parser.add_argument("--tests-rc", type=int, required=True)
    parser.add_argument("--medium-dashboard-rc", type=int, required=True)
    parser.add_argument("--mutation-dashboard-rc", type=int, required=True)
    parser.add_argument("--policy-dashboard-rc", type=int, required=True)
    parser.add_argument("--ci-matrix-rc", type=int, required=True)
    parser.add_argument(
        "--medium-dashboard-json",
        default="artifacts/benchmark_medium_v1/dashboard.json",
        help="Medium dashboard artifact path",
    )
    parser.add_argument(
        "--mutation-dashboard-json",
        default="artifacts/mutation_dashboard_demo/summary.json",
        help="Mutation dashboard artifact path",
    )
    parser.add_argument(
        "--policy-dashboard-json",
        default="artifacts/governance_policy_patch_dashboard_demo/demo_summary.json",
        help="Policy dashboard artifact path",
    )
    parser.add_argument(
        "--ci-matrix-json",
        default="artifacts/ci_matrix_summary.json",
        help="CI matrix summary path",
    )
    parser.add_argument(
        "--out",
        default="artifacts/mvp_freeze/summary.json",
        help="MVP freeze summary JSON path",
    )
    parser.add_argument("--report-out", default=None, help="MVP freeze summary markdown path")
    args = parser.parse_args()

    medium = _load_json(args.medium_dashboard_json)
    mutation = _load_json(args.mutation_dashboard_json)
    policy = _load_json(args.policy_dashboard_json)
    matrix = _load_json(args.ci_matrix_json)

    steps = [
        {
            "name": "tests",
            "exit_code": int(args.tests_rc),
            "status": _step_status(int(args.tests_rc), True),
        },
        {
            "name": "medium_dashboard",
            "exit_code": int(args.medium_dashboard_rc),
            "status": _step_status(
                int(args.medium_dashboard_rc),
                Path(args.medium_dashboard_json).exists()
                and str(medium.get("bundle_status")) == "PASS",
            ),
        },
        {
            "name": "mutation_dashboard",
            "exit_code": int(args.mutation_dashboard_rc),
            "status": _step_status(
                int(args.mutation_dashboard_rc),
                Path(args.mutation_dashboard_json).exists()
                and str(mutation.get("bundle_status")) == "PASS",
            ),
        },
        {
            "name": "policy_dashboard",
            "exit_code": int(args.policy_dashboard_rc),
            "status": _step_status(
                int(args.policy_dashboard_rc),
                Path(args.policy_dashboard_json).exists()
                and str(policy.get("bundle_status")) == "PASS",
            ),
        },
        {
            "name": "ci_matrix_targeted",
            "exit_code": int(args.ci_matrix_rc),
            "status": _step_status(
                int(args.ci_matrix_rc),
                Path(args.ci_matrix_json).exists()
                and str(matrix.get("matrix_status")) == "PASS",
            ),
        },
    ]
    blocking = next((s["name"] for s in steps if s["status"] != "PASS"), None)
    verdict = "MVP_FREEZE_PASS" if blocking is None else "MVP_FREEZE_FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "blocking_step": blocking,
        "steps": steps,
        "artifact_paths": {
            "medium_dashboard_json": args.medium_dashboard_json,
            "mutation_dashboard_json": args.mutation_dashboard_json,
            "policy_dashboard_json": args.policy_dashboard_json,
            "ci_matrix_json": args.ci_matrix_json,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"verdict": verdict, "blocking_step": blocking}))
    if verdict != "MVP_FREEZE_PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
