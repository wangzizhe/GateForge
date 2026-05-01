from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "strategy_memory_granularity_v0_33_8"

DEFAULT_RUN_SPECS = [
    {
        "run_id": "high_level_sem19_sem20_run_01",
        "granularity": "broad_strategy_note",
        "path": REPO_ROOT / "artifacts" / "external_strategy_source_probe_v0_33_1",
    },
    {
        "run_id": "high_level_sem19_sem20_run_02",
        "granularity": "broad_strategy_note",
        "path": REPO_ROOT / "artifacts" / "external_strategy_source_probe_v0_33_1_repeat_run_02",
    },
    {
        "run_id": "worked_sem19_run_01",
        "granularity": "worked_strategy_note",
        "path": REPO_ROOT / "artifacts" / "worked_strategy_source_probe_v0_33_2_sem19",
    },
    {
        "run_id": "semantic_specific_sem19_run_01",
        "granularity": "semantic_specific_strategy_source",
        "path": REPO_ROOT / "artifacts" / "library_semantic_migration_probe_v0_33_3_sem19",
    },
    {
        "run_id": "semantic_specific_sem19_run_02",
        "granularity": "semantic_specific_strategy_source",
        "path": REPO_ROOT / "artifacts" / "library_semantic_migration_probe_v0_33_3_sem19_repeat_run_02",
    },
    {
        "run_id": "generic_cards_sem13_sem19_sem20",
        "granularity": "generic_strategy_cards",
        "path": REPO_ROOT / "artifacts" / "semantic_strategy_cards_live_probe_v0_33_5",
    },
    {
        "run_id": "generic_cards_sem20_retry",
        "granularity": "generic_strategy_cards",
        "path": REPO_ROOT / "artifacts" / "semantic_strategy_cards_submit_budget_probe_v0_33_7_sem20_retry_02",
    },
]


def _model_texts(row: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            text = str(args.get("model_text") or "")
            if text.strip() and text not in seen:
                texts.append(text)
                seen.add(text)
    return texts


def _strategy_signals(texts: list[str]) -> dict[str, Any]:
    joined = "\n".join(texts)
    standard_library = bool(re.search(r"\bModelica\.Electrical\.Analog\.", joined))
    direct_flow = bool(re.search(r"\.[A-Za-z_][A-Za-z0-9_\[\].]*\.i\s*=", joined))
    flow_balance = bool(re.search(r"\.[A-Za-z_][A-Za-z0-9_\[\].]*\.i\s*\+", joined))
    one_sided_zero_flow = bool(re.search(r"\bp\[[^\]]+\]\.i\s*=\s*0\b", joined) or re.search(r"\bhigh\[[^\]]+\]\.i\s*=\s*0\b", joined))
    output_preserved = bool(re.search(r"\breadings\s*\[", joined) or "yTotal" in joined)
    return {
        "standard_library_migration_attempted": standard_library,
        "direct_flow_equation_attempted": direct_flow,
        "flow_balance_equation_attempted": flow_balance,
        "one_sided_zero_flow_attempted": one_sided_zero_flow,
        "required_output_mentions_seen": output_preserved,
    }


def _success_seen(row: dict[str, Any]) -> bool:
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for result in step.get("tool_results", []):
            if not isinstance(result, dict):
                continue
            if result.get("name") in {"check_model", "simulate_model"} and 'resultFile = "/workspace/' in str(result.get("result") or ""):
                return True
    return False


def _run_case_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in load_jsonl(Path(spec["path"]) / "results.jsonl"):
        texts = _model_texts(row)
        rows.append(
            {
                "run_id": str(spec["run_id"]),
                "granularity": str(spec["granularity"]),
                "case_id": str(row.get("case_id") or ""),
                "final_verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "provider_error": str(row.get("provider_error") or ""),
                "token_used": int(row.get("token_used") or 0),
                "step_count": int(row.get("step_count") or 0),
                "candidate_count": len(texts),
                "success_candidate_seen": _success_seen(row),
                "strategy_signals": _strategy_signals(texts),
            }
        )
    return rows


def _granularity_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["granularity"]), []).append(row)
    out: list[dict[str, Any]] = []
    for granularity, group in sorted(grouped.items()):
        pass_count = sum(1 for row in group if row["final_verdict"] == "PASS")
        success_seen_count = sum(1 for row in group if row["success_candidate_seen"])
        provider_error_count = sum(1 for row in group if row["provider_error"])
        signal_counts: dict[str, int] = {}
        for row in group:
            for key, value in row["strategy_signals"].items():
                if value:
                    signal_counts[key] = signal_counts.get(key, 0) + 1
        out.append(
            {
                "granularity": granularity,
                "run_case_count": len(group),
                "pass_count": pass_count,
                "success_candidate_seen_count": success_seen_count,
                "provider_error_count": provider_error_count,
                "signal_counts": dict(sorted(signal_counts.items())),
                "cases": sorted({str(row["case_id"]) for row in group}),
            }
        )
    return out


def _derive_decision(rows: list[dict[str, Any]]) -> str:
    sem19 = [row for row in rows if row["case_id"] == "sem_19_arrayed_shared_probe_bus"]
    specific_pass = sum(1 for row in sem19 if row["granularity"] == "semantic_specific_strategy_source" and row["final_verdict"] == "PASS")
    generic_pass = sum(1 for row in sem19 if row["granularity"] == "generic_strategy_cards" and row["final_verdict"] == "PASS")
    broad_pass = sum(1 for row in sem19 if row["granularity"] in {"broad_strategy_note", "worked_strategy_note"} and row["final_verdict"] == "PASS")
    if specific_pass >= 2 and not generic_pass and not broad_pass:
        return "semantic_memory_needs_boundary_specific_granularity"
    if specific_pass or generic_pass or broad_pass:
        return "strategy_memory_granularity_has_partial_signal"
    return "strategy_memory_granularity_inconclusive"


def build_strategy_memory_granularity(
    *,
    run_specs: list[dict[str, Any]] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    specs = run_specs or DEFAULT_RUN_SPECS
    missing_runs: list[str] = []
    rows: list[dict[str, Any]] = []
    for spec in specs:
        if not (Path(spec["path"]) / "results.jsonl").exists():
            missing_runs.append(str(spec["run_id"]))
            continue
        rows.extend(_run_case_rows(spec))
    summary = {
        "version": "v0.33.8",
        "status": "PASS" if rows and not missing_runs else "REVIEW",
        "analysis_scope": "strategy_memory_granularity",
        "run_case_count": len(rows),
        "missing_runs": missing_runs,
        "granularity_rows": _granularity_rows(rows),
        "case_rows": rows,
        "decision": _derive_decision(rows),
        "discipline": {
            "private_context_text_exported": False,
            "deterministic_repair_added": False,
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
