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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    delta = payload.get("delta", {}) if isinstance(payload.get("delta"), dict) else {}
    lines = [
        "# GateForge Dataset Promotion Effectiveness",
        "",
        f"- decision: `{payload.get('decision')}`",
        f"- before_path: `{payload.get('before_path')}`",
        f"- after_path: `{payload.get('after_path')}`",
        f"- delta_pass_rate: `{delta.get('pass_rate')}`",
        f"- delta_needs_review_rate: `{delta.get('needs_review_rate')}`",
        f"- delta_fail_rate: `{delta.get('fail_rate')}`",
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
    parser = argparse.ArgumentParser(description="Evaluate dataset promotion effectiveness from before/after apply-history summaries")
    parser.add_argument("--before", required=True, help="dataset promotion apply history summary before change")
    parser.add_argument("--after", required=True, help="dataset promotion apply history summary after change")
    parser.add_argument("--out", default="artifacts/dataset_promotion/effectiveness.json", help="Output JSON path")
    parser.add_argument("--report-out", default=None, help="Output markdown path")
    parser.add_argument("--max-fail-rate-increase", type=float, default=0.1)
    parser.add_argument("--max-needs-review-rate-increase", type=float, default=0.15)
    parser.add_argument("--max-pass-rate-drop", type=float, default=0.2)
    args = parser.parse_args()

    before = _load_json(args.before)
    after = _load_json(args.after)

    d_pass = round(_to_float(after.get("pass_rate")) - _to_float(before.get("pass_rate")), 4)
    d_review = round(_to_float(after.get("needs_review_rate")) - _to_float(before.get("needs_review_rate")), 4)
    d_fail = round(_to_float(after.get("fail_rate")) - _to_float(before.get("fail_rate")), 4)

    reasons: list[str] = []
    if d_fail > float(args.max_fail_rate_increase):
        reasons.append("promotion_apply_fail_rate_increase_too_high")
    if d_review > float(args.max_needs_review_rate_increase):
        reasons.append("promotion_apply_needs_review_rate_increase_too_high")
    if d_pass < -float(args.max_pass_rate_drop):
        reasons.append("promotion_apply_pass_rate_drop_too_high")

    if not reasons:
        decision = "KEEP"
    elif "promotion_apply_fail_rate_increase_too_high" in reasons:
        decision = "ROLLBACK_REVIEW"
    else:
        decision = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "before_path": args.before,
        "after_path": args.after,
        "decision": decision,
        "delta": {
            "pass_rate": d_pass,
            "needs_review_rate": d_review,
            "fail_rate": d_fail,
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
