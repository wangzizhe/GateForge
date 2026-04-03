from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_14_replay_evidence import _first_attempt_cluster
from .agent_modelica_v0_3_17_common import REPO_ROOT, key_tuple, load_json, now_utc, norm, write_json, write_text


SCHEMA_VERSION = "agent_modelica_v0_3_17_distribution_analysis"
DEFAULT_GENERATION_CENSUS = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_census_current" / "summary.json"
DEFAULT_ONE_STEP_REPAIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_one_step_live_repair_current" / "summary.json"
DEFAULT_EXPERIENCE_STORE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_authority_trace_extraction_current" / "experience_store.json"
DEFAULT_RUNTIME_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_live_results_current"
DEFAULT_INITIALIZATION_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_initialization_live_results_current"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_distribution_analysis_current"


def _result_paths(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted([path for path in directory.glob("*_result.json") if path.is_file()])


def _detail_key_from_result(path: Path) -> tuple[str, str]:
    return _first_attempt_cluster(str(path))


def _build_synthetic_family_keyspace() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for directory in (DEFAULT_RUNTIME_RESULTS_DIR, DEFAULT_INITIALIZATION_RESULTS_DIR):
        for path in _result_paths(directory):
            keys.add(_detail_key_from_result(path))
    return {key for key in keys if all(key)}


def _build_promoted_multiround_keyspace() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for directory in (DEFAULT_RUNTIME_RESULTS_DIR, DEFAULT_INITIALIZATION_RESULTS_DIR):
        for path in _result_paths(directory):
            detail = load_json(path)
            if not bool(detail.get("success")):
                continue
            if not bool(detail.get("planner_invoked")):
                continue
            keys.add(_detail_key_from_result(path))
    return {key for key in keys if all(key)}


def _build_replay_keyspace(experience_store: dict) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for row in experience_store.get("step_records") or []:
        if not isinstance(row, dict):
            continue
        key = (norm(row.get("dominant_stage_subtype")), norm(row.get("residual_signal_cluster")))
        if all(key):
            keys.add(key)
    return keys


def _label_counts(rows: list[dict], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field_name) or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


def _overlap_counts(rows: list[dict], field_name: str, keyspace: set[tuple[str, str]]) -> dict[str, object]:
    total = 0
    matched = 0
    for row in rows:
        snapshot = row.get(field_name) if isinstance(row.get(field_name), dict) else {}
        key = key_tuple(snapshot)
        if not all(key):
            continue
        total += 1
        if key in keyspace:
            matched += 1
    return {
        "eligible_count": total,
        "matched_count": matched,
        "matched_rate_pct": round(100.0 * matched / float(total), 1) if total else 0.0,
    }


def _rows_by_tier(rows: list[dict]) -> dict[str, list[dict]]:
    grouped = {"simple": [], "medium": [], "complex": []}
    for row in rows:
        tier = str(row.get("complexity_tier") or "").strip().lower()
        if tier in grouped:
            grouped[tier].append(row)
    return grouped


def _first_failure_rows(generation_summary: dict) -> list[dict]:
    rows = []
    for row in generation_summary.get("rows") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "task_id": row.get("task_id"),
                "complexity_tier": row.get("complexity_tier"),
                "first_failure": row.get("first_failure") if isinstance(row.get("first_failure"), dict) else {},
                "first_failure_actionability": row.get("first_failure_actionability")
                or "",
            }
        )
    return rows


def _inject_actionability(rows: list[dict], field_name: str) -> None:
    for row in rows:
        snapshot = row.get(field_name) if isinstance(row.get(field_name), dict) else {}
        suggested = snapshot.get("suggested_actions") if isinstance(snapshot.get("suggested_actions"), list) else []
        stage = str(snapshot.get("dominant_stage_subtype") or "")
        if stage.startswith("stage_1_"):
            label = "high_actionability"
        elif stage.startswith("stage_2_"):
            label = "low_actionability"
        elif stage.startswith("stage_4_"):
            label = "medium_actionability"
        elif stage.startswith("stage_5_") and suggested:
            label = "high_actionability"
        elif stage.startswith("stage_5_"):
            label = "medium_actionability"
        elif stage.startswith("stage_0_"):
            label = "high_actionability"
        else:
            label = "low_actionability"
        row[f"{field_name}_actionability"] = label


def _tier_report(rows: list[dict], *, synthetic_keys: set[tuple[str, str]], replay_keys: set[tuple[str, str]], promoted_keys: set[tuple[str, str]], field_name: str, actionability_field: str) -> dict:
    return {
        "count": len(rows),
        "actionability_distribution": _label_counts(rows, actionability_field),
        "synthetic_family_overlap": _overlap_counts(rows, field_name, synthetic_keys),
        "replay_keyspace_overlap": _overlap_counts(rows, field_name, replay_keys),
        "promoted_multiround_overlap": _overlap_counts(rows, field_name, promoted_keys),
    }


