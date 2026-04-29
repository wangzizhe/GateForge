from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "external_strategy_source_synthesis_v0_33_4"

DEFAULT_RUN_SPECS = [
    {
        "run_id": "strategy_source_run_01",
        "source_class": "high_level_strategy_source",
        "path": REPO_ROOT / "artifacts" / "external_strategy_source_probe_v0_33_1",
    },
    {
        "run_id": "strategy_source_run_02",
        "source_class": "high_level_strategy_source",
        "path": REPO_ROOT / "artifacts" / "external_strategy_source_probe_v0_33_1_repeat_run_02",
    },
    {
        "run_id": "worked_source_run_01",
        "source_class": "worked_strategy_source",
        "path": REPO_ROOT / "artifacts" / "worked_strategy_source_probe_v0_33_2_sem19",
    },
    {
        "run_id": "semantic_migration_run_01",
        "source_class": "library_semantic_strategy_source",
        "path": REPO_ROOT / "artifacts" / "library_semantic_migration_probe_v0_33_3_sem19",
    },
    {
        "run_id": "semantic_migration_run_02",
        "source_class": "library_semantic_strategy_source",
        "path": REPO_ROOT / "artifacts" / "library_semantic_migration_probe_v0_33_3_sem19_repeat_run_02",
    },
]


def _tool_counts(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            name = str(call.get("name") or "")
            if name:
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _run_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    root = Path(spec["path"])
    rows: list[dict[str, Any]] = []
    for row in load_jsonl(root / "results.jsonl"):
        rows.append(
            {
                "run_id": str(spec["run_id"]),
                "source_class": str(spec["source_class"]),
                "case_id": str(row.get("case_id") or ""),
                "final_verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "step_count": int(row.get("step_count") or 0),
                "tool_counts": _tool_counts(row),
                "provider_error": str(row.get("provider_error") or ""),
            }
        )
    return rows


def _case_source_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["case_id"]), str(row["source_class"]))
        grouped.setdefault(key, []).append(row)
    out: list[dict[str, Any]] = []
    for (case_id, source_class), group in sorted(grouped.items()):
        pass_count = sum(1 for row in group if row["final_verdict"] == "PASS")
        submit_count = sum(1 for row in group if row["submitted"])
        provider_error_count = sum(1 for row in group if row["provider_error"])
        tool_counts: dict[str, int] = {}
        for row in group:
            for name, count in row["tool_counts"].items():
                tool_counts[name] = tool_counts.get(name, 0) + int(count)
        out.append(
            {
                "case_id": case_id,
                "source_class": source_class,
                "run_count": len(group),
                "pass_count": pass_count,
                "submit_count": submit_count,
                "provider_error_count": provider_error_count,
                "tool_counts": dict(sorted(tool_counts.items())),
                "verdict": "positive_signal" if pass_count else "no_positive_signal",
            }
        )
    return out


def _derive_decision(case_source_rows: list[dict[str, Any]]) -> str:
    sem19_library = [
        row
        for row in case_source_rows
        if row["case_id"] == "sem_19_arrayed_shared_probe_bus"
        and row["source_class"] == "library_semantic_strategy_source"
    ]
    sem19_other = [
        row
        for row in case_source_rows
        if row["case_id"] == "sem_19_arrayed_shared_probe_bus"
        and row["source_class"] != "library_semantic_strategy_source"
    ]
    library_passes = sum(int(row["pass_count"]) for row in sem19_library)
    other_passes = sum(int(row["pass_count"]) for row in sem19_other)
    if library_passes >= 2 and other_passes == 0:
        return "strategy_source_specificity_changes_candidate_discovery"
    if any(int(row["pass_count"]) for row in case_source_rows):
        return "external_strategy_source_has_partial_positive_signal"
    return "external_strategy_source_synthesis_inconclusive"


def build_external_strategy_source_synthesis(
    *,
    run_specs: list[dict[str, Any]] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    specs = run_specs or DEFAULT_RUN_SPECS
    run_rows: list[dict[str, Any]] = []
    missing_runs: list[str] = []
    for spec in specs:
        root = Path(spec["path"])
        if not (root / "results.jsonl").exists():
            missing_runs.append(str(spec["run_id"]))
            continue
        run_rows.extend(_run_rows(spec))
    case_source_rows = _case_source_rows(run_rows)
    total_runs = len(run_rows)
    total_pass = sum(1 for row in run_rows if row["final_verdict"] == "PASS")
    summary = {
        "version": "v0.33.4",
        "status": "PASS" if total_runs and not missing_runs else "REVIEW",
        "analysis_scope": "external_strategy_source_synthesis",
        "run_case_count": total_runs,
        "pass_count": total_pass,
        "case_source_rows": case_source_rows,
        "missing_runs": missing_runs,
        "decision": _derive_decision(case_source_rows),
        "interpretation": (
            "External strategy context can change LLM candidate discovery when the strategy source matches "
            "the semantic boundary. This is not wrapper repair because the harness still only executes LLM "
            "tool calls and final submissions."
        ),
        "discipline": {
            "private_strategy_text_exported": False,
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
