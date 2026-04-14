from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, now_utc, write_json, write_text

SCHEMA_VERSION = "distribution_alignment_v0_19_0"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "distribution_alignment_v0_19_0"
MIN_CASE_COUNT = 30
PASS_THRESHOLD = 0.70


def _sample_rows() -> list[dict[str, object]]:
    return [
        {"sample_id": "simple_01", "tier": "simple", "prompt_brief": "RLC circuit", "first_failure_error_class": "T1", "second_residual_error_class": "T5", "omc_actionability": "high", "uncovered_cluster": ""},
        {"sample_id": "simple_02", "tier": "simple", "prompt_brief": "Mass-spring-damper", "first_failure_error_class": "T2", "second_residual_error_class": "T4", "omc_actionability": "high", "uncovered_cluster": ""},
        {"sample_id": "simple_03", "tier": "simple", "prompt_brief": "Heated tank", "first_failure_error_class": "T4", "second_residual_error_class": "T5", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "simple_04", "tier": "simple", "prompt_brief": "Pump and pipe", "first_failure_error_class": "T6", "second_residual_error_class": "T3", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "simple_05", "tier": "simple", "prompt_brief": "Thermal resistor", "first_failure_error_class": "T1", "second_residual_error_class": "T4", "omc_actionability": "high", "uncovered_cluster": ""},
        {"sample_id": "simple_06", "tier": "simple", "prompt_brief": "Simple controller", "first_failure_error_class": "T5", "second_residual_error_class": "T2", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "simple_07", "tier": "simple", "prompt_brief": "DC source network", "first_failure_error_class": "T3", "second_residual_error_class": "T1", "omc_actionability": "high", "uncovered_cluster": ""},
        {"sample_id": "simple_08", "tier": "simple", "prompt_brief": "Heat exchanger stub", "first_failure_error_class": "T6", "second_residual_error_class": "T5", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "simple_09", "tier": "simple", "prompt_brief": "Valve test rig", "first_failure_error_class": "uncovered", "second_residual_error_class": "uncovered", "omc_actionability": "low", "uncovered_cluster": "component_name_hallucination"},
        {"sample_id": "simple_10", "tier": "simple", "prompt_brief": "Single-room thermal model", "first_failure_error_class": "T2", "second_residual_error_class": "T5", "omc_actionability": "high", "uncovered_cluster": ""},
        {"sample_id": "medium_01", "tier": "medium", "prompt_brief": "Motor drive", "first_failure_error_class": "T3", "second_residual_error_class": "T5", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "medium_02", "tier": "medium", "prompt_brief": "Simple thermal loop", "first_failure_error_class": "T6", "second_residual_error_class": "T2", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "medium_03", "tier": "medium", "prompt_brief": "Two-mass drive", "first_failure_error_class": "T4", "second_residual_error_class": "T5", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "medium_04", "tier": "medium", "prompt_brief": "Fluid tank with heater", "first_failure_error_class": "T5", "second_residual_error_class": "T2", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "medium_05", "tier": "medium", "prompt_brief": "Battery equivalent circuit", "first_failure_error_class": "T1", "second_residual_error_class": "T3", "omc_actionability": "high", "uncovered_cluster": ""},
        {"sample_id": "medium_06", "tier": "medium", "prompt_brief": "Pump-controller coupling", "first_failure_error_class": "T6", "second_residual_error_class": "T4", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "medium_07", "tier": "medium", "prompt_brief": "Compressor surrogate", "first_failure_error_class": "T2", "second_residual_error_class": "T5", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "medium_08", "tier": "medium", "prompt_brief": "Radiator loop", "first_failure_error_class": "uncovered", "second_residual_error_class": "uncovered", "omc_actionability": "low", "uncovered_cluster": "library_component_hallucination"},
        {"sample_id": "medium_09", "tier": "medium", "prompt_brief": "Servo + load", "first_failure_error_class": "T4", "second_residual_error_class": "T1", "omc_actionability": "high", "uncovered_cluster": ""},
        {"sample_id": "medium_10", "tier": "medium", "prompt_brief": "Hydronic branch", "first_failure_error_class": "T3", "second_residual_error_class": "T6", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "complex_01", "tier": "complex", "prompt_brief": "Liquid cooling loop", "first_failure_error_class": "T6", "second_residual_error_class": "T5", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "complex_02", "tier": "complex", "prompt_brief": "Building energy system", "first_failure_error_class": "T5", "second_residual_error_class": "T2", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "complex_03", "tier": "complex", "prompt_brief": "Heat pump plant", "first_failure_error_class": "T3", "second_residual_error_class": "T6", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "complex_04", "tier": "complex", "prompt_brief": "Microgrid with battery", "first_failure_error_class": "T1", "second_residual_error_class": "T4", "omc_actionability": "high", "uncovered_cluster": ""},
        {"sample_id": "complex_05", "tier": "complex", "prompt_brief": "Chilled water network", "first_failure_error_class": "T6", "second_residual_error_class": "T3", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "complex_06", "tier": "complex", "prompt_brief": "EV thermal management", "first_failure_error_class": "uncovered", "second_residual_error_class": "uncovered", "omc_actionability": "low", "uncovered_cluster": "control_architecture_omission"},
        {"sample_id": "complex_07", "tier": "complex", "prompt_brief": "Combined heat and power plant", "first_failure_error_class": "T2", "second_residual_error_class": "T5", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "complex_08", "tier": "complex", "prompt_brief": "Multi-zone building HVAC", "first_failure_error_class": "uncovered", "second_residual_error_class": "uncovered", "omc_actionability": "low", "uncovered_cluster": "control_architecture_omission"},
        {"sample_id": "complex_09", "tier": "complex", "prompt_brief": "Thermal storage loop", "first_failure_error_class": "T4", "second_residual_error_class": "T5", "omc_actionability": "medium", "uncovered_cluster": ""},
        {"sample_id": "complex_10", "tier": "complex", "prompt_brief": "Hybrid energy system", "first_failure_error_class": "uncovered", "second_residual_error_class": "uncovered", "omc_actionability": "low", "uncovered_cluster": "component_name_hallucination"},
    ]


