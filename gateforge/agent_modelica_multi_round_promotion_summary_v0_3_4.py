from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_multi_round_repair_audit_v0_3_4 import build_multi_round_repair_audit


SCHEMA_VERSION = "agent_modelica_multi_round_promotion_summary_v0_3_4"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_multi_round_promotion_summary_v0_3_4"
PROMOTION_MIN_RESCUES = 2


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_multi_round_promotion_summary(*, validation_input_path: str, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    out_root = Path(out_dir)
    audit = build_multi_round_repair_audit(
        input_path=str(validation_input_path),
        out_dir=str(out_root / "repair_audit"),
    )
    metrics = audit.get("metrics") if isinstance(audit.get("metrics"), dict) else {}
    rescue_count = int(metrics.get("deterministic_multi_round_rescue_count") or 0)
    applicable_count = int(metrics.get("applicable_multi_round_rows") or 0)
    promotion_ready = rescue_count >= PROMOTION_MIN_RESCUES
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PROMOTION_READY" if promotion_ready else "NEEDS_MORE_VALIDATION",
        "validation_input_path": str(Path(validation_input_path).resolve()),
        "promotion_target": "multi_round_deterministic_repair_validation",
        "promotion_threshold": {
            "minimum_rescues": PROMOTION_MIN_RESCUES,
        },
        "observed_metrics": {
            "applicable_multi_round_rows": applicable_count,
            "deterministic_multi_round_rescue_count": rescue_count,
            "deterministic_multi_round_rescue_rate_pct": float(metrics.get("deterministic_multi_round_rescue_rate_pct") or 0.0),
        },
        "decision": {
            "promote": promotion_ready,
            "reason": (
                f"validated deterministic rescues reached {rescue_count} >= {PROMOTION_MIN_RESCUES}"
                if promotion_ready
                else f"validated deterministic rescues stayed below threshold: {rescue_count} < {PROMOTION_MIN_RESCUES}"
            ),
        },
        "next_actions": (
            [
                "Promote multi-round deterministic repair validation to the primary v0.3.4 repair lever.",
                "Expand validation to additional hard_multiround_simulate_failure freeze-ready members.",
                "Keep repair_rule_ordering as a secondary lever for unresolved planner-sensitive failures.",
            ]
            if promotion_ready
            else [
                "Collect more multi-round live validation before changing the primary v0.3.4 repair lever.",
            ]
        ),
    }
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    observed = payload.get("observed_metrics") if isinstance(payload.get("observed_metrics"), dict) else {}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    lines = [
        "# Multi-Round Promotion Summary v0.3.4",
        "",
        f"- status: `{payload.get('status')}`",
        f"- promotion_target: `{payload.get('promotion_target')}`",
        f"- applicable_multi_round_rows: `{observed.get('applicable_multi_round_rows')}`",
        f"- deterministic_multi_round_rescue_count: `{observed.get('deterministic_multi_round_rescue_count')}`",
        f"- deterministic_multi_round_rescue_rate_pct: `{observed.get('deterministic_multi_round_rescue_rate_pct')}`",
        f"- promote: `{decision.get('promote')}`",
        f"- reason: `{decision.get('reason')}`",
        "",
        "## Next Actions",
        "",
    ]
    for idx, action in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{idx}. {action}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize whether multi-round deterministic repair should be promoted in v0.3.4.")
    parser.add_argument("--validation-input", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_multi_round_promotion_summary(
        validation_input_path=str(args.validation_input),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "promote": (payload.get("decision") or {}).get("promote")}))


if __name__ == "__main__":
    main()
