from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_planner_sensitive_pack_builder_v1"
DEFAULT_TARGET_STAGE_SUBTYPES = (
    "stage_3_behavioral_contract_semantic",
    "stage_3_type_connector_semantic",
    "stage_4_initialization_singularity",
)
DEFAULT_INCLUDE_RESOLUTION_PATHS = (
    "rule_then_llm",
    "llm_planner_assisted",
)


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    payload = json.loads(p.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _stage_priority(stage_subtype: str) -> int:
    stage = str(stage_subtype or "").strip().lower()
    if stage == "stage_3_behavioral_contract_semantic":
        return 2
    if stage == "stage_4_initialization_singularity":
        return 2
    if stage in {"stage_3_type_connector_consistency", "stage_3_type_connector_semantic"}:
        return 1
    return 0


def _select_result_rows(
    *,
    results: list[dict],
    target_stage_subtypes: tuple[str, ...],
    include_resolution_paths: tuple[str, ...],
) -> list[dict]:
    rows: list[dict] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        resolution = row.get("resolution_attribution") if isinstance(row.get("resolution_attribution"), dict) else {}
        mutation_id = str(row.get("mutation_id") or "").strip()
        stage_subtype = str(
            resolution.get("dominant_stage_subtype")
            or row.get("dominant_stage_subtype")
            or ""
        ).strip()
        resolution_path = str(
            resolution.get("resolution_path")
            or row.get("resolution_path")
            or ""
        ).strip()
        planner_invoked = bool(resolution.get("planner_invoked")) or bool(row.get("planner_invoked"))
        planner_used = bool(resolution.get("planner_used")) or bool(row.get("planner_used"))
        planner_decisive = bool(resolution.get("planner_decisive")) or bool(row.get("planner_decisive"))
        llm_request_count = int(resolution.get("llm_request_count") or 0)

        reasons: list[str] = []
        score = 0
        if stage_subtype in target_stage_subtypes:
            reasons.append("target_stage_subtype")
            score += 2 + _stage_priority(stage_subtype)
        if resolution_path in include_resolution_paths:
            reasons.append("llm_resolution_path")
            score += 3
        if planner_invoked:
            reasons.append("planner_invoked")
            score += 3
        if planner_used:
            reasons.append("planner_used")
            score += 2
        if planner_decisive:
            reasons.append("planner_decisive")
            score += 2
        if llm_request_count > 0:
            reasons.append("llm_request_count_positive")
            score += 1

        if not mutation_id or not reasons:
            continue
        rows.append(
            {
                "mutation_id": mutation_id,
                "expected_failure_type": str(row.get("expected_failure_type") or ""),
                "target_scale": str(row.get("target_scale") or ""),
                "dominant_stage_subtype": stage_subtype,
                "resolution_path": resolution_path,
                "planner_invoked": planner_invoked,
                "planner_used": planner_used,
                "planner_decisive": planner_decisive,
                "llm_request_count": llm_request_count,
                "selection_reasons": reasons,
                "selection_score": score,
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row.get("selection_score") or 0),
            -_stage_priority(str(row.get("dominant_stage_subtype") or "")),
            str(row.get("target_scale") or ""),
            str(row.get("mutation_id") or ""),
        )
    )
    return rows


