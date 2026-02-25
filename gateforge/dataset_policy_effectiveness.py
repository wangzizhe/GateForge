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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    delta = payload.get("delta", {}) if isinstance(payload.get("delta"), dict) else {}
    lines = [
        "# GateForge Dataset Policy Effectiveness",
        "",
        f"- decision: `{payload.get('decision')}`",
        f"- before_path: `{payload.get('before_path')}`",
        f"- after_path: `{payload.get('after_path')}`",
        f"- delta_deduplicated_cases: `{delta.get('deduplicated_cases')}`",
        f"- delta_failure_case_rate: `{delta.get('failure_case_rate')}`",
        f"- delta_freeze_pass_rate: `{delta.get('freeze_pass_rate')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate dataset policy effectiveness from before/after history summaries")
    parser.add_argument("--before", required=True, help="Dataset history summary before policy change")
    parser.add_argument("--after", required=True, help="Dataset history summary after policy change")
    parser.add_argument("--out", default="artifacts/dataset_policy/effectiveness.json", help="Output JSON path")
    parser.add_argument("--report-out", default=None, help="Output markdown path")
    parser.add_argument("--min-dedup-improvement", type=int, default=2, help="Expected minimum dedup increase")
    parser.add_argument(
        "--min-failure-rate-improvement",
        type=float,
        default=0.05,
        help="Expected minimum failure-case-rate increase",
    )
    args = parser.parse_args()

    before = _load_json(args.before)
    after = _load_json(args.after)

    delta_dedup = _to_int(after.get("latest_deduplicated_cases")) - _to_int(before.get("latest_deduplicated_cases"))
    delta_failure = round(
        _to_float(after.get("latest_failure_case_rate")) - _to_float(before.get("latest_failure_case_rate")),
        4,
    )
    delta_freeze = round(
        _to_float(after.get("freeze_pass_rate")) - _to_float(before.get("freeze_pass_rate")),
        4,
    )

    reasons: list[str] = []
    if delta_dedup < int(args.min_dedup_improvement):
        reasons.append("deduplicated_case_growth_below_target")
    if delta_failure < float(args.min_failure_rate_improvement):
        reasons.append("failure_case_rate_growth_below_target")
    if delta_freeze < 0:
        reasons.append("freeze_pass_rate_regressed")

    if not reasons:
        decision = "KEEP"
    elif "freeze_pass_rate_regressed" in reasons:
        decision = "ROLLBACK_REVIEW"
    else:
        decision = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "before_path": args.before,
        "after_path": args.after,
        "decision": decision,
        "delta": {
            "deduplicated_cases": delta_dedup,
            "failure_case_rate": delta_failure,
            "freeze_pass_rate": delta_freeze,
        },
        "reasons": reasons,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"decision": decision, "reasons": reasons}))
    if decision == "ROLLBACK_REVIEW":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

