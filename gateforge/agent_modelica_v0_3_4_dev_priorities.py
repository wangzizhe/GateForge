from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_failure_classifier_v0_3_4 import build_failure_classifier
from .agent_modelica_harder_lane_gate_v0_3_4 import build_harder_lane_gate
from .agent_modelica_multi_round_repair_audit_v0_3_4 import build_multi_round_repair_audit
from .agent_modelica_planner_bottleneck_analysis_v0_3_4 import build_planner_bottleneck_analysis


SCHEMA_VERSION = "agent_modelica_v0_3_4_dev_priorities"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_4_dev_priorities"
PROMOTE_MULTI_ROUND_REPAIR_MIN_RESCUES = 2


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


def build_v0_3_4_dev_priorities(
    *,
    failure_input_path: str,
    refreshed_candidate_taskset_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
    min_freeze_ready_cases: int = 5,
    multi_round_audit_input_path: str = "",
) -> dict:
    out_root = Path(out_dir)
    classifier = build_failure_classifier(
        input_path=str(failure_input_path),
        out_dir=str(out_root / "failure_classifier"),
    )
    bottlenecks = build_planner_bottleneck_analysis(
        failure_classifier_summary_path=str(out_root / "failure_classifier" / "summary.json"),
        out_dir=str(out_root / "planner_bottlenecks"),
    )
    lane_gate = build_harder_lane_gate(
        refreshed_candidate_taskset_path=str(refreshed_candidate_taskset_path),
        out_dir=str(out_root / "harder_lane_gate"),
        min_freeze_ready_cases=int(min_freeze_ready_cases),
    )
    multi_round_audit: dict = {}
    if str(multi_round_audit_input_path or "").strip():
        multi_round_audit = build_multi_round_repair_audit(
            input_path=str(multi_round_audit_input_path),
            out_dir=str(out_root / "multi_round_repair_audit"),
        )

    ranked_levers = bottlenecks.get("ranked_levers") if isinstance(bottlenecks.get("ranked_levers"), list) else []
    lane_rows = lane_gate.get("lane_rows") if isinstance(lane_gate.get("lane_rows"), list) else []
    top_lever = ranked_levers[0] if ranked_levers else {}
    best_lane = max(
        [row for row in lane_rows if isinstance(row, dict)],
        key=lambda row: int(row.get("freeze_ready_count") or 0),
        default={},
    )

    next_actions: list[str] = []
    multi_round_action = str(multi_round_audit.get("recommended_action") or "").strip()
    multi_round_metrics = multi_round_audit.get("metrics") if isinstance(multi_round_audit.get("metrics"), dict) else {}
    multi_round_rescues = int(multi_round_metrics.get("deterministic_multi_round_rescue_count") or 0)
    promoted_primary_lever = ""
    if multi_round_action == "promote_multi_round_deterministic_repair_validation" and multi_round_rescues >= PROMOTE_MULTI_ROUND_REPAIR_MIN_RESCUES:
        promoted_primary_lever = "multi_round_deterministic_repair_validation"
    if multi_round_action == "promote_multi_round_deterministic_repair_validation":
        next_actions.append(
            "Promote multi-round deterministic repair validation; live evidence shows at least one multi-round family case is rescued without planner or replay."
        )
    if promoted_primary_lever:
        next_actions.append(
            f"Treat `{promoted_primary_lever}` as the primary v0.3.4 repair lever; deterministic rescues reached `{multi_round_rescues}` validated cases."
        )
    elif top_lever.get("lever"):
        next_actions.append(
            f"Start with `{top_lever.get('lever')}`; it covers `{top_lever.get('case_count')}` currently classified planner-sensitive failures."
        )
    if promoted_primary_lever and top_lever.get("lever"):
        next_actions.append(
            f"Keep `{top_lever.get('lever')}` as a secondary follow-up lever for planner-sensitive unresolved failures."
        )
    if best_lane.get("family_id"):
        next_actions.append(
            f"Advance `{best_lane.get('family_id')}` next; current status is `{best_lane.get('status')}` with freeze_ready_count=`{best_lane.get('freeze_ready_count')}`."
        )
    if float((classifier.get("metrics") or {}).get("attribution_missing_rate_pct") or 0.0) > 0.0:
        next_actions.append("Reduce attribution-missing failures before claiming deeper failure-family trends.")
    next_actions.append("Keep Claude/Codex comparative maintenance in smoke-only mode until quota/cost conditions improve.")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if classifier.get("status") == "PASS" and lane_gate.get("status") else "FAIL",
        "inputs": {
            "failure_input_path": str(Path(failure_input_path).resolve()) if Path(failure_input_path).exists() else str(failure_input_path),
            "refreshed_candidate_taskset_path": str(Path(refreshed_candidate_taskset_path).resolve()) if Path(refreshed_candidate_taskset_path).exists() else str(refreshed_candidate_taskset_path),
        },
        "top_bottleneck_lever": top_lever,
        "primary_repair_lever": {
            "lever": promoted_primary_lever or str(top_lever.get("lever") or ""),
            "promotion_reason": (
                f"validated deterministic multi-round rescues >= {PROMOTE_MULTI_ROUND_REPAIR_MIN_RESCUES}"
                if promoted_primary_lever
                else "fallback_to_failure_classifier_bottleneck"
            ),
        },
        "evidence_backed_repair_lever": {
            "lever": "multi_round_deterministic_repair_validation" if multi_round_action == "promote_multi_round_deterministic_repair_validation" else "",
            "source": "multi_round_repair_audit" if multi_round_action else "",
            "recommended_action": multi_round_action,
            "metrics": multi_round_metrics if isinstance(multi_round_audit, dict) else {},
        },
        "best_harder_lane": best_lane,
        "failure_classifier_metrics": classifier.get("metrics") or {},
        "multi_round_repair_audit_metrics": multi_round_metrics if isinstance(multi_round_audit, dict) else {},
        "harder_lane_status_counts": {
            str(row.get("status")): len([item for item in lane_rows if isinstance(item, dict) and str(item.get("status")) == str(row.get("status"))])
            for row in lane_rows
            if isinstance(row, dict)
        },
        "next_actions": next_actions,
    }
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# Agent Modelica v0.3.4 Dev Priorities",
        "",
        f"- status: `{payload.get('status')}`",
        f"- primary_repair_lever: `{(payload.get('primary_repair_lever') or {}).get('lever')}`",
        f"- top_bottleneck_lever: `{(payload.get('top_bottleneck_lever') or {}).get('lever')}`",
        f"- evidence_backed_repair_lever: `{(payload.get('evidence_backed_repair_lever') or {}).get('lever')}`",
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
    parser = argparse.ArgumentParser(description="Build an actionable v0.3.4 development-priorities summary.")
    parser.add_argument("--failure-input", required=True)
    parser.add_argument("--refreshed-candidate-taskset", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-freeze-ready-cases", type=int, default=5)
    parser.add_argument("--multi-round-audit-input", default="")
    args = parser.parse_args()
    payload = build_v0_3_4_dev_priorities(
        failure_input_path=str(args.failure_input),
        refreshed_candidate_taskset_path=str(args.refreshed_candidate_taskset),
        out_dir=str(args.out_dir),
        min_freeze_ready_cases=int(args.min_freeze_ready_cases),
        multi_round_audit_input_path=str(args.multi_round_audit_input),
    )
    print(json.dumps({"status": payload.get("status"), "top_bottleneck_lever": (payload.get("top_bottleneck_lever") or {}).get("lever")}))


if __name__ == "__main__":
    main()