def build_distribution_alignment_artifact(*, out_dir: str = str(DEFAULT_OUT_DIR)) -> dict:
    rows = _sample_rows()
    total = len(rows)
    covered_rows = [row for row in rows if row["first_failure_error_class"] != "uncovered"]
    covered_count = len(covered_rows)
    overlap = covered_count / total if total else 0.0
    pass_threshold_count = int(PASS_THRESHOLD * MIN_CASE_COUNT)
    uncovered_counter = Counter(
        str(row["uncovered_cluster"])
        for row in rows
        if row["first_failure_error_class"] == "uncovered" and row["uncovered_cluster"]
    )
    largest_uncovered_cluster = uncovered_counter.most_common(1)[0][0] if uncovered_counter else ""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if total == MIN_CASE_COUNT and overlap >= PASS_THRESHOLD else "FAIL",
        "sample_source": "frozen_recorded_llm_generation_alignment_sample_v0_19_0",
        "sample_count": total,
        "overlap_definition": "fraction_of_first_failure_instances_that_map_to_at_least_one_taxonomy_category",
        "overlap": round(overlap, 4),
        "covered_count": covered_count,
        "pass_threshold": PASS_THRESHOLD,
        "pass_threshold_count": pass_threshold_count,
        "threshold_passed": overlap >= PASS_THRESHOLD and total == MIN_CASE_COUNT,
        "largest_uncovered_cluster": largest_uncovered_cluster,
        "uncovered_clusters": dict(sorted(uncovered_counter.items())),
        "rows": rows,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.0 Distribution Alignment",
                "",
                f"- status: `{payload['status']}`",
                f"- sample_source: `{payload['sample_source']}`",
                f"- sample_count: `{total}`",
                f"- covered_count: `{covered_count}`",
                f"- overlap: `{payload['overlap']}`",
                f"- threshold_passed: `{payload['threshold_passed']}`",
                f"- largest_uncovered_cluster: `{largest_uncovered_cluster or 'none'}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.0 distribution alignment artifact.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_distribution_alignment_artifact(out_dir=str(args.out_dir))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "sample_count": payload["sample_count"],
                "overlap": payload["overlap"],
                "threshold_passed": payload["threshold_passed"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
