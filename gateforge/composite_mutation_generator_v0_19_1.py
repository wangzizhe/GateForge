from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_19_1_common import (
    DEFAULT_REAL_CASE_BANK_PATH,
    DEFAULT_GENERATOR_OUT_DIR,
    SCHEMA_PREFIX,
    now_utc,
    write_json,
    write_text,
)
from .real_case_bank_v0_19_1 import load_real_case_bank_v191

_SOURCE_MODEL_IDS = [f"source_model_{i:03d}" for i in range(1, 41)]
_PATTERNS = (
    ("surface_cleanup_to_parameter_recovery", "T1", "T5"),
    ("surface_cleanup_to_residual_branch_choice", "T3", "T6"),
)


def build_composite_mutation_generator_v191(
    *,
    out_dir: str = str(DEFAULT_GENERATOR_OUT_DIR),
    case_bank_path: str = str(DEFAULT_REAL_CASE_BANK_PATH),
) -> dict:
    rows: list[dict] = []
    case_bank = load_real_case_bank_v191(case_bank_path=case_bank_path, limit=80)
    if case_bank:
        for candidate_index, case in enumerate(case_bank, start=1):
            surface_tid = str(case.get("surface_layer_taxonomy_id") or "T1")
            residual_tid = str(case.get("residual_layer_taxonomy_id") or "T5")
            optional_third = str(case.get("optional_third_layer_taxonomy_id") or "")
            mutation_count = 2 if not optional_third else 3
            row = {
                "candidate_id": str(case.get("candidate_id") or f"cmp_{candidate_index:03d}"),
                "source_model_id": str(case.get("source_case_id") or case.get("task_id") or ""),
                "task_id": str(case.get("task_id") or ""),
                "source_case_id": str(case.get("source_case_id") or ""),
                "source_model_path": str(case.get("source_model_path") or ""),
                "mutated_model_path": str(case.get("mutated_model_path") or ""),
                "failure_type": str(case.get("failure_type") or ""),
                "expected_stage": str(case.get("expected_stage") or ""),
                "workflow_goal": str(case.get("workflow_goal") or ""),
                "planner_backend": str(case.get("planner_backend") or ""),
                "backend": str(case.get("backend") or ""),
                "scale": str(case.get("scale") or ""),
                "mutation_count": mutation_count,
                "mutation_chain": [surface_tid, residual_tid] + ([optional_third] if optional_third else []),
                "surface_layer_taxonomy_id": surface_tid,
                "residual_layer_taxonomy_id": residual_tid,
                "optional_third_layer_taxonomy_id": optional_third,
                "dependency_masking_pattern": "real_case_corpus_alignment",
                "generator_status": "valid",
            }
            rows.append(row)
    else:
        candidate_index = 0
        for source_idx, source_model_id in enumerate(_SOURCE_MODEL_IDS, start=1):
            for pattern_name, surface_tid, residual_tid in _PATTERNS:
                candidate_index += 1
                mutation_count = 2 if candidate_index % 5 else 3
                optional_third = "T4" if mutation_count == 3 else ""
                row = {
                    "candidate_id": f"cmp_{candidate_index:03d}",
                    "source_model_id": source_model_id,
                    "mutation_count": mutation_count,
                    "mutation_chain": [surface_tid, residual_tid] + ([optional_third] if optional_third else []),
                    "surface_layer_taxonomy_id": surface_tid,
                    "residual_layer_taxonomy_id": residual_tid,
                    "optional_third_layer_taxonomy_id": optional_third,
                    "dependency_masking_pattern": pattern_name,
                    "generator_status": "valid",
                }
                rows.append(row)
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_composite_mutation_generator",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "candidate_count": len(rows),
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.1 Composite Mutation Generator",
                "",
                f"- candidate_count: `{len(rows)}`",
                f"- status: `{payload['status']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.1 composite mutation generator artifact.")
    parser.add_argument("--out-dir", default=str(DEFAULT_GENERATOR_OUT_DIR))
    parser.add_argument("--case-bank", default=str(DEFAULT_REAL_CASE_BANK_PATH))
    args = parser.parse_args()
    payload = build_composite_mutation_generator_v191(out_dir=str(args.out_dir), case_bank_path=str(args.case_bank))
    print(json.dumps({"status": payload["status"], "candidate_count": payload["candidate_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
