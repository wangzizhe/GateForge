from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_10_dev_priorities"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_10_dev_priorities"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_v0_3_10_dev_priorities(
    *,
    lane_summary_path: str,
    block_b_decision_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    lane = _load_json(lane_summary_path)
    decision = _load_json(block_b_decision_summary_path)
    block_b = str(decision.get("decision") or "")
    hypothesis = str(decision.get("replacement_hypothesis") or "")

    if block_b == "continuity_promotion_supported":
        status = "PASS"
        next_hypothesis = "same_branch_continuity_after_partial_progress"
        reason = "continuity_promotion_supported"
    elif block_b == "narrower_replacement_hypothesis_supported" and hypothesis:
        status = "PASS"
        next_hypothesis = hypothesis
        reason = "narrower_replacement_hypothesis_supported"
    else:
        status = "PARTIAL"
        next_hypothesis = ""
        reason = str(decision.get("reason") or "")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "primary_direction": {
            "family_id": "same_branch_continuity_after_partial_progress",
            "lane_status": str(lane.get("lane_status") or ""),
            "admitted_count": int(lane.get("admitted_count") or 0),
        },
        "next_hypothesis": {
            "lever": next_hypothesis,
            "reason": reason,
            "identified": bool(next_hypothesis),
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.10 Dev Priorities",
                "",
                f"- status: `{status}`",
                f"- next_hypothesis: `{next_hypothesis}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.10 development-priority summary.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--block-b-decision-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_10_dev_priorities(
        lane_summary_path=str(args.lane_summary),
        block_b_decision_summary_path=str(args.block_b_decision_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_hypothesis": (payload.get("next_hypothesis") or {}).get("lever")}))


if __name__ == "__main__":
    main()
