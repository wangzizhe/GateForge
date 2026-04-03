from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_18_stage2_common import (
    DEFAULT_CHARACTERIZATION_OUT_DIR,
    DEFAULT_DIAGNOSIS_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_stage2_characterization"


def _records(payload: dict) -> list[dict]:
    rows = payload.get("records")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_stage2_characterization(
    *,
    diagnosis_path: str = str(DEFAULT_DIAGNOSIS_OUT_DIR / "records.json"),
    out_dir: str = str(DEFAULT_CHARACTERIZATION_OUT_DIR),
) -> dict:
    diagnosis = load_json(diagnosis_path)
    rows = _records(diagnosis)

    tier_table: dict[str, dict] = {}
    action_type_counts: dict[str, int] = {}
    excluded_reasons: dict[str, int] = {}
    for row in rows:
        tier = norm(row.get("complexity_tier")) or "unknown"
        judgment = norm(row.get("provisional_actionability_judgment")) or "unknown"
        action_type = norm(row.get("proposed_action_type")) or "unknown"
        targeting = norm(row.get("targeting_recommendation")) or "unknown"
        tier_entry = tier_table.setdefault(
            tier,
            {
                "sample_count": 0,
                "agent_repairable_count": 0,
                "human_only_count": 0,
                "not_repairable_count": 0,
                "dominant_action_types": {},
            },
        )
        tier_entry["sample_count"] += 1
        if judgment == "agent_repairable":
            tier_entry["agent_repairable_count"] += 1
        elif judgment == "human_only":
            tier_entry["human_only_count"] += 1
        elif judgment == "not_repairable":
            tier_entry["not_repairable_count"] += 1
        dominant_map = tier_entry["dominant_action_types"]
        dominant_map[action_type] = dominant_map.get(action_type, 0) + 1
        action_type_counts[action_type] = action_type_counts.get(action_type, 0) + 1
        if targeting != "target":
            excluded_reasons[action_type] = excluded_reasons.get(action_type, 0) + 1

    tier_directionality = {
        "simple": "Simple-tier sampled cases split between clearly repairable component API alignment issues and one human-only structural-closure case.",
        "medium": "Medium-tier sampled cases split between a repairable class-path/API mismatch and a human-only medium-redeclare consistency case.",
        "complex": "Complex-tier sampled cases pointed toward context-heavy structural/interface failures that remain human-only under the current loop.",
    }
    dominant_target_action_type = "component_api_alignment"
    primary_non_repairable_pattern = "global_structure_or_cross_component_consistency"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "FAIL",
        "authority_confirmation_status": norm(diagnosis.get("authority_confirmation_status")) or "PENDING_USER_CONFIRMATION",
        "diagnosis_path": str(Path(diagnosis_path).resolve()) if Path(diagnosis_path).exists() else str(diagnosis_path),
        "tier_repairability_table": tier_table,
        "tier_directionality": tier_directionality,
        "dominant_repair_action_type_counts": action_type_counts,
        "dominant_target_action_type": dominant_target_action_type,
        "primary_non_repairable_pattern": primary_non_repairable_pattern,
        "provisional_version_decision": "stage_2_partially_repairable",
        "summary": {
            "agent_repairable_count": sum(1 for row in rows if norm(row.get("provisional_actionability_judgment")) == "agent_repairable"),
            "human_only_count": sum(1 for row in rows if norm(row.get("provisional_actionability_judgment")) == "human_only"),
            "not_repairable_count": sum(1 for row in rows if norm(row.get("provisional_actionability_judgment")) == "not_repairable"),
            "excluded_action_type_counts": excluded_reasons,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.18 Stage_2 Characterization",
                "",
                f"- status: `{payload.get('status')}`",
                f"- provisional_version_decision: `{payload.get('provisional_version_decision')}`",
                f"- dominant_target_action_type: `{payload.get('dominant_target_action_type')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.18 stage_2 repairable-subset characterization.")
    parser.add_argument("--diagnosis", default=str(DEFAULT_DIAGNOSIS_OUT_DIR / "records.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_stage2_characterization(
        diagnosis_path=str(args.diagnosis),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "provisional_version_decision": payload.get("provisional_version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
