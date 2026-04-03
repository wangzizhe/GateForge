from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_dual_layer_mutation_v0_3_5 import apply_marked_top_mutation, build_dual_layer_task
from .agent_modelica_v0_3_13_initialization_curriculum_sources import SOURCE_SPECS
from .agent_modelica_v0_3_15_replay_sensitive_admission_spec import (
    MAIN_INITIALIZATION_ANCHOR,
    MAIN_RUNTIME_ANCHOR,
    SUPPORTING_INITIALIZATION_ANCHOR,
    has_exact_match_anchor,
)


SCHEMA_VERSION = "agent_modelica_v0_3_15_replay_sensitive_candidates"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_SOURCE_MANIFEST = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_generation_source_current" / "manifest.json"
DEFAULT_EXPERIENCE_STORE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_authority_trace_extraction_current" / "experience_store.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_candidate_lane_current"

RUNTIME_FAMILY_ID = "runtime_same_cluster_harder_variant"
INITIALIZATION_FAMILY_ID = "initialization_same_cluster_harder_variant"
SUPPLEMENTARY_FAMILY_ID = "failure_bank_near_miss_variant"
SAFE_INITIALIZATION_SOURCE_IDS = {
    "init_log_sqrt",
    "init_dual_sqrt",
    "init_log_growth",
}


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


def _candidate_real_parameter_matches(model_text: str) -> list[dict]:
    pattern = re.compile(
        r"(parameter\s+Real\s+(\w+)\s*(?:\([^)]*\))?\s*=\s*)([0-9]+\.?[0-9]*(?:e[+-]?[0-9]+)?)(\s*;)",
        re.IGNORECASE,
    )
    rows = []
    for match in pattern.finditer(model_text):
        rows.append(
            {
                "span": (match.start(3), match.end(3)),
                "name": match.group(2),
                "value": match.group(3),
            }
        )
    return rows


def apply_multi_value_collapse(
    model_text: str,
    *,
    target_param_names: list[str] | tuple[str, ...],
    collapse_value: str = "0.0",
) -> tuple[str, dict]:
    wanted = [_norm(name) for name in target_param_names if _norm(name)]
    matches = _candidate_real_parameter_matches(model_text)
    by_name = {_norm(row.get("name")): row for row in matches}
    picked = [by_name.get(name) for name in wanted]
    if not wanted or any(row is None for row in picked):
        return model_text, {
            "applied": False,
            "reason": "target_parameter_set_not_found",
        }
    mutated = model_text
    mutations = []
    for row in sorted([item for item in picked if isinstance(item, dict)], key=lambda item: item["span"][0], reverse=True):
        start, end = row["span"]
        mutated = mutated[:start] + collapse_value + mutated[end:]
        mutations.append(
            {
                "param_name": row["name"],
                "original_value": row["value"],
                "new_value": collapse_value,
            }
        )
    mutations.reverse()
    return mutated, {
        "applied": True,
        "operator": "multi_value_collapse",
        "mutation_count": len(mutations),
        "mutations": mutations,
        "target_param_names": wanted,
        "has_gateforge_marker": False,
    }


def _runtime_task_id(source_task_id: str, param_names: list[str]) -> str:
    suffix = "_".join(_norm(name).lower() for name in param_names if _norm(name))
    return f"{source_task_id}__harder_{suffix}__candidate"


def _initialization_task_id(source_id: str, target_names: list[str]) -> str:
    suffix = "_".join(_norm(name).lower() for name in target_names if _norm(name))
    return f"{source_id}__dual_{suffix}__candidate"


