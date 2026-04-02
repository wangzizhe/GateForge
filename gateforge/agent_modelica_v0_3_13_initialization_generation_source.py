from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_initialization_generation_source"
DEFAULT_AUDIT_SUMMARY = "artifacts/agent_modelica_v0_3_13_v0_3_5_audit_current/summary.json"
DEFAULT_CANDIDATE_DIR = "artifacts/agent_modelica_block_a_dual_layer_candidates_v0_3_5"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_initialization_generation_source"
FAMILY_ID = "surface_cleanup_then_initialization_parameter_recovery"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _audit_rows(payload: dict) -> list[dict]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and _norm(row.get("residual_signal_cluster_id")) == "initialization_parameter_recovery"
    ]


def _candidate_payload(candidate_dir: str | Path, task_id: str) -> dict:
    return _load_json(Path(candidate_dir) / f"{task_id}.json")


def _recover_clean_source_text(candidate: dict) -> str:
    text = _norm(candidate.get("source_model_text"))
    mutations = (((candidate.get("mutation_spec") or {}).get("hidden_base") or {}).get("audit") or {}).get("mutations")
    rows = [row for row in mutations if isinstance(row, dict)] if isinstance(mutations, list) else []
    lines = text.splitlines()
    for row in sorted(rows, key=lambda item: int(item.get("line_index") or 0), reverse=True):
        index = int(row.get("line_index") or -1)
        original_rhs = _norm(row.get("original_rhs"))
        lhs = _norm(row.get("lhs"))
        if index < 0 or index >= len(lines):
            continue
        line = lines[index]
        match = re.match(rf"^(\s*{re.escape(lhs)}\s*=\s*).+?(;\s*)$", line)
        if match:
            lines[index] = f"{match.group(1)}{original_rhs}{match.group(2)}"
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _initial_equation_targets(model_text: str) -> list[dict]:
    init_eq_start = re.compile(r"^\s*initial\s+equation\b", re.IGNORECASE)
    eq_assignment = re.compile(r"^(\s*)(\w[\w.]*(?:\([^)]*\))?)\s*=\s*(.+?);\s*$")
    section_end = re.compile(r"^\s*(equation|algorithm|protected|public|end\s+\w+)\b", re.IGNORECASE)
    lines = model_text.splitlines()
    in_init = False
    targets: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if init_eq_start.match(stripped):
            in_init = True
            continue
        if in_init:
            if section_end.match(stripped) and not init_eq_start.match(stripped):
                in_init = False
                continue
            m = eq_assignment.match(line)
            if not m:
                continue
            targets.append(
                {
                    "lhs": _norm(m.group(2)),
                    "rhs": _norm(m.group(3)),
                    "line_index": i,
                }
            )
    return targets


def _target_statuses(*, known_good_lhs: str, targets: list[dict]) -> list[dict]:
    rows = []
    for row in targets:
        lhs = _norm(row.get("lhs"))
        rows.append(
            {
                "lhs": lhs,
                "rhs": _norm(row.get("rhs")),
                "line_index": int(row.get("line_index") or 0),
                "status": "validated_initialization_seed" if lhs == known_good_lhs else "requires_preview",
            }
        )
    return rows


def build_initialization_generation_source(
    *,
    audit_summary_path: str = DEFAULT_AUDIT_SUMMARY,
    candidate_dir: str = DEFAULT_CANDIDATE_DIR,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    audit_summary = _load_json(audit_summary_path)
    sources = []
    for audit_row in _audit_rows(audit_summary):
        task_id = _norm(audit_row.get("task_id"))
        candidate = _candidate_payload(candidate_dir, task_id)
        if not candidate:
            continue
        clean_source_text = _recover_clean_source_text(candidate)
        targets = _initial_equation_targets(clean_source_text)
        known_good_lhs = _norm(((candidate.get("mutation_spec") or {}).get("hidden_base") or {}).get("audit", {}).get("mutations", [{}])[0].get("lhs"))
        sources.append(
            {
                "source_task_id": task_id,
                "model_hint": _norm(candidate.get("model_hint")),
                "source_model_path": _norm(candidate.get("source_model_path")),
                "source_library": _norm(candidate.get("source_library")),
                "clean_model_text": clean_source_text,
                "allowed_hidden_base_operator": _norm(candidate.get("hidden_base_operator")),
                "known_good_lhs": known_good_lhs,
                "initial_equation_targets": targets,
                "target_statuses": _target_statuses(known_good_lhs=known_good_lhs, targets=targets),
                "evidence": {
                    "masking_pattern": _norm(audit_row.get("masking_pattern")),
                    "surface_rule_id": _norm(audit_row.get("surface_rule_id")),
                    "first_attempt_stage_subtype": _norm(audit_row.get("first_attempt_stage_subtype")),
                    "second_attempt_stage_subtype": _norm(audit_row.get("second_attempt_stage_subtype")),
                    "resolution_path": _norm(audit_row.get("resolution_path")),
                    "rounds_used": int(audit_row.get("rounds_used") or 0),
                },
            }
        )

    target_status_counts: dict[str, int] = {}
    preview_queue = []
    for source in sources:
        for row in source.get("target_statuses") or []:
            if not isinstance(row, dict):
                continue
            status = _norm(row.get("status")) or "unknown"
            target_status_counts[status] = target_status_counts.get(status, 0) + 1
            if status == "requires_preview":
                preview_queue.append(
                    {
                        "source_task_id": _norm(source.get("source_task_id")),
                        "lhs": _norm(row.get("lhs")),
                    }
                )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if sources else "EMPTY",
        "family_id": FAMILY_ID,
        "audit_summary_path": str(Path(audit_summary_path).resolve()) if Path(audit_summary_path).exists() else str(audit_summary_path),
        "candidate_dir": str(Path(candidate_dir).resolve()) if Path(candidate_dir).exists() else str(candidate_dir),
        "source_count": len(sources),
        "total_target_count": sum(len(source.get("target_statuses") or []) for source in sources),
        "target_status_counts": target_status_counts,
        "preview_queue_count": len(preview_queue),
        "preview_queue": preview_queue,
        "sources": sources,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "manifest.json", payload)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# v0.3.13 Initialization Generation Source",
        "",
        f"- status: `{payload.get('status')}`",
        f"- source_count: `{payload.get('source_count')}`",
        f"- total_target_count: `{payload.get('total_target_count')}`",
        f"- preview_queue_count: `{payload.get('preview_queue_count')}`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 initialization generation source manifest.")
    parser.add_argument("--audit-summary", default=DEFAULT_AUDIT_SUMMARY)
    parser.add_argument("--candidate-dir", default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_initialization_generation_source(
        audit_summary_path=str(args.audit_summary),
        candidate_dir=str(args.candidate_dir),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "source_count": payload.get("source_count"), "preview_queue_count": payload.get("preview_queue_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
