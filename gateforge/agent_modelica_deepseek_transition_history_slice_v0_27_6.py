from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_modelica_deepseek_source_backed_slice_v0_27_1 import (
    DEFAULT_MANIFEST_ROWS,
    DEFAULT_V0226_CANDIDATES,
    DEFAULT_V0228_ADMITTED,
    CheckFn,
    RepairFn,
    llm_repair_model_text,
    run_deepseek_source_backed_slice,
    run_omc_check,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "deepseek_transition_history_slice_v0_27_6"


def run_deepseek_transition_history_slice(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    manifest_rows_path: Path | None = None,
    v0226_candidates_path: Path | None = None,
    v0228_admitted_path: Path | None = None,
    limit: int = 3,
    max_rounds: int = 3,
    planner_backend: str = "auto",
    check_fn: CheckFn = run_omc_check,
    repair_fn: RepairFn = llm_repair_model_text,
) -> dict[str, Any]:
    summary = run_deepseek_source_backed_slice(
        out_dir=out_dir,
        manifest_rows_path=manifest_rows_path or DEFAULT_MANIFEST_ROWS,
        v0226_candidates_path=v0226_candidates_path or DEFAULT_V0226_CANDIDATES,
        v0228_admitted_path=v0228_admitted_path or DEFAULT_V0228_ADMITTED,
        limit=limit,
        max_rounds=max_rounds,
        planner_backend=planner_backend,
        check_fn=check_fn,
        repair_fn=repair_fn,
    )
    summary.update(
        {
            "version": "v0.27.6",
            "analysis_scope": "deepseek_transition_history_source_backed_slice",
            "max_rounds": int(max_rounds),
            "changed_variable": "repair_history_transition_contract",
            "comparison_baseline_artifact": "artifacts/deepseek_three_round_slice_v0_27_3/summary.json",
            "sample_interpretation": "same_slice_transition_history_probe_not_representative_benchmark",
            "decision": "deepseek_transition_history_slice_artifact_ready",
            "next_focus": "compare_transition_history_against_three_round_baseline",
        }
    )
    from .agent_modelica_deepseek_source_backed_slice_v0_27_1 import write_outputs

    import json

    results_path = out_dir / "results.jsonl"
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()] if results_path.exists() else []
    write_outputs(out_dir=out_dir, summary=summary, results=results)
    return summary