def build_runtime_same_cluster_harder_variant(source_row: dict) -> dict:
    param_rows = _candidate_real_parameter_matches(_norm(source_row.get("clean_model_text")))
    target_param_names = [_norm(row.get("name")) for row in param_rows if _norm(row.get("name"))]
    mutated_source_text, base_audit = apply_multi_value_collapse(
        _norm(source_row.get("clean_model_text")),
        target_param_names=target_param_names,
        collapse_value="0.0",
    )
    if not base_audit.get("applied"):
        raise RuntimeError(f"runtime harder variant build failed: {base_audit.get('reason')}")
    task_id = _runtime_task_id(_norm(source_row.get("source_task_id")), target_param_names)
    mutated_model_text, top_audit = apply_marked_top_mutation(mutated_source_text)
    if not top_audit.get("applied"):
        raise RuntimeError(f"runtime harder variant top mutation failed: {top_audit.get('reason')}")
    task = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "task_id": task_id,
        "failure_type": "simulate_error",
        "declared_failure_type": "simulate_error",
        "expected_stage": "simulate",
        "source_model_path": _norm(source_row.get("source_model_path")),
        "source_library": _norm(source_row.get("source_library")),
        "model_hint": _norm(source_row.get("model_hint")),
        "source_model_text": mutated_source_text,
        "mutated_model_text": mutated_model_text,
        "mutation_spec": {
            "hidden_base": {
                "operator": "multi_value_collapse",
                "audit": base_audit,
                "has_gateforge_marker": False,
            },
            "marked_top": {
                "operator": "simulate_error_top_injection",
                "audit": top_audit,
                "has_gateforge_marker": True,
                "removed_by_rule": "rule_simulate_error_injection_repair",
            },
        },
        "v0_3_15_family_id": RUNTIME_FAMILY_ID,
        "v0_3_15_variant_kind": "runtime_same_cluster_harder_variant",
        "v0_3_15_candidate_priority": 1,
        "v0_3_15_source_lane": "runtime_curriculum_source",
        "v0_3_15_expected_retrieval_anchor": dict(MAIN_RUNTIME_ANCHOR),
        "v0_3_15_expected_retrieval_anchors": [dict(MAIN_RUNTIME_ANCHOR)],
        "v0_3_13_source_task_id": _norm(source_row.get("source_task_id")),
        "v0_3_15_target_param_names": target_param_names,
        "v0_3_15_supplementary_source": False,
    }
    return task


def build_initialization_same_cluster_harder_variant(spec: dict) -> dict:
    target_names = [_norm(name) for name in (spec.get("target_lhs_names") or []) if _norm(name)]
    task = build_dual_layer_task(
        task_id=_initialization_task_id(_norm(spec.get("source_id")), target_names),
        clean_source_text=_norm(spec.get("model_text")),
        source_model_path=_norm(spec.get("source_model_path")),
        source_library=_norm(spec.get("source_library")),
        model_hint=_norm(spec.get("model_name")),
        hidden_base_operator="init_equation_sign_flip",
        hidden_base_kwargs={
            "target_lhs_names": list(target_names),
            "max_targets": len(target_names),
        },
    )
    task["schema_version"] = SCHEMA_VERSION
    task["v0_3_15_family_id"] = INITIALIZATION_FAMILY_ID
    task["v0_3_15_variant_kind"] = "initialization_same_cluster_harder_variant"
    task["v0_3_15_candidate_priority"] = 2
    task["v0_3_15_source_lane"] = "initialization_selective_source"
    task["v0_3_15_expected_retrieval_anchor"] = dict(MAIN_INITIALIZATION_ANCHOR)
    task["v0_3_15_expected_retrieval_anchors"] = [
        dict(MAIN_INITIALIZATION_ANCHOR),
        dict(SUPPORTING_INITIALIZATION_ANCHOR),
    ]
    task["v0_3_13_source_id"] = _norm(spec.get("source_id"))
    task["v0_3_15_target_lhs_names"] = target_names
    task["v0_3_15_supplementary_source"] = False
    return task


