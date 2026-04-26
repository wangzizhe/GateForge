from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_deepseek_frozen_harness_baseline_v0_27_0 import (
    DEFAULT_OUT_DIR as V0270_OUT_DIR,
    CheckFn,
    RepairFn,
    llm_repair_model_text,
    run_live_case,
    run_omc_check,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_ROWS = REPO_ROOT / "artifacts" / "substrate_manifest_v0_25_3" / "manifest_rows.jsonl"
DEFAULT_V0226_CANDIDATES = REPO_ROOT / "artifacts" / "single_point_complex_pack_v0_22_6" / "single_point_candidates.jsonl"
DEFAULT_V0228_ADMITTED = REPO_ROOT / "artifacts" / "single_point_family_screening_v0_22_8" / "admitted_cases.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "deepseek_source_backed_slice_v0_27_1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _by_candidate_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("candidate_id") or ""): row for row in rows if row.get("candidate_id")}


def resolve_source_backed_cases(
    *,
    manifest_rows_path: Path | None = None,
    v0226_candidates_path: Path | None = None,
    v0228_admitted_path: Path | None = None,
    split: str = "positive",
    limit: int = 3,
) -> list[dict[str, Any]]:
    manifest_rows_path = manifest_rows_path or DEFAULT_MANIFEST_ROWS
    v0226_candidates_path = v0226_candidates_path or DEFAULT_V0226_CANDIDATES
    v0228_admitted_path = v0228_admitted_path or DEFAULT_V0228_ADMITTED
    manifest_rows = load_jsonl(manifest_rows_path)
    v0226 = _by_candidate_id(load_jsonl(v0226_candidates_path))
    v0228 = _by_candidate_id(load_jsonl(v0228_admitted_path))
    resolved: list[dict[str, Any]] = []
    for manifest in manifest_rows:
        if str(manifest.get("split") or "") != split:
            continue
        candidate_id = str(manifest.get("candidate_id") or "")
        source_row = v0226.get(candidate_id) or v0228.get(candidate_id)
        if not source_row:
            continue
        model_path = Path(str(source_row.get("target_model_path") or source_row.get("mutated_model_path") or ""))
        source_model_path = Path(str(source_row.get("source_model_path") or ""))
        if not model_path.exists() or not source_model_path.exists():
            continue
        model_name = str(
            source_row.get("target_model_name")
            or source_row.get("source_model_name")
            or model_path.stem
        )
        resolved.append(
            {
                "case_id": candidate_id,
                "model_name": model_name,
                "failure_type": str(source_row.get("failure_type") or source_row.get("target_bucket_id") or "model_check_error"),
                "workflow_goal": str(
                    source_row.get("workflow_goal")
                    or "Repair the source-backed Modelica mutation using only model text and compiler feedback."
                ),
                "model_text": model_path.read_text(encoding="utf-8"),
                "mutation_family": str(manifest.get("mutation_family") or source_row.get("mutation_family") or ""),
                "split": str(manifest.get("split") or ""),
                "repeatability_class": str(manifest.get("repeatability_class") or ""),
                "source_model_path": str(source_model_path),
                "mutated_model_path": str(model_path),
                "source_backed": True,
                "workflow_proximal": True,
            }
        )
        if len(resolved) >= max(0, int(limit)):
            break
    return resolved


def run_deepseek_source_backed_slice(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    manifest_rows_path: Path | None = None,
    v0226_candidates_path: Path | None = None,
    v0228_admitted_path: Path | None = None,
    limit: int = 3,
    max_rounds: int = 2,
    planner_backend: str = "auto",
    check_fn: CheckFn = run_omc_check,
    repair_fn: RepairFn = llm_repair_model_text,
) -> dict[str, Any]:
    cases = resolve_source_backed_cases(
        manifest_rows_path=manifest_rows_path,
        v0226_candidates_path=v0226_candidates_path,
        v0228_admitted_path=v0228_admitted_path,
        limit=limit,
    )
    results = [
        run_live_case(
            case,
            max_rounds=max_rounds,
            planner_backend=planner_backend,
            check_fn=check_fn,
            repair_fn=repair_fn,
        )
        for case in cases
    ]
    pass_count = sum(1 for row in results if row.get("final_verdict") == "PASS")
    provider_errors = sum(1 for row in results if any(str(a.get("llm_error") or "") for a in row.get("attempts", [])))
    observation_error_count = sum(int(row.get("observation_validation_error_count") or 0) for row in results)
    true_multi_turn_count = sum(1 for row in results if row.get("true_multi_turn"))
    summary = {
        "version": "v0.27.1",
        "status": "PASS" if cases and observation_error_count == 0 else "REVIEW",
        "analysis_scope": "deepseek_source_backed_smoke_slice",
        "upstream_frozen_harness": str(V0270_OUT_DIR.relative_to(REPO_ROOT)),
        "provider": "deepseek",
        "model_profile": "deepseek-v4-flash",
        "run_mode": "raw_only",
        "case_count": len(results),
        "pass_count": pass_count,
        "provider_error_count": provider_errors,
        "observation_validation_error_count": observation_error_count,
        "true_multi_turn_count": true_multi_turn_count,
        "selected_case_ids": [str(case.get("case_id") or "") for case in cases],
        "selected_families": sorted({str(case.get("mutation_family") or "") for case in cases}),
        "sample_interpretation": "source_backed_smoke_slice_not_representative_benchmark",
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "deepseek_source_backed_slice_artifact_ready"
            if cases and observation_error_count == 0
            else "deepseek_source_backed_slice_needs_review"
        ),
        "next_focus": "review_source_backed_slice_before_expansion",
    }
    write_outputs(out_dir=out_dir, summary=summary, results=results)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    patched_dir = out_dir / "patched_models"
    patched_dir.mkdir(exist_ok=True)
    for row in results:
        (patched_dir / f"{row['case_id']}.mo").write_text(str(row.get("final_model_text") or ""), encoding="utf-8")
