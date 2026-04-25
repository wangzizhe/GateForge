from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIT_PATH = REPO_ROOT / "artifacts" / "true_multiturn_audit_v0_22_2" / "case_audit.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "true_multiturn_pattern_study_v0_22_3"


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


def infer_mechanism(row: dict[str, Any]) -> str:
    candidate_id = str(row.get("candidate_id") or "")
    run_dir = str(row.get("run_dir") or "")
    sequence = [str(item) for item in (row.get("observed_error_sequence") or [])]
    if "measurement_abstraction_partial" in candidate_id and sequence == [
        "model_check_error",
        "constraint_violation",
        "none",
    ]:
        return "cross_layer_feedback_after_interface_repair"
    if "raw_only_triple" in run_dir or "triple_underdetermined" in run_dir:
        return "compound_residual_sequential_exposure"
    if "raw_only_underdetermined" in run_dir:
        return "double_residual_sequential_exposure"
    return "other_true_multi_repair"


def build_pattern_rows(audit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in audit_rows:
        if row.get("sample_quality") != "true_multi_repair_pass":
            continue
        pattern_row = {
            "candidate_id": row.get("candidate_id"),
            "run_dir": row.get("run_dir"),
            "repair_round_count": row.get("repair_round_count"),
            "n_turns": row.get("n_turns"),
            "observed_error_sequence": row.get("observed_error_sequence"),
            "mechanism": infer_mechanism(row),
        }
        rows.append(pattern_row)
    return rows


def summarize_patterns(pattern_rows: list[dict[str, Any]], audit_rows: list[dict[str, Any]]) -> dict[str, Any]:
    mechanism_counts = Counter(str(row.get("mechanism") or "") for row in pattern_rows)
    sequence_counts = Counter("->".join(str(x) for x in (row.get("observed_error_sequence") or [])) for row in pattern_rows)
    false_multiturn = [row for row in audit_rows if row.get("false_multiturn_by_attempt_count")]
    recommended_principles = [
        "Require at least two independently repairable residuals in one workflow-proximal mutation.",
        "The first repair should reduce, not eliminate, the structural deficit.",
        "A high-value case should expose a second feedback surface after the first patch.",
        "Accept same bucket feedback only if equation/variable deficit or named residuals shrink between rounds.",
        "Reject single repair then validate cases from true multi-turn benchmark construction.",
    ]
    next_mutation_families = [
        "staged_parameter_and_phantom_residual",
        "measurement_interface_then_behavioral_constraint_residual",
        "compound_structural_deficit_with_residual_symbol_exposure",
    ]
    return {
        "version": "v0.22.3",
        "status": "PASS" if pattern_rows else "REVIEW",
        "analysis_scope": "true_multiturn_pattern_study_no_repair_logic",
        "true_multi_case_count": len(pattern_rows),
        "false_multiturn_case_count": len(false_multiturn),
        "mechanism_counts": dict(sorted(mechanism_counts.items())),
        "sequence_counts": dict(sorted(sequence_counts.items())),
        "recommended_construction_principles": recommended_principles,
        "next_mutation_families": next_mutation_families,
        "discipline": "analysis_only_no_deterministic_repair_no_routing_no_hint",
        "conclusion": (
            "true_multiturn_construction_principles_identified"
            if pattern_rows
            else "true_multiturn_pattern_study_needs_audit_rows"
        ),
    }


def render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# v0.22.3 True Multi-Turn Pattern Study",
        "",
        f"- status: `{summary.get('status')}`",
        f"- true_multi_case_count: `{summary.get('true_multi_case_count')}`",
        f"- false_multiturn_case_count: `{summary.get('false_multiturn_case_count')}`",
        "",
        "## Mechanisms",
    ]
    for key, count in (summary.get("mechanism_counts") or {}).items():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Construction Principles"])
    for item in summary.get("recommended_construction_principles") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Candidate Families"])
    for item in summary.get("next_mutation_families") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## True Multi-Turn Cases"])
    for row in rows:
        lines.append(
            "- `{candidate_id}` mechanism=`{mechanism}` repairs=`{repairs}` sequence=`{sequence}`".format(
                candidate_id=row.get("candidate_id"),
                mechanism=row.get("mechanism"),
                repairs=row.get("repair_round_count"),
                sequence="->".join(str(x) for x in (row.get("observed_error_sequence") or [])),
            )
        )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, pattern_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "true_multiturn_patterns.jsonl").open("w", encoding="utf-8") as fh:
        for row in pattern_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "REPORT.md").write_text(render_report(summary, pattern_rows), encoding="utf-8")


def run_true_multiturn_pattern_study(
    *,
    audit_path: Path = DEFAULT_AUDIT_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    audit_rows = load_jsonl(audit_path)
    pattern_rows = build_pattern_rows(audit_rows)
    summary = summarize_patterns(pattern_rows, audit_rows)
    write_outputs(out_dir, pattern_rows, summary)
    return summary