def _runtime_sources(runtime_manifest: dict) -> list[dict]:
    rows = runtime_manifest.get("sources")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _annotate_offline_retrieval(task: dict, experience_payload: dict) -> dict:
    primary = task.get("v0_3_15_expected_retrieval_anchor") if isinstance(task.get("v0_3_15_expected_retrieval_anchor"), dict) else {}
    supporting = [row for row in (task.get("v0_3_15_expected_retrieval_anchors") or []) if isinstance(row, dict)]
    primary_ready = has_exact_match_anchor(
        experience_payload,
        dominant_stage_subtype=_norm(primary.get("dominant_stage_subtype")),
        residual_signal_cluster=_norm(primary.get("residual_signal_cluster")),
    )
    supporting_ready_count = 0
    for anchor in supporting:
        if has_exact_match_anchor(
            experience_payload,
            dominant_stage_subtype=_norm(anchor.get("dominant_stage_subtype")),
            residual_signal_cluster=_norm(anchor.get("residual_signal_cluster")),
        ):
            supporting_ready_count += 1
    enriched = dict(task)
    enriched["v0_3_15_offline_exact_match_ready"] = bool(primary_ready)
    enriched["v0_3_15_supporting_anchor_ready_count"] = supporting_ready_count
    return enriched


def build_replay_sensitive_candidate_lane(
    *,
    runtime_source_manifest_path: str = str(DEFAULT_RUNTIME_SOURCE_MANIFEST),
    experience_store_path: str = str(DEFAULT_EXPERIENCE_STORE),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    runtime_manifest = _load_json(runtime_source_manifest_path)
    experience_payload = _load_json(experience_store_path)
    runtime_tasks = []
    for source_row in _runtime_sources(runtime_manifest):
        param_rows = _candidate_real_parameter_matches(_norm(source_row.get("clean_model_text")))
        if len(param_rows) < 3:
            continue
        runtime_tasks.append(build_runtime_same_cluster_harder_variant(source_row))
    initialization_tasks = []
    for spec in SOURCE_SPECS:
        if _norm(spec.get("source_id")) not in SAFE_INITIALIZATION_SOURCE_IDS:
            continue
        initialization_tasks.append(build_initialization_same_cluster_harder_variant(spec))

    tasks = [_annotate_offline_retrieval(task, experience_payload) for task in runtime_tasks + initialization_tasks]
    family_counts: dict[str, int] = {}
    offline_ready_count = 0
    for task in tasks:
        family_id = _norm(task.get("v0_3_15_family_id")) or "unknown"
        family_counts[family_id] = family_counts.get(family_id, 0) + 1
        if bool(task.get("v0_3_15_offline_exact_match_ready")):
            offline_ready_count += 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if tasks else "EMPTY",
        "runtime_source_manifest_path": str(Path(runtime_source_manifest_path).resolve()) if Path(runtime_source_manifest_path).exists() else str(runtime_source_manifest_path),
        "experience_store_path": str(Path(experience_store_path).resolve()) if Path(experience_store_path).exists() else str(experience_store_path),
        "task_count": len(tasks),
        "runtime_candidate_count": len(runtime_tasks),
        "initialization_candidate_count": len(initialization_tasks),
        "offline_exact_match_ready_count": offline_ready_count,
        "offline_exact_match_ready_rate_pct": round(100.0 * offline_ready_count / float(len(tasks)), 1) if tasks else 0.0,
        "family_counts": family_counts,
        "tasks": tasks,
    }
    out_root = Path(out_dir)
    for task in tasks:
        _write_json(out_root / "tasks" / f"{task['task_id']}.json", task)
    _write_json(out_root / "taskset.json", payload)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    return "\n".join(
        [
            "# v0.3.15 Replay-Sensitive Candidate Lane",
            "",
            f"- status: `{payload.get('status')}`",
            f"- task_count: `{payload.get('task_count')}`",
            f"- runtime_candidate_count: `{payload.get('runtime_candidate_count')}`",
            f"- initialization_candidate_count: `{payload.get('initialization_candidate_count')}`",
            f"- offline_exact_match_ready_rate_pct: `{payload.get('offline_exact_match_ready_rate_pct')}`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.3.15 replay-sensitive harder candidates.")
    parser.add_argument("--runtime-source-manifest", default=str(DEFAULT_RUNTIME_SOURCE_MANIFEST))
    parser.add_argument("--experience-store", default=str(DEFAULT_EXPERIENCE_STORE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_replay_sensitive_candidate_lane(
        runtime_source_manifest_path=str(args.runtime_source_manifest),
        experience_store_path=str(args.experience_store),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
