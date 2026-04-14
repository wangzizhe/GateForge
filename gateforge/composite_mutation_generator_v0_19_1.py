from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_19_1_common import (
    DEFAULT_GENERATOR_OUT_DIR,
    SCHEMA_PREFIX,
    now_utc,
    write_json,
    write_text,
)

_SOURCE_MODEL_IDS = [f"source_model_{i:03d}" for i in range(1, 41)]
_PATTERNS = (
    ("surface_cleanup_to_parameter_recovery", "T1", "T5"),
    ("surface_cleanup_to_residual_branch_choice", "T3", "T6"),
)


def build_composite_mutation_generator_v191(*, out_dir: str = str(DEFAULT_GENERATOR_OUT_DIR)) -> dict:
    rows: list[dict] = []
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
    args = parser.parse_args()
    payload = build_composite_mutation_generator_v191(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload["status"], "candidate_count": payload["candidate_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
