from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_resolution_attribution_v1 import build_resolution_attribution


SCHEMA_VERSION = "agent_modelica_foundation_acceptance_v0"


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
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


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _records(payload: dict) -> list[dict]:
    if isinstance(payload.get("records"), list):
        rows = payload.get("records")
    elif isinstance(payload.get("results"), list):
        rows = payload.get("results")
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _row_success(row: dict) -> bool:
    if bool(row.get("passed")):
        return True
    hard_checks = row.get("hard_checks") if isinstance(row.get("hard_checks"), dict) else {}
    if hard_checks:
        return bool(
            hard_checks.get("check_model_pass")
            and hard_checks.get("simulate_pass")
            and hard_checks.get("physics_contract_pass", True)
            and hard_checks.get("regression_pass", True)
        )
    return bool(
        row.get("check_model_pass")
        and row.get("simulate_pass")
        and row.get("physics_contract_pass", True)
        and row.get("regression_pass", True)
    )


def summarize_lane(lane: dict) -> dict:
    lane_id = str(lane.get("lane_id") or "").strip() or "unknown_lane"
    label = str(lane.get("label") or lane_id)
    run_results_path = str(lane.get("run_results") or "")
    sidecar_path = str(lane.get("sidecar") or "")
    planner_expected = bool(lane.get("planner_expected"))
    require_stage_subtype_coverage = bool(lane.get("require_stage_subtype_coverage", True))
    payload = _load_json(run_results_path)
    rows = _records(payload)

    record_count = len(rows)
    success_count = 0
    stage_subtype_present_count = 0
    unresolved_success_count = 0
    planner_invoked_count = 0
    saved_vs_recomputed_mismatch_count = 0

    for row in rows:
        recomputed = build_resolution_attribution(row)
        saved_resolution_path = str(row.get("resolution_path") or "").strip()
        saved_stage_subtype = str(row.get("dominant_stage_subtype") or "").strip()
        resolved_path = str(recomputed.get("resolution_path") or saved_resolution_path)
        stage_subtype = str(recomputed.get("dominant_stage_subtype") or saved_stage_subtype)
        planner_invoked = bool(recomputed.get("planner_invoked"))

        if saved_resolution_path and saved_resolution_path != resolved_path:
            saved_vs_recomputed_mismatch_count += 1
        elif saved_stage_subtype and saved_stage_subtype != stage_subtype:
            saved_vs_recomputed_mismatch_count += 1

        if stage_subtype:
            stage_subtype_present_count += 1
        if planner_invoked:
            planner_invoked_count += 1
        if _row_success(row):
            success_count += 1
            if resolved_path == "unresolved":
                unresolved_success_count += 1

    return {
        "lane_id": lane_id,
        "label": label,
        "run_results_path": run_results_path,
        "sidecar_path": sidecar_path,
        "record_count": record_count,
        "success_count": success_count,
        "stage_subtype_present_count": stage_subtype_present_count,
        "stage_subtype_coverage_pct": _ratio(stage_subtype_present_count, record_count),
        "unresolved_success_count": unresolved_success_count,
        "saved_vs_recomputed_mismatch_count": saved_vs_recomputed_mismatch_count,
        "planner_expected": planner_expected,
        "require_stage_subtype_coverage": require_stage_subtype_coverage,
        "planner_invoked_count": planner_invoked_count,
        "planner_invoked_rate_pct": _ratio(planner_invoked_count, record_count),
        "sidecar_exists": bool(sidecar_path and Path(sidecar_path).exists()),
        "run_results_exists": bool(run_results_path and Path(run_results_path).exists()),
    }


def _layer4_metrics(layer_summary: dict) -> dict:
    gap = layer_summary.get("coverage_gap") if isinstance(layer_summary.get("coverage_gap"), dict) else {}
    counts = gap.get("aggregate_layer_counts") if isinstance(gap.get("aggregate_layer_counts"), dict) else {}
    total = 0
    for value in counts.values():
        if isinstance(value, int):
            total += int(value)
    layer4_count = int(counts.get("layer_4") or 0)
    return {
        "aggregate_layer_counts": {str(k): int(v) for k, v in counts.items() if isinstance(v, int)},
        "total_case_count": total,
        "layer_4_case_count": layer4_count,
        "layer_4_share_pct": _ratio(layer4_count, total),
    }


