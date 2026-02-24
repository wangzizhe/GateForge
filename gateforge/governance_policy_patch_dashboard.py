from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
    lines = [
        "# GateForge Policy Patch Dashboard",
        "",
        f"- bundle_status: `{payload.get('bundle_status')}`",
        f"- latest_apply_status: `{payload.get('latest_apply_status')}`",
        f"- latest_history_status: `{payload.get('latest_history_status')}`",
        f"- rollback_decision: `{payload.get('rollback_decision')}`",
        f"- rollback_recommended: `{payload.get('rollback_recommended')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- pairwise_threshold_enabled_count: `{payload.get('pairwise_threshold_enabled_count')}`",
        f"- latest_pairwise_threshold: `{payload.get('latest_pairwise_threshold')}`",
        f"- pairwise_threshold_enable_rate_delta: `{payload.get('pairwise_threshold_enable_rate_delta')}`",
        "",
        "## Result Flags",
        "",
    ]
    flags = payload.get("result_flags", {})
    if isinstance(flags, dict):
        for key in sorted(flags):
            lines.append(f"- {key}: `{flags[key]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build governance policy patch dashboard summary")
    parser.add_argument("--proposal", required=True, help="Policy patch proposal JSON")
    parser.add_argument("--apply", required=True, help="Policy patch apply summary JSON")
    parser.add_argument("--history", required=True, help="Policy patch history summary JSON")
    parser.add_argument("--trend", required=True, help="Policy patch history trend JSON")
    parser.add_argument("--rollback", required=True, help="Policy patch rollback advisor JSON")
    parser.add_argument("--out", default="artifacts/governance_policy_patch_dashboard/summary.json", help="Summary JSON path")
    parser.add_argument("--report", default=None, help="Summary markdown path")
    args = parser.parse_args()

    proposal = _load_json(args.proposal)
    apply_summary = _load_json(args.apply)
    history = _load_json(args.history)
    trend_payload = _load_json(args.trend)
    rollback = _load_json(args.rollback)
    trend = trend_payload.get("trend", {}) if isinstance(trend_payload.get("trend"), dict) else {}
    rollback_advice = rollback.get("advice", {}) if isinstance(rollback.get("advice"), dict) else {}

    flags = {
        "proposal_present": "PASS" if bool(proposal.get("proposal_id")) else "FAIL",
        "apply_status_present": "PASS" if apply_summary.get("final_status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
        "history_total_records_present": "PASS" if isinstance(history.get("total_records"), int) else "FAIL",
        "trend_delta_present": "PASS" if isinstance(trend.get("delta_total_records"), int) else "FAIL",
        "rollback_decision_present": "PASS"
        if rollback_advice.get("decision") in {"KEEP", "ROLLBACK_RECOMMENDED"}
        else "FAIL",
        "pairwise_threshold_signal_present": "PASS"
        if isinstance(history.get("pairwise_threshold_enabled_count"), int)
        else "FAIL",
    }
    bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bundle_status": bundle_status,
        "proposal_id": proposal.get("proposal_id"),
        "latest_apply_status": apply_summary.get("final_status"),
        "latest_history_status": history.get("latest_status"),
        "rollback_decision": rollback_advice.get("decision"),
        "rollback_recommended": rollback_advice.get("rollback_recommended"),
        "total_records": history.get("total_records"),
        "pairwise_threshold_enabled_count": history.get("pairwise_threshold_enabled_count"),
        "latest_pairwise_threshold": history.get("latest_pairwise_threshold"),
        "fail_rate_delta": trend.get("delta_fail_rate"),
        "reject_rate_delta": trend.get("delta_reject_rate"),
        "pairwise_threshold_enable_rate_delta": trend.get("delta_pairwise_threshold_enable_rate"),
        "paths": {
            "proposal": args.proposal,
            "apply": args.apply,
            "history": args.history,
            "trend": args.trend,
            "rollback": args.rollback,
        },
        "result_flags": flags,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report or _default_md_path(args.out), payload)
    print(json.dumps({"bundle_status": bundle_status, "proposal_id": payload.get("proposal_id")}))
    if bundle_status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
