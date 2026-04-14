from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_19_1_common import (
    BENCHMARK_MIN_CASES,
    DEFAULT_BENCHMARK_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_EMPIRICAL_OUT_DIR,
    DEFAULT_GENERATOR_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_PREVIEW_OUT_DIR,
    DEFAULT_V190_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    TARGET_MAX_TURNS,
    TURN1_SUCCESS_RATE_MAX,
    TURN1_SUCCESS_RATE_MIN,
    TURNN_SUCCESS_RATE_MAX,
    TURNN_SUCCESS_RATE_MIN,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_19_1_handoff_integrity import build_v191_handoff_integrity
from .composite_mutation_generator_v0_19_1 import build_composite_mutation_generator_v191
from .trajectory_preview_filter_v0_19_1 import build_trajectory_preview_filter_v191
from .empirical_difficulty_filter_v0_19_1 import build_empirical_difficulty_filter_v191


def build_v191_closeout(
    *,
    v190_closeout_path: str = str(DEFAULT_V190_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    generator_summary_path: str = str(DEFAULT_GENERATOR_OUT_DIR / "summary.json"),
    preview_summary_path: str = str(DEFAULT_PREVIEW_OUT_DIR / "summary.json"),
    empirical_summary_path: str = str(DEFAULT_EMPIRICAL_OUT_DIR / "summary.json"),
    benchmark_summary_path: str = str(DEFAULT_BENCHMARK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v191_handoff_integrity(v190_closeout_path=v190_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(generator_summary_path).exists():
        build_composite_mutation_generator_v191(out_dir=str(Path(generator_summary_path).parent))
    if not Path(preview_summary_path).exists():
        build_trajectory_preview_filter_v191(generator_summary_path=generator_summary_path, out_dir=str(Path(preview_summary_path).parent))
    if not Path(empirical_summary_path).exists() or not Path(benchmark_summary_path).exists():
        build_empirical_difficulty_filter_v191(
            preview_summary_path=preview_summary_path,
            empirical_out_dir=str(Path(empirical_summary_path).parent),
            benchmark_out_dir=str(Path(benchmark_summary_path).parent),
        )

    handoff = load_json(handoff_integrity_path)
    generator = load_json(generator_summary_path)
    preview = load_json(preview_summary_path)
    empirical = load_json(empirical_summary_path)
    benchmark = load_json(benchmark_summary_path)

    handoff_ok = handoff.get("handoff_integrity_status") == "PASS"
    generator_ok = generator.get("status") == "PASS" and int(generator.get("candidate_count") or 0) > 0
    preview_ok = preview.get("status") == "PASS" and int(preview.get("preview_pass_count") or 0) > 0
    empirical_ok = empirical.get("status") == "PASS" and str(empirical.get("frontier_agent_id") or "") != ""
    benchmark_gate_pass = (
        int(benchmark.get("benchmark_pass_count") or 0) >= BENCHMARK_MIN_CASES
        and TURN1_SUCCESS_RATE_MIN <= float(benchmark.get("turn_1_success_rate") or 0.0) <= TURN1_SUCCESS_RATE_MAX
        and TURNN_SUCCESS_RATE_MIN <= float(benchmark.get("turn_n_success_rate") or 0.0) <= TURNN_SUCCESS_RATE_MAX
    )

    if not handoff_ok or not generator_ok or not preview_ok or not empirical_ok:
        version_decision = "v0_19_1_foundation_inputs_invalid"
        status = "FAIL"
        handoff_mode = "rebuild_v0_19_1_from_valid_foundation_inputs"
    elif benchmark_gate_pass:
        version_decision = "v0_19_1_first_benchmark_batch_ready"
        status = "PASS"
        handoff_mode = "run_first_real_multiturn_trajectory_dataset"
    else:
        version_decision = "v0_19_1_benchmark_construction_partial"
        status = "PASS"
        handoff_mode = "repair_benchmark_construction_gaps_without_reopening_v0_19_0_foundation"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "frontier_agent_id": str(benchmark.get("frontier_agent_id") or empirical.get("frontier_agent_id") or ""),
            "candidate_count_total": int(benchmark.get("candidate_count_total") or 0),
            "preview_pass_count": int(benchmark.get("preview_pass_count") or 0),
            "benchmark_pass_count": int(benchmark.get("benchmark_pass_count") or 0),
            "turn_1_success_rate": float(benchmark.get("turn_1_success_rate") or 0.0),
            "turn_n_success_rate": float(benchmark.get("turn_n_success_rate") or 0.0),
            "difficulty_calibration_status": str(benchmark.get("difficulty_calibration_status") or ""),
            "target_max_turns": TARGET_MAX_TURNS,
            "v0_19_2_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "generator": generator,
        "preview": preview,
        "empirical": empirical,
        "benchmark": benchmark,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- benchmark_pass_count: `{payload['conclusion']['benchmark_pass_count']}`",
                f"- turn_1_success_rate: `{payload['conclusion']['turn_1_success_rate']}`",
                f"- turn_n_success_rate: `{payload['conclusion']['turn_n_success_rate']}`",
                f"- v0_19_2_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.1 benchmark construction closeout.")
    parser.add_argument("--v190-closeout", default=str(DEFAULT_V190_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--generator-summary", default=str(DEFAULT_GENERATOR_OUT_DIR / "summary.json"))
    parser.add_argument("--preview-summary", default=str(DEFAULT_PREVIEW_OUT_DIR / "summary.json"))
    parser.add_argument("--empirical-summary", default=str(DEFAULT_EMPIRICAL_OUT_DIR / "summary.json"))
    parser.add_argument("--benchmark-summary", default=str(DEFAULT_BENCHMARK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v191_closeout(
        v190_closeout_path=str(args.v190_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        generator_summary_path=str(args.generator_summary),
        preview_summary_path=str(args.preview_summary),
        empirical_summary_path=str(args.empirical_summary),
        benchmark_summary_path=str(args.benchmark_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload["status"], "version_decision": payload["conclusion"]["version_decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