def build_summary(spec: dict) -> dict:
    thresholds = spec.get("thresholds") if isinstance(spec.get("thresholds"), dict) else {}
    min_stage_subtype_coverage_pct = float(thresholds.get("min_stage_subtype_coverage_pct") or 95.0)
    max_unresolved_success_count = int(thresholds.get("max_unresolved_success_count") or 0)
    min_planner_invoked_rate_pct_when_expected = float(
        thresholds.get("min_planner_invoked_rate_pct_when_expected") or 50.0
    )
    max_layer4_share_pct = thresholds.get("max_layer4_share_pct")
    max_layer4_case_count = thresholds.get("max_layer4_case_count")

    layer_summary_path = str(spec.get("layer_summary") or "")
    layer_summary = _load_json(layer_summary_path)
    lanes = spec.get("lanes") if isinstance(spec.get("lanes"), list) else []
    lane_summaries = [summarize_lane(lane) for lane in lanes if isinstance(lane, dict)]

    required_regeneration_paths = [
        str(path) for path in (spec.get("required_regeneration_paths") or []) if str(path).strip()
    ]
    missing_regeneration_paths = [
        path for path in required_regeneration_paths if not Path(path).exists()
    ]

    checks: dict[str, dict] = {}
    reasons: list[str] = []

    stage_ok = True
    resolution_ok = True
    sidecar_ok = True
    planner_ok = True
    for lane in lane_summaries:
        if bool(lane.get("require_stage_subtype_coverage", True)) and float(lane.get("stage_subtype_coverage_pct") or 0.0) < min_stage_subtype_coverage_pct:
            stage_ok = False
        if int(lane.get("unresolved_success_count") or 0) > max_unresolved_success_count:
            resolution_ok = False
        if not bool(lane.get("sidecar_exists")):
            sidecar_ok = False
        if bool(lane.get("planner_expected")) and float(lane.get("planner_invoked_rate_pct") or 0.0) < min_planner_invoked_rate_pct_when_expected:
            planner_ok = False

    checks["dominant_stage_subtype_coverage"] = {
        "status": "PASS" if stage_ok else "FAIL",
        "min_required_pct": min_stage_subtype_coverage_pct,
    }
    checks["resolution_path_consistency"] = {
        "status": "PASS" if resolution_ok else "FAIL",
        "max_unresolved_success_count": max_unresolved_success_count,
    }
    checks["difficulty_layer_sidecar_coverage"] = {
        "status": "PASS" if sidecar_ok else "FAIL",
    }
    checks["planner_sensitive_activation"] = {
        "status": "PASS" if planner_ok else "FAIL",
        "min_required_pct_when_expected": min_planner_invoked_rate_pct_when_expected,
    }
    checks["regeneration_path_presence"] = {
        "status": "PASS" if not missing_regeneration_paths else "FAIL",
        "missing_paths": missing_regeneration_paths,
    }

    layer4 = _layer4_metrics(layer_summary)
    scarcity_ok = True
    scarcity_constraints: dict[str, float | int] = {}
    if isinstance(max_layer4_share_pct, (int, float)):
        scarcity_constraints["max_layer4_share_pct"] = float(max_layer4_share_pct)
        if float(layer4.get("layer_4_share_pct") or 0.0) > float(max_layer4_share_pct):
            scarcity_ok = False
    if isinstance(max_layer4_case_count, int):
        scarcity_constraints["max_layer4_case_count"] = int(max_layer4_case_count)
        if int(layer4.get("layer_4_case_count") or 0) > int(max_layer4_case_count):
            scarcity_ok = False
    checks["layer_4_scarcity_confirmation"] = {
        "status": "PASS" if scarcity_ok else "FAIL",
        "layer_4_metrics": layer4,
        "constraints": scarcity_constraints,
    }

    for key, row in checks.items():
        if str(row.get("status") or "") != "PASS":
            reasons.append(f"{key}_not_pass")

    status = "PASS" if not reasons else "FAIL"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reasons": reasons,
        "checks": checks,
        "lane_count": len(lane_summaries),
        "lanes": lane_summaries,
        "sources": {
            "layer_summary": layer_summary_path,
            "required_regeneration_paths": required_regeneration_paths,
        },
    }


def _write_markdown(path: str | Path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Foundation Acceptance v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- lane_count: `{payload.get('lane_count')}`",
        f"- reasons: `{','.join(payload.get('reasons') or []) or 'none'}`",
        "",
        "## Checks",
        "",
    ]
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    for key, row in checks.items():
        if not isinstance(row, dict):
            continue
        lines.append(f"- {key}: `{row.get('status')}`")
    lines.append("")
    lines.append("## Lanes")
    lines.append("")
    for lane in payload.get("lanes") or []:
        if not isinstance(lane, dict):
            continue
        lines.append(
            f"- {lane.get('lane_id')}: records=`{lane.get('record_count')}`, stage_subtype_coverage_pct=`{lane.get('stage_subtype_coverage_pct')}`, unresolved_success_count=`{lane.get('unresolved_success_count')}`, planner_invoked_rate_pct=`{lane.get('planner_invoked_rate_pct')}`, saved_vs_recomputed_mismatch_count=`{lane.get('saved_vs_recomputed_mismatch_count')}`, sidecar_exists=`{lane.get('sidecar_exists')}`"
        )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Block 0 foundation acceptance checks for Agent-Modelica v0.3.0")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    spec = _load_json(str(args.spec))
    payload = build_summary(spec)
    _write_json(str(args.out), payload)
    _write_markdown(str(args.report_out or _default_md_path(str(args.out))), payload)
    print(json.dumps({"status": payload.get("status"), "lane_count": int(payload.get("lane_count") or 0)}))
    if payload.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
