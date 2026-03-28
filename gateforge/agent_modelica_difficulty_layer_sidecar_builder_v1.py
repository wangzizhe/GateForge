from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_difficulty_layer_spec_v1 import (
    LAYER_1,
    LAYER_2,
    LAYER_3,
    LAYER_4,
    STAGE_SUBTYPE_NONE,
    default_difficulty_layer_from_stage_subtype,
    stage_subtype_default_layer_reason,
)


SCHEMA_VERSION = "agent_modelica_difficulty_layer_sidecar_builder_v1"

MULTISTEP_LAYER_3_FAMILIES = {
    "stability_then_behavior",
    "behavior_then_robustness",
    "switch_then_recovery",
}


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _substrate_rows(payload: dict) -> tuple[str, list[dict], str]:
    if isinstance(payload.get("cases"), list):
        return "hardpack", [row for row in payload.get("cases") or [] if isinstance(row, dict)], "mutation_id"
    if isinstance(payload.get("tasks"), list):
        return "taskset", [row for row in payload.get("tasks") or [] if isinstance(row, dict)], "task_id"
    return "unknown", [], ""


def _read_text(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="latin-1")
    except Exception:
        return ""


def _infer_expected_layer(row: dict) -> tuple[str, str]:
    failure_type = str(row.get("expected_failure_type") or row.get("failure_type") or "").strip().lower()
    family = str(row.get("multi_step_family") or "").strip().lower()
    if family in MULTISTEP_LAYER_3_FAMILIES or failure_type in MULTISTEP_LAYER_3_FAMILIES:
        return LAYER_3, "inferred_from_task_family"
    if failure_type in {"semantic_regression", "constraint_violation"}:
        return LAYER_3, "inferred_from_failure_type"
    if failure_type in {"simulate_error", "numerical_instability"}:
        return LAYER_4, "inferred_from_failure_type"
    if failure_type == "model_check_error":
        mutated_model_path = str(row.get("mutated_model_path") or "").strip()
        model_text = _read_text(mutated_model_path)
        if "__gf_undef_" in model_text:
            return LAYER_1, "inferred_from_mutation_family"
        return LAYER_2, "inferred_from_failure_type"
    return "", ""


def _observed_candidates(results_paths: list[str]) -> dict[str, dict]:
    observed: dict[str, dict] = {}
    for path in results_paths:
        payload = _load_json(path)
        rows = payload.get("results") if isinstance(payload.get("results"), list) else payload.get("records")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            item_id = str(row.get("mutation_id") or row.get("task_id") or "").strip()
            if not item_id:
                continue
            resolution = row.get("resolution_attribution") if isinstance(row.get("resolution_attribution"), dict) else {}
            dominant_stage_subtype = str(
                resolution.get("dominant_stage_subtype")
                or row.get("dominant_stage_subtype")
                or row.get("stage_subtype")
                or ""
            ).strip()
            if not dominant_stage_subtype or dominant_stage_subtype == STAGE_SUBTYPE_NONE:
                continue
            difficulty_layer = default_difficulty_layer_from_stage_subtype(dominant_stage_subtype)
            if not difficulty_layer:
                continue
            observed[item_id] = {
                "difficulty_layer": difficulty_layer,
                "layer_reason": stage_subtype_default_layer_reason(dominant_stage_subtype) or "observed_from_run",
                "difficulty_layer_source": "observed",
                "dominant_stage_subtype": dominant_stage_subtype,
                "dominant_stage_subtype_source": "observed",
                "observed_results_path": str(path),
            }
    return observed


def build_sidecar(*, substrate_path: str, results_paths: list[str], out_sidecar: str) -> dict:
    substrate_payload = _load_json(substrate_path)
    substrate_kind, rows, id_key = _substrate_rows(substrate_payload)
    observed = _observed_candidates(results_paths)

    annotations: list[dict] = []
    inferred_count = 0
    observed_count = 0
    layer_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {"observed": 0, "inferred": 0}

    for row in rows:
        item_id = str(row.get(id_key) or "").strip()
        if not item_id:
            continue
        expected_layer_hint, expected_layer_reason = _infer_expected_layer(row)
        annotation = {
            "item_id": item_id,
            "item_kind": substrate_kind,
            "difficulty_layer": "",
            "layer_reason": "",
            "difficulty_layer_source": "",
            "dominant_stage_subtype": "",
            "dominant_stage_subtype_source": "",
            "expected_layer_hint": expected_layer_hint,
            "expected_layer_reason": expected_layer_reason,
        }
        observed_row = observed.get(item_id)
        if observed_row:
            annotation.update(observed_row)
            observed_count += 1
            source_counts["observed"] += 1
        elif expected_layer_hint:
            annotation["difficulty_layer"] = expected_layer_hint
            annotation["layer_reason"] = expected_layer_reason
            annotation["difficulty_layer_source"] = "inferred"
            annotation["dominant_stage_subtype"] = ""
            annotation["dominant_stage_subtype_source"] = "inferred"
            inferred_count += 1
            source_counts["inferred"] += 1
        if annotation["difficulty_layer"]:
            layer = str(annotation["difficulty_layer"])
            layer_counts[layer] = int(layer_counts.get(layer, 0)) + 1
        annotations.append(annotation)

    total = len(annotations)
    sidecar = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "substrate_path": str(substrate_path),
        "substrate_kind": substrate_kind,
        "annotations": annotations,
        "summary": {
            "total_items": total,
            "observed_count": observed_count,
            "inferred_count": inferred_count,
            "inferred_ratio": round((inferred_count / total) * 100.0, 2) if total else 0.0,
            "source_counts": source_counts,
            "layer_counts": dict(sorted(layer_counts.items())),
            "results_paths": [str(path) for path in results_paths],
        },
    }
    _write_json(out_sidecar, sidecar)
    return sidecar["summary"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build difficulty-layer sidecar metadata for hardpacks and tasksets")
    parser.add_argument("--substrate", required=True)
    parser.add_argument("--results", action="append", default=[])
    parser.add_argument("--out-sidecar", required=True)
    parser.add_argument("--out-summary", default="")
    args = parser.parse_args()

    summary = build_sidecar(
        substrate_path=str(args.substrate),
        results_paths=[str(path) for path in (args.results or []) if str(path).strip()],
        out_sidecar=str(args.out_sidecar),
    )
    out_summary = str(args.out_summary or "")
    if out_summary:
        _write_json(out_summary, {"schema_version": SCHEMA_VERSION, **summary})
    print(json.dumps({"status": "PASS", "total_items": int(summary.get("total_items") or 0), "inferred_ratio": float(summary.get("inferred_ratio") or 0.0)}))


if __name__ == "__main__":
    main()