def build_planner_sensitive_pack(
    *,
    source_pack_path: str,
    gf_results_paths: list[str],
    out_pack_path: str,
    max_cases: int = 24,
    target_stage_subtypes: tuple[str, ...] = DEFAULT_TARGET_STAGE_SUBTYPES,
    include_resolution_paths: tuple[str, ...] = DEFAULT_INCLUDE_RESOLUTION_PATHS,
    planner_invoked_target_pct: float = 50.0,
) -> dict:
    source_pack = _load_json(source_pack_path)
    source_cases = source_pack.get("cases") if isinstance(source_pack.get("cases"), list) else []
    source_cases = [row for row in source_cases if isinstance(row, dict)]
    case_by_mutation_id = {
        str(row.get("mutation_id") or "").strip(): row
        for row in source_cases
        if str(row.get("mutation_id") or "").strip()
    }

    selected_rows: list[dict] = []
    seen: set[str] = set()
    missing_results: list[str] = []
    for path in gf_results_paths:
        payload = _load_json(path)
        if not payload:
            missing_results.append(str(path))
            continue
        rows = _select_result_rows(
            results=[row for row in (payload.get("results") or []) if isinstance(row, dict)],
            target_stage_subtypes=target_stage_subtypes,
            include_resolution_paths=include_resolution_paths,
        )
        for row in rows:
            mutation_id = str(row.get("mutation_id") or "")
            if mutation_id in seen or mutation_id not in case_by_mutation_id:
                continue
            seen.add(mutation_id)
            selected_rows.append(row)

    selected_rows = selected_rows[: max(0, int(max_cases or 0))] if int(max_cases or 0) > 0 else selected_rows
    selected_cases = [case_by_mutation_id[str(row.get("mutation_id") or "")] for row in selected_rows if str(row.get("mutation_id") or "") in case_by_mutation_id]
    planner_invoked_count = len([row for row in selected_rows if bool(row.get("planner_invoked"))])
    planner_invoked_rate_pct = round((planner_invoked_count / len(selected_rows)) * 100.0, 2) if selected_rows else 0.0

    if not selected_rows:
        status = "FAIL"
        validation_reason = "no_planner_sensitive_candidates"
    elif planner_invoked_rate_pct < float(planner_invoked_target_pct):
        status = "NEEDS_REVIEW"
        validation_reason = "planner_invoked_rate_below_target"
    else:
        status = "PASS"
        validation_reason = "planner_invoked_rate_met"

    pack_payload = {
        **{k: v for k, v in source_pack.items() if k != "cases"},
        "pack_label": str(source_pack.get("pack_label") or "Planner-Sensitive Pack").strip() or "Planner-Sensitive Pack",
        "planner_sensitive_metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_pack_path": str(source_pack_path),
            "gf_results_paths": [str(path) for path in gf_results_paths],
            "planner_invoked_target_pct": float(planner_invoked_target_pct),
            "planner_invoked_rate_pct": planner_invoked_rate_pct,
            "selection_count": len(selected_rows),
            "validation_status": status,
            "validation_reason": validation_reason,
        },
        "cases": selected_cases,
    }
    _write_json(out_pack_path, pack_payload)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "validation_reason": validation_reason,
        "source_pack_path": str(source_pack_path),
        "out_pack_path": str(out_pack_path),
        "gf_results_paths": [str(path) for path in gf_results_paths],
        "planner_invoked_target_pct": float(planner_invoked_target_pct),
        "planner_invoked_rate_pct": planner_invoked_rate_pct,
        "selected_case_count": len(selected_rows),
        "selected_rows": selected_rows,
        "missing_results": missing_results,
        "target_stage_subtypes": list(target_stage_subtypes),
        "include_resolution_paths": list(include_resolution_paths),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a planner-sensitive hardpack subset from prior GF batch results")
    parser.add_argument("--source-pack", required=True)
    parser.add_argument("--gf-results", action="append", default=[])
    parser.add_argument("--out-pack", required=True)
    parser.add_argument("--out-summary", default="")
    parser.add_argument("--max-cases", type=int, default=24)
    parser.add_argument("--target-stage-subtype", action="append", default=list(DEFAULT_TARGET_STAGE_SUBTYPES))
    parser.add_argument("--include-resolution-path", action="append", default=list(DEFAULT_INCLUDE_RESOLUTION_PATHS))
    parser.add_argument("--planner-invoked-target-pct", type=float, default=50.0)
    args = parser.parse_args()

    out_summary = str(args.out_summary or "")
    if not out_summary:
        out_summary = str(Path(args.out_pack).with_name("planner_sensitive_summary.json"))
    summary = build_planner_sensitive_pack(
        source_pack_path=args.source_pack,
        gf_results_paths=[str(path) for path in (args.gf_results or []) if str(path).strip()],
        out_pack_path=str(args.out_pack),
        max_cases=int(args.max_cases or 0),
        target_stage_subtypes=tuple(str(x) for x in (args.target_stage_subtype or []) if str(x).strip()),
        include_resolution_paths=tuple(str(x) for x in (args.include_resolution_path or []) if str(x).strip()),
        planner_invoked_target_pct=float(args.planner_invoked_target_pct or 0.0),
    )
    _write_json(out_summary, summary)
    print(json.dumps({"status": summary.get("status"), "selected_case_count": summary.get("selected_case_count")}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
