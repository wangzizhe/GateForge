from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ATTRIBUTION = REPO_ROOT / "artifacts" / "external_agent_attribution_v0_62_0" / "summary.json"
DEFAULT_SUBMIT_SLICE = REPO_ROOT / "artifacts" / "solvable_holdout_submit_checkpoint_probe_v0_63_0"
DEFAULT_REMAINING_SLICE = REPO_ROOT / "artifacts" / "solvable_holdout_submit_checkpoint_probe_v0_63_1"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "submit_checkpoint_probe_summary_v0_63_0"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _summary_for_probe_dir(path: Path) -> dict[str, Any]:
    summary = load_json(path / "summary.json")
    rows = load_jsonl(path / "results.jsonl")
    return {
        "path": str(path),
        "artifact_complete": bool(summary.get("artifact_complete")),
        "case_count": int(summary.get("case_count") or 0),
        "completed_case_count": int(summary.get("completed_case_count") or len(rows)),
        "pass_count": int(summary.get("pass_count") or 0),
        "fail_count": int(summary.get("fail_count") or 0),
        "provider_error_count": int(summary.get("provider_error_count") or 0),
        "case_ids": list(summary.get("case_ids") or []),
        "completed_case_ids": list(summary.get("completed_case_ids") or [row.get("case_id") for row in rows]),
        "pass_case_ids": list(summary.get("pass_case_ids") or []),
        "fail_case_ids": list(summary.get("fail_case_ids") or []),
        "tool_profile": str(summary.get("tool_profile") or ""),
    }


def build_submit_checkpoint_probe_summary(
    *,
    attribution_summary: dict[str, Any],
    submit_slice: dict[str, Any],
    remaining_slice: dict[str, Any],
    version: str = "v0.63.0",
) -> dict[str, Any]:
    attribution_counts = dict(attribution_summary.get("gateforge_failure_attribution_counts") or {})
    submit_failure_count = int(attribution_counts.get("successful_candidate_not_submitted") or 0)
    submit_slice_pass = int(submit_slice.get("pass_count") or 0)
    submit_slice_completed = int(submit_slice.get("completed_case_count") or 0)
    remaining_completed = int(remaining_slice.get("completed_case_count") or 0)
    remaining_pass = int(remaining_slice.get("pass_count") or 0)
    remaining_complete = bool(remaining_slice.get("artifact_complete"))
    return {
        "version": version,
        "analysis_scope": "submit_checkpoint_probe_summary",
        "evidence_role": "formal_experiment",
        "artifact_complete": bool(submit_slice.get("artifact_complete")) and remaining_completed > 0,
        "provider_status": "provider_stable"
        if int(submit_slice.get("provider_error_count") or 0) == 0
        and int(remaining_slice.get("provider_error_count") or 0) == 0
        else "provider_unstable",
        "conclusion_allowed": bool(submit_slice.get("artifact_complete")) and remaining_completed > 0,
        "source_attribution_counts": attribution_counts,
        "submit_failure_slice_case_count": submit_failure_count,
        "submit_failure_slice_completed_count": submit_slice_completed,
        "submit_failure_slice_pass_count": submit_slice_pass,
        "submit_failure_slice_recovered": bool(
            submit_failure_count > 0
            and submit_slice_completed == submit_failure_count
            and submit_slice_pass == submit_failure_count
        ),
        "remaining_candidate_slice_case_count": len(
            [
                row
                for row in attribution_summary.get("paired_rows", [])
                if row.get("paired_outcome") == "gateforge_fail_external_pass"
                and row.get("gateforge_failure_attribution")
                != "successful_candidate_not_submitted"
            ]
        ),
        "remaining_probe_completed_count": remaining_completed,
        "remaining_probe_pass_count": remaining_pass,
        "remaining_probe_partial": not remaining_complete,
        "submit_slice": submit_slice,
        "remaining_slice": remaining_slice,
        "decision": (
            "promote_transparent_submit_checkpoint_for_submit_failure_slice_only"
            if submit_slice_pass == submit_failure_count and submit_failure_count > 0
            else "do_not_promote"
        ),
        "next_direction": (
            "study_workspace_style_candidate_generation_for_remaining_semantic_slice"
            if remaining_pass < int(remaining_slice.get("case_count") or 0)
            else "rerun_full_remaining_slice_before_claiming_candidate_improvement"
        ),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "wrapper_auto_submit_added": False,
        },
    }


def run_submit_checkpoint_probe_summary(
    *,
    attribution_path: Path = DEFAULT_ATTRIBUTION,
    submit_slice_dir: Path = DEFAULT_SUBMIT_SLICE,
    remaining_slice_dir: Path = DEFAULT_REMAINING_SLICE,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_submit_checkpoint_probe_summary(
        attribution_summary=load_json(attribution_path),
        submit_slice=_summary_for_probe_dir(submit_slice_dir),
        remaining_slice=_summary_for_probe_dir(remaining_slice_dir),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
