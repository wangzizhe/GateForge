from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "neutral_benchmark_audit_v0_94_0"
DEFAULT_PATHS = (
    REPO_ROOT / "gateforge" / "agent_modelica_workspace_style_probe_v0_67_0.py",
    REPO_ROOT / "gateforge" / "agent_modelica_engineering_multifile_expansion_tasks_v0_92_2.py",
    REPO_ROOT / "gateforge" / "agent_modelica_engineering_multifile_baseline_tasks_v0_88_2.py",
)
DEFAULT_TASK_PATHS = (
    REPO_ROOT / "artifacts" / "engineering_baseline_tasks_v0_83_0" / "tasks.jsonl",
    REPO_ROOT / "artifacts" / "engineering_harder_baseline_tasks_v0_84_3" / "tasks.jsonl",
    REPO_ROOT / "artifacts" / "engineering_packaged_baseline_tasks_v0_86_3" / "tasks.jsonl",
    REPO_ROOT / "artifacts" / "engineering_multifile_baseline_tasks_v0_88_2" / "tasks.jsonl",
    REPO_ROOT / "artifacts" / "engineering_multifile_expansion_tasks_v0_92_2" / "tasks.jsonl",
)
VISIBLE_TASK_FIELDS = ("description", "constraints")


BANNED_VISIBLE_HINTS = (
    "p.i = 0",
    "n.i = 0",
    "zero-flow",
    "zero flow",
    "PositivePin",
    "NegativePin",
    "replace custom",
    "Common Modelica repair patterns",
    "Ohm's law",
    "fix those directly",
    "no exploration needed",
    "Focus on remaining deficit",
    "Combine effective changes",
    "equation balance summary",
    "structured diagnostics",
)


def audit_text(path: Path, *, banned_phrases: tuple[str, ...] = BANNED_VISIBLE_HINTS) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lower = text.lower()
    hits = [
        {
            "phrase": phrase,
            "count": lower.count(phrase.lower()),
        }
        for phrase in banned_phrases
        if phrase.lower() in lower
    ]
    return {
        "path": str(path),
        "exists": path.exists(),
        "hit_count": sum(int(hit["count"]) for hit in hits),
        "hits": hits,
        "status": "PASS" if path.exists() and not hits else "REVIEW",
    }


def _visible_task_text(row: dict[str, Any]) -> str:
    chunks: list[str] = []
    for field in VISIBLE_TASK_FIELDS:
        value = row.get(field)
        if isinstance(value, list):
            chunks.extend(str(item) for item in value)
        elif value is not None:
            chunks.append(str(value))
    return "\n".join(chunks)


def audit_task_jsonl(path: Path, *, banned_phrases: tuple[str, ...] = BANNED_VISIBLE_HINTS) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if path.exists():
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append({"line": index, "status": "REVIEW", "hits": [{"phrase": "invalid_json", "count": 1}]})
                continue
            text = _visible_task_text(row if isinstance(row, dict) else {})
            lower = text.lower()
            hits = [
                {"phrase": phrase, "count": lower.count(phrase.lower())}
                for phrase in banned_phrases
                if phrase.lower() in lower
            ]
            if hits:
                rows.append({
                    "line": index,
                    "case_id": str(row.get("case_id") or ""),
                    "status": "REVIEW",
                    "hits": hits,
                })
    return {
        "path": str(path),
        "exists": path.exists(),
        "visible_fields": list(VISIBLE_TASK_FIELDS),
        "review_row_count": len(rows),
        "status": "PASS" if path.exists() and not rows else "REVIEW",
        "review_rows": rows,
    }


def build_neutral_benchmark_audit(
    *,
    paths: tuple[Path, ...] = DEFAULT_PATHS,
    task_paths: tuple[Path, ...] = DEFAULT_TASK_PATHS,
    version: str = "v0.94.0",
) -> dict[str, Any]:
    rows = [audit_text(path) for path in paths]
    task_rows = [audit_task_jsonl(path) for path in task_paths if path.exists()]
    review = [row for row in rows if row["status"] != "PASS"]
    task_review = [row for row in task_rows if row["status"] != "PASS"]
    return {
        "version": version,
        "analysis_scope": "neutral_benchmark_prompt_and_task_audit",
        "status": "PASS" if rows and not review and not task_review else "REVIEW",
        "evidence_role": "formal_experiment",
        "artifact_complete": bool(rows),
        "conclusion_allowed": bool(rows and not review and not task_review),
        "audited_path_count": len(rows),
        "review_path_count": len(review),
        "audited_task_path_count": len(task_rows),
        "review_task_path_count": len(task_review),
        "visible_task_fields": list(VISIBLE_TASK_FIELDS),
        "banned_visible_hints": list(BANNED_VISIBLE_HINTS),
        "discipline": {
            "benchmark_profile": "neutral_benchmark",
            "product_repair_profile": "disabled_for_benchmark",
            "wrapper_auto_submit_added": False,
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
        },
        "results": rows,
        "task_results": task_rows,
    }


def run_neutral_benchmark_audit(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_neutral_benchmark_audit()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
