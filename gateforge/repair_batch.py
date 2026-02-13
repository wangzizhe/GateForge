from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# GateForge Repair Batch Summary",
        "",
        f"- pack_id: `{summary.get('pack_id')}`",
        f"- planner_backend_default: `{summary.get('planner_backend_default')}`",
        f"- total_cases: `{summary.get('total_cases')}`",
        f"- pass_count: `{summary.get('pass_count')}`",
        f"- fail_count: `{summary.get('fail_count')}`",
        f"- needs_review_count: `{summary.get('needs_review_count')}`",
        f"- unknown_count: `{summary.get('unknown_count')}`",
        "",
        "## Cases",
        "",
    ]

    cases = summary.get("cases", [])
    if not cases:
        lines.append("- `none`")
    else:
        for case in cases:
            lines.append(
                f"- `{case.get('name')}`: status=`{case.get('status')}` delta=`{case.get('delta')}` "
                f"retry_used=`{case.get('retry_used')}` exit_code=`{case.get('exit_code')}`"
            )

    lines.extend(["", "## Failed Cases", ""])
    failed = [c for c in cases if c.get("status") in {"FAIL", "UNKNOWN"}]
    if failed:
        for case in failed:
            lines.append(f"- `{case.get('name')}` reasons=`{','.join(case.get('reasons', [])) or 'none'}`")
    else:
        lines.append("- `none`")

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _safe_case_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
    cleaned = cleaned.strip("_")
    return cleaned or "case"


def _load_pack(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("pack must be a JSON object")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("pack must contain non-empty 'cases' list")
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{i}] must be an object")
        if not isinstance(case.get("source"), str) or not case.get("source"):
            raise ValueError(f"cases[{i}].source is required")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run repair_loop over a batch pack")
    parser.add_argument("--pack", required=True, help="Path to repair batch pack JSON")
    parser.add_argument("--out-dir", default="artifacts/repair_batch", help="Where to write per-case outputs")
    parser.add_argument("--summary-out", default="artifacts/repair_batch/summary.json", help="Summary JSON path")
    parser.add_argument("--report-out", default=None, help="Summary markdown path")
    parser.add_argument("--planner-backend", default="rule", choices=["rule", "gemini", "openai"])
    parser.add_argument("--baseline", default="auto")
    parser.add_argument("--baseline-index", default="baselines/index.json")
    parser.add_argument("--runtime-threshold", type=float, default=0.2)
    parser.add_argument("--policy", default=None)
    parser.add_argument("--policy-profile", default=None)
    parser.add_argument("--save-run-under", default="autopilot", choices=["autopilot", "agent"])
    parser.add_argument("--retry-on-failed-attempt", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--retry-fallback-planner-backend", default="rule", choices=["rule", "gemini", "openai"])
    parser.add_argument("--retry-confidence-min", type=float, default=0.8)
    parser.add_argument("--continue-on-fail", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    pack = _load_pack(args.pack)
    pack_id = pack.get("pack_id", "repair_pack")
    cases = pack["cases"]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    fail_count = 0
    needs_review_count = 0
    unknown_count = 0

    for idx, case in enumerate(cases):
        source = str(case["source"])
        name = str(case.get("name") or f"case_{idx+1}")
        safe_name = _safe_case_name(name)

        case_out_json = str(out_dir / f"{safe_name}.json")
        case_out_md = str(out_dir / f"{safe_name}.md")

        cmd = [
            sys.executable,
            "-m",
            "gateforge.repair_loop",
            "--source",
            source,
            "--planner-backend",
            str(case.get("planner_backend") or args.planner_backend),
            "--baseline",
            str(case.get("baseline") or args.baseline),
            "--baseline-index",
            str(case.get("baseline_index") or args.baseline_index),
            "--runtime-threshold",
            str(case.get("runtime_threshold") if case.get("runtime_threshold") is not None else args.runtime_threshold),
            "--save-run-under",
            str(case.get("save_run_under") or args.save_run_under),
            "--max-retries",
            str(case.get("max_retries") if case.get("max_retries") is not None else args.max_retries),
            "--retry-fallback-planner-backend",
            str(case.get("retry_fallback_planner_backend") or args.retry_fallback_planner_backend),
            "--retry-confidence-min",
            str(case.get("retry_confidence_min") if case.get("retry_confidence_min") is not None else args.retry_confidence_min),
            "--out",
            case_out_json,
            "--report",
            case_out_md,
        ]

        if case.get("proposal_id"):
            cmd.extend(["--proposal-id", str(case["proposal_id"])])

        policy_value = case.get("policy") if case.get("policy") is not None else args.policy
        if policy_value:
            cmd.extend(["--policy", str(policy_value)])

        profile_value = case.get("policy_profile") if case.get("policy_profile") is not None else args.policy_profile
        if profile_value:
            cmd.extend(["--policy-profile", str(profile_value)])

        retry_enabled = case.get("retry_on_failed_attempt")
        if retry_enabled is None:
            retry_enabled = args.retry_on_failed_attempt
        cmd.append("--retry-on-failed-attempt" if retry_enabled else "--no-retry-on-failed-attempt")

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

        payload = {}
        if Path(case_out_json).exists():
            payload = json.loads(Path(case_out_json).read_text(encoding="utf-8"))

        status = str(payload.get("status") or "UNKNOWN").upper()
        reasons = payload.get("after", {}).get("reasons")
        if not isinstance(reasons, list):
            reasons = []

        row = {
            "name": name,
            "source": source,
            "status": status,
            "delta": payload.get("comparison", {}).get("delta"),
            "retry_used": bool(payload.get("retry_used")),
            "selected_attempt": payload.get("selected_attempt"),
            "planner_backend": payload.get("planner_backend"),
            "exit_code": int(proc.returncode),
            "reasons": [str(r) for r in reasons if isinstance(r, str)],
            "json_path": case_out_json,
            "report_path": case_out_md,
        }
        results.append(row)

        if status == "FAIL":
            fail_count += 1
        elif status == "NEEDS_REVIEW":
            needs_review_count += 1
        elif status not in {"PASS"}:
            unknown_count += 1

        if proc.returncode != 0 and not args.continue_on_fail:
            break

    pass_count = sum(1 for r in results if r["status"] == "PASS")
    summary = {
        "pack_id": str(pack_id),
        "planner_backend_default": args.planner_backend,
        "total_cases": len(results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "needs_review_count": needs_review_count,
        "unknown_count": unknown_count,
        "cases": results,
    }

    _write_json(args.summary_out, summary)
    _write_markdown(args.report_out or _default_md_path(args.summary_out), summary)

    print(json.dumps({"pack_id": summary["pack_id"], "total_cases": summary["total_cases"], "fail_count": fail_count}))
    if fail_count > 0 or unknown_count > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
