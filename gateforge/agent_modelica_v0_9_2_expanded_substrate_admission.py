from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_9_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_9_0_common import PRIORITY_BARRIERS
from .agent_modelica_v0_9_2_common import (
    DEFAULT_EXPANDED_SUBSTRATE_ADMISSION_OUT_DIR,
    DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR,
    MAX_SUBSTRATE_SIZE,
    MIN_SUBSTRATE_SIZE,
    READY_BARRIER_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_2_expanded_substrate_builder import build_v092_expanded_substrate_builder


def build_v092_expanded_substrate_admission(
    *,
    expanded_substrate_builder_path: str = str(DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_EXPANDED_SUBSTRATE_ADMISSION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    if not Path(expanded_substrate_builder_path).exists():
        build_v092_expanded_substrate_builder(out_dir=str(Path(expanded_substrate_builder_path).parent))
    builder = load_json(expanded_substrate_builder_path)
    rows = builder.get("expanded_substrate_candidate_table") if isinstance(builder.get("expanded_substrate_candidate_table"), list) else []
    evaluations = evaluate_candidate_rows(rows)
    admitted = [verdict for verdict in evaluations if verdict.get("admitted")]
    size = len(rows)
    barrier_counts = builder.get("priority_barrier_coverage_table") if isinstance(builder.get("priority_barrier_coverage_table"), dict) else {}
    workflow_family_mix = builder.get("workflow_family_mix") if isinstance(builder.get("workflow_family_mix"), dict) else {}
    complexity_mix = builder.get("complexity_mix") if isinstance(builder.get("complexity_mix"), dict) else {}
    template_mix = builder.get("workflow_task_template_mix") if isinstance(builder.get("workflow_task_template_mix"), dict) else {}
    governance_pass_rate_pct = 100.0 * len(admitted) / size if size else 0.0
    no_zero_barrier = all(int(barrier_counts.get(barrier) or 0) > 0 for barrier in PRIORITY_BARRIERS)
    all_barriers_ready = all(int(barrier_counts.get(barrier) or 0) >= READY_BARRIER_MIN for barrier in PRIORITY_BARRIERS)
    size_in_range = MIN_SUBSTRATE_SIZE <= size <= MAX_SUBSTRATE_SIZE
    family_breadth_ok = len([key for key, value in workflow_family_mix.items() if int(value) > 0]) >= 2
    complexity_breadth_ok = len([key for key, value in complexity_mix.items() if int(value) > 0]) >= 2
    template_breadth_ok = len([key for key, value in template_mix.items() if int(value) > 0]) >= 2
    provenance_counter = Counter(str(row.get("source_id") or "") for row in rows)
    provenance_explicit_ok = all(source_id.strip() and count > 0 for source_id, count in provenance_counter.items())
    governance_clean = len(admitted) == size

    if governance_clean and no_zero_barrier:
        admission_status = "PASS"
    else:
        admission_status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_expanded_substrate_admission",
        "generated_at_utc": now_utc(),
        "status": "PASS" if admission_status == "PASS" else "FAIL",
        "expanded_substrate_admission_status": admission_status,
        "expanded_substrate_size": size,
        "governance_pass_rate_pct": governance_pass_rate_pct,
        "priority_barrier_coverage_table": barrier_counts,
        "workflow_family_coverage_table": workflow_family_mix,
        "complexity_coverage_table": complexity_mix,
        "goal_specific_check_mode_coverage_table": builder.get("goal_specific_check_mode_mix"),
        "workflow_task_template_coverage_table": template_mix,
        "size_in_range": size_in_range,
        "family_breadth_ok": family_breadth_ok,
        "complexity_breadth_ok": complexity_breadth_ok,
        "template_breadth_ok": template_breadth_ok,
        "all_priority_barriers_at_least_five": all_barriers_ready,
        "no_zero_priority_barriers": no_zero_barrier,
        "provenance_explicit_ok": provenance_explicit_ok,
        "candidate_row_evaluations": evaluations,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.2 Expanded Substrate Admission",
                "",
                f"- expanded_substrate_admission_status: `{admission_status}`",
                f"- expanded_substrate_size: `{size}`",
                f"- priority_barrier_coverage_table: `{barrier_counts}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.2 expanded substrate admission artifact.")
    parser.add_argument("--expanded-substrate-builder", default=str(DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_EXPANDED_SUBSTRATE_ADMISSION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v092_expanded_substrate_admission(
        expanded_substrate_builder_path=str(args.expanded_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "expanded_substrate_admission_status": payload.get("expanded_substrate_admission_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
