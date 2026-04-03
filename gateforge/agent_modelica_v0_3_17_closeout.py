from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_17_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_VERSION = "agent_modelica_v0_3_17_closeout"
DEFAULT_PROMPT_PACK = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_prompt_pack_current" / "summary.json"
DEFAULT_GENERATION_CENSUS = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_census_current" / "summary.json"
DEFAULT_ONE_STEP_REPAIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_one_step_live_repair_current" / "summary.json"
DEFAULT_ANALYSIS = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_distribution_analysis_current" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_closeout_current"


def build_v0317_closeout(
    *,
    prompt_pack_path: str = str(DEFAULT_PROMPT_PACK),
    generation_census_path: str = str(DEFAULT_GENERATION_CENSUS),
    one_step_repair_path: str = str(DEFAULT_ONE_STEP_REPAIR),
    analysis_path: str = str(DEFAULT_ANALYSIS),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    prompt_pack = load_json(prompt_pack_path)
    generation = load_json(generation_census_path)
    one_step = load_json(one_step_repair_path)
    analysis = load_json(analysis_path)
    decision = str(analysis.get("version_decision") or "distribution_alignment_not_supported")
    second_overall = (analysis.get("second_residual_report") or {}).get("overall") if isinstance(analysis.get("second_residual_report"), dict) else {}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": decision.upper(),
        "prompt_pack": {
            "status": prompt_pack.get("status"),
            "total_active_count": prompt_pack.get("total_active_count"),
            "total_reserve_count": prompt_pack.get("total_reserve_count"),
        },
        "generation_census": {
            "status": generation.get("status"),
            "final_task_count": generation.get("final_task_count"),
            "repair_eligible_task_count": generation.get("repair_eligible_task_count"),
            "reserve_used_count": generation.get("reserve_used_count"),
        },
        "one_step_repair": {
            "status": one_step.get("status"),
            "task_count": one_step.get("task_count"),
            "immediate_pass_count": one_step.get("immediate_pass_count"),
            "terminal_death_count": one_step.get("terminal_death_count"),
        },
        "distribution_analysis": {
            "status": analysis.get("status"),
            "version_decision": decision,
            "first_failure_report": analysis.get("first_failure_report"),
            "second_residual_report": analysis.get("second_residual_report"),
        },
        "conclusion": {
            "version_decision": decision,
            "primary_bottleneck": (
                "synthetic_to_generation_overlap_low"
                if decision == "distribution_alignment_not_supported"
                else "coverage_shift_requires_family_expansion"
                if decision == "distribution_alignment_partial"
                else "alignment_supports_continued_repair_mainline"
            ),
            "summary": (
                "The frozen generation-to-repair slice supports the current synthetic repair mainline strongly enough to justify continued investment."
                if decision == "distribution_alignment_supported"
                else "The generation-to-repair slice overlaps only partially with the current synthetic repair mainline, so follow-on work should expand family coverage before over-investing in replay."
                if decision == "distribution_alignment_partial"
                else "The generation-to-repair slice does not overlap strongly enough with the current synthetic repair mainline, so mutation-family expansion should come before more replay-focused versions."
            ),
            "second_residual_synthetic_overlap_pct": ((second_overall or {}).get("synthetic_family_overlap") or {}).get("matched_rate_pct"),
            "second_residual_replay_overlap_pct": ((second_overall or {}).get("replay_keyspace_overlap") or {}).get("matched_rate_pct"),
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.17 Closeout",
                "",
                f"- status: `{payload.get('status')}`",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{decision}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.17 closeout artifact.")
    parser.add_argument("--prompt-pack", default=str(DEFAULT_PROMPT_PACK))
    parser.add_argument("--generation-census", default=str(DEFAULT_GENERATION_CENSUS))
    parser.add_argument("--one-step-repair", default=str(DEFAULT_ONE_STEP_REPAIR))
    parser.add_argument("--analysis", default=str(DEFAULT_ANALYSIS))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0317_closeout(
        prompt_pack_path=str(args.prompt_pack),
        generation_census_path=str(args.generation_census),
        one_step_repair_path=str(args.one_step_repair),
        analysis_path=str(args.analysis),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": payload.get("conclusion", {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
