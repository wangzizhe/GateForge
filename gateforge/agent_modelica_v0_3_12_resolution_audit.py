from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_resolution_audit_v0_3_2 import summarize_lane_payload


SCHEMA_VERSION = "agent_modelica_v0_3_12_resolution_audit"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_12_resolution_audit"
DEFAULT_LANES = (
    {
        "lane_id": "track_a",
        "label": "Track A",
        "source_path": "artifacts/agent_modelica_planner_sensitive_pack_builder_v1/gf_results_track_a_v0_2_5.json",
        "lane_role": "authority_track",
    },
    {
        "lane_id": "track_b",
        "label": "Track B",
        "source_path": "artifacts/agent_modelica_track_b_attribution_proxy_v0_3_2/summary.json",
        "lane_role": "authority_track",
    },
    {
        "lane_id": "harder_holdout",
        "label": "Harder Holdout",
        "source_path": "artifacts/agent_modelica_harder_holdout_ablation_v0_3_1/baseline/gf_results.json",
        "lane_role": "layer4_calibration",
    },
    {
        "lane_id": "planner_sensitive",
        "label": "Planner-Sensitive Lane",
        "source_path": "artifacts/agent_modelica_planner_sensitive_attribution_repair_v0_3_2/summary_baseline.json",
        "lane_role": "planner_calibration",
    },
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _path_pct(lane: dict, path_name: str) -> float:
    payload = lane.get("success_resolution_path_pct")
    if not isinstance(payload, dict):
        return 0.0
    return float(payload.get(path_name) or 0.0)


def _path_count(lane: dict, path_name: str) -> int:
    payload = lane.get("all_resolution_path_counts")
    if not isinstance(payload, dict):
        return 0
    return int(payload.get(path_name) or 0)


def _interpret_lane(lane: dict) -> str:
    lane_id = _norm(lane.get("lane_id"))
    deterministic_pct = _path_pct(lane, "deterministic_rule_only")
    rule_then_llm_pct = _path_pct(lane, "rule_then_llm")
    llm_assisted_pct = _path_pct(lane, "llm_planner_assisted")
    unresolved_count = _path_count(lane, "unresolved")
    if str(lane.get("status") or "") != "PASS":
        return "artifact_gap_blocks_interpretation"
    if lane_id in {"track_a", "track_b"} and deterministic_pct >= 80.0:
        return "deterministic_dominated_not_suitable_for_planner_claim"
    if lane_id == "harder_holdout":
        if unresolved_count > 0 and deterministic_pct >= 80.0:
            return "mixed_calibration_lane_with_failure_signal_not_clean_comparative_slice"
        if unresolved_count > 0:
            return "contains_unresolved_cases_needs_failure_sidecar"
    if lane_id == "planner_sensitive":
        if llm_assisted_pct + rule_then_llm_pct >= 80.0:
            return "planner_expressive_reference_lane"
    if deterministic_pct >= 80.0:
        return "deterministic_dominated"
    if llm_assisted_pct + rule_then_llm_pct > 0.0:
        return "planner_expressive"
    return "mixed_or_unclear"


def build_v0_3_12_overall_interpretation(lanes: list[dict]) -> dict:
    deterministic_dominated_lanes: list[str] = []
    planner_expressive_lanes: list[str] = []
    unresolved_lanes: list[str] = []
    attribution_gap_lanes: list[str] = []
    lane_notes: dict[str, str] = {}

    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        lane_id = _norm(lane.get("lane_id"))
        if str(lane.get("status") or "") != "PASS":
            attribution_gap_lanes.append(lane_id)
        if _path_pct(lane, "deterministic_rule_only") >= 80.0:
            deterministic_dominated_lanes.append(lane_id)
        if _path_pct(lane, "llm_planner_assisted") + _path_pct(lane, "rule_then_llm") >= 50.0:
            planner_expressive_lanes.append(lane_id)
        if _path_count(lane, "unresolved") > 0:
            unresolved_lanes.append(lane_id)
        lane_notes[lane_id] = _interpret_lane(lane)

    track_a_det = "track_a" in deterministic_dominated_lanes
    track_b_det = "track_b" in deterministic_dominated_lanes
    planner_sensitive_ready = "planner_sensitive" in planner_expressive_lanes
    harder_holdout_unresolved = "harder_holdout" in unresolved_lanes

    paper_claim_status = "partial_support_only"
    paper_claim_recommendation = "resolution_audit_insufficient"
    if track_a_det and track_b_det and planner_sensitive_ready:
        paper_claim_status = "planner_value_visible_only_on_calibration_lane"
        paper_claim_recommendation = "use_planner_sensitive_as_calibration_reference_not_main_comparative_slice"
    if track_a_det and track_b_det and planner_sensitive_ready and harder_holdout_unresolved:
        paper_claim_recommendation = "treat_harder_holdout_as_failure_sidecar_and_design_new_track_c_slice"
    elif track_a_det and track_b_det and planner_sensitive_ready:
        paper_claim_recommendation = "design_new_track_c_slice_away_from_deterministic_tracks"

    return {
        "status": "PASS" if not attribution_gap_lanes else "NEEDS_RERUN",
        "deterministic_dominated_lanes": deterministic_dominated_lanes,
        "planner_expressive_lanes": planner_expressive_lanes,
        "unresolved_lanes": unresolved_lanes,
        "attribution_gap_lanes": attribution_gap_lanes,
        "lane_interpretations": lane_notes,
        "paper_claim_status": paper_claim_status,
        "paper_claim_recommendation": paper_claim_recommendation,
        "takeaways": [
            "Track A and Track B are still dominated by deterministic_rule_only success paths." if track_a_det and track_b_det else "Authority tracks are not uniformly deterministic dominated.",
            "Planner-sensitive lane is still the only clean current lane where planner-mediated success dominates." if planner_sensitive_ready else "Planner-sensitive lane does not yet provide a clean planner-mediated success signal.",
            "Harder holdout should be treated as a mixed calibration/failure lane rather than the main comparative moat slice." if harder_holdout_unresolved else "Harder holdout does not currently force a failure-sidecar route.",
        ],
    }


def render_markdown(payload: dict) -> str:
    overall = payload.get("overall") if isinstance(payload.get("overall"), dict) else {}
    lines = [
        "# GateForge v0.3.12 Resolution Audit",
        "",
        f"- status: `{_norm(overall.get('status'))}`",
        f"- paper_claim_status: `{_norm(overall.get('paper_claim_status'))}`",
        f"- paper_claim_recommendation: `{_norm(overall.get('paper_claim_recommendation'))}`",
        "",
        "## Overall",
        "",
        f"- deterministic_dominated_lanes: `{', '.join(overall.get('deterministic_dominated_lanes') or [])}`",
        f"- planner_expressive_lanes: `{', '.join(overall.get('planner_expressive_lanes') or [])}`",
        f"- unresolved_lanes: `{', '.join(overall.get('unresolved_lanes') or [])}`",
        f"- attribution_gap_lanes: `{', '.join(overall.get('attribution_gap_lanes') or [])}`",
        "",
        "## Lanes",
        "",
    ]
    for lane in payload.get("lanes") or []:
        if not isinstance(lane, dict):
            continue
        lane_id = _norm(lane.get("lane_id"))
        lines.append(f"### {lane.get('label')}")
        lines.append("")
        lines.append(f"- lane_id: `{lane_id}`")
        lines.append(f"- status: `{lane.get('status')}`")
        lines.append(f"- source_path: `{lane.get('source_path')}`")
        lines.append(f"- task_count: `{lane.get('task_count')}`, success_count: `{lane.get('success_count')}`, success_rate_pct: `{lane.get('success_rate_pct')}`")
        lines.append(f"- success_resolution_path_counts: `{json.dumps(lane.get('success_resolution_path_counts') or {}, sort_keys=True)}`")
        lines.append(f"- all_resolution_path_counts: `{json.dumps(lane.get('all_resolution_path_counts') or {}, sort_keys=True)}`")
        lines.append(f"- interpretation: `{(overall.get('lane_interpretations') or {}).get(lane_id, '')}`")
        notes = lane.get("notes") if isinstance(lane.get("notes"), list) else []
        if notes:
            lines.append(f"- notes: `{'; '.join(str(note) for note in notes)}`")
        lines.append("")
    if isinstance(overall.get("takeaways"), list) and overall.get("takeaways"):
        lines.append("## Takeaways")
        lines.append("")
        for note in overall.get("takeaways") or []:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_v0_3_12_resolution_audit(*, out_dir: str = DEFAULT_OUT_DIR, lane_overrides: list[dict] | None = None) -> dict:
    lane_rows: list[dict] = []
    for lane_cfg in (lane_overrides if lane_overrides is not None else list(DEFAULT_LANES)):
        lane_id = _norm(lane_cfg.get("lane_id"))
        label = _norm(lane_cfg.get("label") or lane_id)
        source_path = _norm(lane_cfg.get("source_path"))
        payload = _load_json(source_path)
        lane = summarize_lane_payload(
            lane_id=lane_id,
            label=label,
            source_path=source_path,
            payload=payload,
        )
        lane["lane_role"] = _norm(lane_cfg.get("lane_role"))
        lane_rows.append(lane)

    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "lanes": lane_rows,
        "overall": build_v0_3_12_overall_interpretation(lane_rows),
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", result)
    _write_text(out_root / "summary.md", render_markdown(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.12 resolution audit sidecar from current authority artifacts.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_12_resolution_audit(out_dir=str(args.out_dir))
    print(json.dumps(payload.get("overall") or {}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