def _decide(second_residual_report: dict) -> str:
    overall_synth = float((((second_residual_report.get("overall") or {}).get("synthetic_family_overlap") or {}).get("matched_rate_pct") or 0.0))
    overall_replay = float((((second_residual_report.get("overall") or {}).get("replay_keyspace_overlap") or {}).get("matched_rate_pct") or 0.0))
    medium_plus_pct = 0.0
    overall_actionability = (((second_residual_report.get("overall") or {}).get("actionability_distribution") or {}))
    total = sum(int(v or 0) for v in overall_actionability.values())
    if total:
        medium_plus_pct = round(
            100.0
            * (
                int(overall_actionability.get("high_actionability", 0))
                + int(overall_actionability.get("medium_actionability", 0))
            )
            / float(total),
            1,
        )
    tier_reports = second_residual_report.get("tiers") if isinstance(second_residual_report.get("tiers"), dict) else {}
    tier_synth = [
        float((((tier_reports.get(tier) or {}).get("synthetic_family_overlap") or {}).get("matched_rate_pct") or 0.0))
        for tier in ("simple", "medium", "complex")
    ]
    if overall_synth >= 60.0 and overall_replay >= 50.0 and medium_plus_pct >= 60.0 and min(tier_synth) >= 40.0:
        return "distribution_alignment_supported"
    if overall_synth >= 30.0 or overall_replay >= 25.0 or max(tier_synth) >= 40.0:
        return "distribution_alignment_partial"
    return "distribution_alignment_not_supported"


def build_distribution_analysis(
    *,
    generation_census_path: str = str(DEFAULT_GENERATION_CENSUS),
    one_step_repair_path: str = str(DEFAULT_ONE_STEP_REPAIR),
    experience_store_path: str = str(DEFAULT_EXPERIENCE_STORE),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    generation = load_json(generation_census_path)
    one_step = load_json(one_step_repair_path)
    experience_store = load_json(experience_store_path)
    synthetic_keys = _build_synthetic_family_keyspace()
    promoted_keys = _build_promoted_multiround_keyspace()
    replay_keys = _build_replay_keyspace(experience_store)

    first_rows = _first_failure_rows(generation)
    _inject_actionability(first_rows, "first_failure")
    second_rows = [row for row in (one_step.get("rows") or []) if isinstance(row, dict)]

    first_by_tier = _rows_by_tier(first_rows)
    second_by_tier = _rows_by_tier(second_rows)

    first_report = {
        "overall": _tier_report(
            first_rows,
            synthetic_keys=synthetic_keys,
            replay_keys=replay_keys,
            promoted_keys=promoted_keys,
            field_name="first_failure",
            actionability_field="first_failure_actionability",
        ),
        "tiers": {
            tier: _tier_report(
                rows,
                synthetic_keys=synthetic_keys,
                replay_keys=replay_keys,
                promoted_keys=promoted_keys,
                field_name="first_failure",
                actionability_field="first_failure_actionability",
            )
            for tier, rows in first_by_tier.items()
        },
    }
    second_report = {
        "overall": _tier_report(
            second_rows,
            synthetic_keys=synthetic_keys,
            replay_keys=replay_keys,
            promoted_keys=promoted_keys,
            field_name="second_residual",
            actionability_field="second_residual_actionability",
        ),
        "tiers": {
            tier: _tier_report(
                rows,
                synthetic_keys=synthetic_keys,
                replay_keys=replay_keys,
                promoted_keys=promoted_keys,
                field_name="second_residual",
                actionability_field="second_residual_actionability",
            )
            for tier, rows in second_by_tier.items()
        },
    }
    decision = _decide(second_report)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "generation_census_path": str(Path(generation_census_path).resolve()) if Path(generation_census_path).exists() else str(generation_census_path),
        "one_step_repair_path": str(Path(one_step_repair_path).resolve()) if Path(one_step_repair_path).exists() else str(one_step_repair_path),
        "experience_store_path": str(Path(experience_store_path).resolve()) if Path(experience_store_path).exists() else str(experience_store_path),
        "synthetic_family_key_count": len(synthetic_keys),
        "replay_keyspace_key_count": len(replay_keys),
        "promoted_multiround_key_count": len(promoted_keys),
        "first_failure_report": first_report,
        "second_residual_report": second_report,
        "version_decision": decision,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.17 Distribution Analysis",
                "",
                f"- status: `{payload.get('status')}`",
                f"- version_decision: `{decision}`",
                f"- synthetic_family_key_count: `{len(synthetic_keys)}`",
                f"- replay_keyspace_key_count: `{len(replay_keys)}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.17 actionability and overlap analysis.")
    parser.add_argument("--generation-census", default=str(DEFAULT_GENERATION_CENSUS))
    parser.add_argument("--one-step-repair", default=str(DEFAULT_ONE_STEP_REPAIR))
    parser.add_argument("--experience-store", default=str(DEFAULT_EXPERIENCE_STORE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_distribution_analysis(
        generation_census_path=str(args.generation_census),
        one_step_repair_path=str(args.one_step_repair),
        experience_store_path=str(args.experience_store),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": payload.get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
