from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_post_restore_promotion_summary_v0_3_5 import (
    build_post_restore_promotion_summary,
)


SCHEMA_VERSION = "agent_modelica_v0_3_5_dev_priorities"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_5_dev_priorities"


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


def build_v0_3_5_dev_priorities(
    *,
    lane_summary_path: str,
    run_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    out_root = Path(out_dir)
    lane = _load_json(lane_summary_path)
    promotion = build_post_restore_promotion_summary(
        lane_summary_path=str(lane_summary_path),
        run_summary_path=str(run_summary_path),
        out_dir=str(out_root / "post_restore_promotion"),
    )
    observed = promotion.get("observed_metrics") if isinstance(promotion.get("observed_metrics"), dict) else {}
    lane_status = str(lane.get("lane_status") or observed.get("lane_status") or "")
    promoted_primary = bool((promotion.get("decision") or {}).get("promote"))

    next_actions: list[str] = []
    if promoted_primary:
        next_actions.append(
            "Treat `simulate_error_parameter_recovery_sweep` as the primary v0.3.5 repair lever for post-restore residual conflicts."
        )
    next_actions.append(
        "Expand the post-restore harder lane toward cases where a single numeric sweep is insufficient and branch selection or replan becomes necessary."
    )
    next_actions.append(
        "Extend the failure-classifier layer with post-restore buckets: residual semantic conflict, verifier reject after restore, wrong-branch follow-up, and stalled search after progress."
    )
    next_actions.append(
        "Keep Claude/Codex comparative work in maintenance-only mode until the v0.3.5 harder lane is richer than the current 10-case freeze-ready set."
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if promoted_primary and lane_status == "FREEZE_READY" else "PARTIAL",
        "primary_repair_lever": {
            "lever": "simulate_error_parameter_recovery_sweep" if promoted_primary else "",
            "promotion_reason": (
                "post_restore_promotion_ready"
                if promoted_primary
                else "needs_more_post_restore_validation"
            ),
        },
        "best_harder_lane": {
            "family_id": "post_restore_residual_conflict",
            "status": lane_status,
            "freeze_ready_count": int(lane.get("admitted_count") or 0),
        },
        "evidence_backed_repair_lever": {
            "lever": "simulate_error_parameter_recovery_sweep" if promoted_primary else "",
            "source": "post_restore_promotion_summary",
            "metrics": observed,
        },
        "roadmap_continuity": {
            "from_v0_3_4": "multi_round_deterministic_repair_validation",
            "to_v0_3_5": "post_restore_residual_conflict",
            "comparative_completion_target": "v0.3.6_or_later",
        },
        "next_actions": next_actions,
    }
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# Agent Modelica v0.3.5 Dev Priorities",
        "",
        f"- status: `{payload.get('status')}`",
        f"- primary_repair_lever: `{(payload.get('primary_repair_lever') or {}).get('lever')}`",
        f"- best_harder_lane: `{(payload.get('best_harder_lane') or {}).get('family_id')}`",
        "",
        "## Next Actions",
        "",
    ]
    for idx, item in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{idx}. {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an actionable v0.3.5 development-priorities summary.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--run-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_5_dev_priorities(
        lane_summary_path=str(args.lane_summary),
        run_summary_path=str(args.run_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "primary_repair_lever": (payload.get("primary_repair_lever") or {}).get("lever")}))


if __name__ == "__main__":
    main()
