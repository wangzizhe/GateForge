from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from .agent_modelica_dual_layer_mutation_v0_3_6 import _candidate_real_parameter_matches
from .agent_modelica_post_restore_taskset_v0_3_6 import CANDIDATE_SPECS


SCHEMA_VERSION = "agent_modelica_v0_3_13_runtime_generation_source"
DEFAULT_RUNTIME_TASKSET = "artifacts/agent_modelica_v0_3_13_runtime_curriculum_taskset_current/taskset.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_runtime_generation_source"
RUNTIME_OPERATOR = "paired_value_collapse"
DEFAULT_COLLAPSE_PRESET_ID = "collapse_pair_to_zero_zero"
DEFAULT_COLLAPSE_VALUES = ("0.0", "0.0")


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


def _source_spec_by_task_id() -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for row in CANDIDATE_SPECS:
        task_id = _norm(row.get("task_id"))
        if task_id:
            mapping[task_id] = row
    return mapping


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _all_parameter_pairs(model_text: str) -> list[list[str]]:
    names = [_norm(row.get("name")) for row in _candidate_real_parameter_matches(model_text) if _norm(row.get("name"))]
    return [list(pair) for pair in combinations(names, 2)]


def _pair_statuses(*, known_good_pair: list[str], all_pairs: list[list[str]]) -> list[dict]:
    statuses = []
    for pair in all_pairs:
        statuses.append(
            {
                "param_names": pair,
                "status": "validated_runtime_seed" if pair == known_good_pair else "requires_preview",
            }
        )
    return statuses


def build_runtime_generation_source(
    *,
    runtime_taskset_path: str = DEFAULT_RUNTIME_TASKSET,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    runtime_taskset = _load_json(runtime_taskset_path)
    source_specs = _source_spec_by_task_id()
    sources = []
    for row in _task_rows(runtime_taskset):
        task_id = _norm(row.get("task_id"))
        spec = source_specs.get(task_id, {})
        clean_model_text = _norm(spec.get("model_text"))
        if not task_id or not clean_model_text:
            continue
        known_good_pair = [name for name in row.get("runtime_recovery_parameter_names") if _norm(name)]
        all_pairs = _all_parameter_pairs(clean_model_text)
        sources.append(
            {
                "source_task_id": task_id,
                "model_hint": _norm(row.get("model_hint") or spec.get("model_name")),
                "source_model_path": _norm(spec.get("source_model_path") or row.get("source_model_path")),
                "source_library": _norm(spec.get("source_library") or row.get("source_library")),
                "clean_model_text": clean_model_text,
                "allowed_hidden_base_operator": RUNTIME_OPERATOR,
                "default_preset": {
                    "preset_id": DEFAULT_COLLAPSE_PRESET_ID,
                    "replacement_values": list(DEFAULT_COLLAPSE_VALUES),
                },
                "known_good_param_pair": known_good_pair,
                "all_candidate_param_pairs": all_pairs,
                "pair_statuses": _pair_statuses(known_good_pair=known_good_pair, all_pairs=all_pairs),
                "evidence": {
                    "family_id": _norm(row.get("v0_3_13_family_id")),
                    "course_stage": _norm(row.get("course_stage")),
                    "residual_signal_cluster_id": _norm((row.get("preview_contract") or {}).get("residual_signal_cluster_id")),
                    "post_rule_residual_stage": _norm((row.get("preview_contract") or {}).get("post_rule_residual_stage")),
                    "post_rule_residual_error_type": _norm((row.get("preview_contract") or {}).get("post_rule_residual_error_type")),
                    "post_rule_residual_reason": _norm((row.get("preview_contract") or {}).get("post_rule_residual_reason")),
                },
            }
        )

    pair_status_counts: dict[str, int] = {}
    total_pairs = 0
    for source in sources:
        for pair_row in source.get("pair_statuses") or []:
            if not isinstance(pair_row, dict):
                continue
            status = _norm(pair_row.get("status")) or "unknown"
            pair_status_counts[status] = pair_status_counts.get(status, 0) + 1
            total_pairs += 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if sources else "EMPTY",
        "runtime_taskset_path": str(Path(runtime_taskset_path).resolve()) if Path(runtime_taskset_path).exists() else str(runtime_taskset_path),
        "source_count": len(sources),
        "total_candidate_pair_count": total_pairs,
        "pair_status_counts": pair_status_counts,
        "sources": sources,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "manifest.json", payload)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# v0.3.13 Runtime Generation Source",
        "",
        f"- status: `{payload.get('status')}`",
        f"- source_count: `{payload.get('source_count')}`",
        f"- total_candidate_pair_count: `{payload.get('total_candidate_pair_count')}`",
        "",
        "## Pair Status Counts",
        "",
    ]
    for key, value in sorted((payload.get("pair_status_counts") or {}).items()):
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 runtime generation source manifest.")
    parser.add_argument("--runtime-taskset", default=DEFAULT_RUNTIME_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_runtime_generation_source(
        runtime_taskset_path=str(args.runtime_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "source_count": payload.get("source_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
