from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_difficulty_layer_summary_v1"


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
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


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _row_id(row: dict) -> str:
    return str(row.get("mutation_id") or row.get("task_id") or "").strip()


def _annotation_rows(sidecar: dict) -> list[dict]:
    rows = sidecar.get("annotations") if isinstance(sidecar.get("annotations"), list) else []
    return [row for row in rows if isinstance(row, dict) and str(row.get("item_id") or "").strip()]


def _gateforge_success_map(payload: dict) -> dict[str, bool]:
    out: dict[str, bool] = {}
    rows = payload.get("results") if isinstance(payload.get("results"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = _row_id(row)
        if not item_id:
            continue
        out[item_id] = bool(row.get("success"))
    return out


def _bare_success_map(payload: dict) -> dict[str, bool]:
    out: dict[str, bool] = {}
    rows = payload.get("bare_llm_results") if isinstance(payload.get("bare_llm_results"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = _row_id(row)
        if not item_id:
            continue
        out[item_id] = bool(row.get("success"))
    return out


def _run_contract_success_map(payload: dict) -> dict[str, bool]:
    out: dict[str, bool] = {}
    rows = payload.get("records") if isinstance(payload.get("records"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = _row_id(row)
        if not item_id:
            continue
        out[item_id] = bool(row.get("passed"))
    return out


def _run_contract_bool_map(payload: dict, key: str) -> dict[str, bool]:
    out: dict[str, bool] = {}
    rows = payload.get("records") if isinstance(payload.get("records"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = _row_id(row)
        if not item_id:
            continue
        out[item_id] = bool(row.get(key))
    return out


def summarize_lane(lane: dict) -> dict:
    lane_id = str(lane.get("lane_id") or "").strip() or "unknown_lane"
    sidecar = _load_json(str(lane.get("sidecar") or ""))
    gf_results = _load_json(str(lane.get("gf_results") or ""))
    comparison = _load_json(str(lane.get("comparison_summary") or ""))
    run_results = _load_json(str(lane.get("run_results") or ""))

    annotations = _annotation_rows(sidecar)
    gf_success = _gateforge_success_map(gf_results)
    bare_success = _bare_success_map(comparison)
    run_success = _run_contract_success_map(run_results)
    planner_invoked = _run_contract_bool_map(run_results, "planner_invoked")
    replay_used = _run_contract_bool_map(run_results, "replay_used")

    per_layer: dict[str, dict] = {}
    for row in annotations:
        layer = str(row.get("difficulty_layer") or "").strip()
        if not layer:
            continue
        bucket = per_layer.setdefault(
            layer,
            {
                "case_count": 0,
                "observed_count": 0,
                "override_count": 0,
                "inferred_count": 0,
                "override_ratio": 0.0,
                "inferred_ratio": 0.0,
                "gateforge_success_count": 0,
                "gateforge_success_rate_pct": 0.0,
                "bare_success_count": 0,
                "bare_success_rate_pct": 0.0,
                "planner_invoked_count": 0,
                "planner_invoked_rate_pct": 0.0,
                "replay_used_count": 0,
                "replay_used_rate_pct": 0.0,
            },
        )
        bucket["case_count"] += 1
        source = str(row.get("difficulty_layer_source") or "").strip().lower()
        if source == "observed":
            bucket["observed_count"] += 1
        elif source == "override":
            bucket["override_count"] += 1
        elif source == "inferred":
            bucket["inferred_count"] += 1
        item_id = str(row.get("item_id") or "").strip()
        if item_id in gf_success and gf_success[item_id]:
            bucket["gateforge_success_count"] += 1
        elif item_id in run_success and run_success[item_id]:
            bucket["gateforge_success_count"] += 1
        if item_id in bare_success and bare_success[item_id]:
            bucket["bare_success_count"] += 1
        if item_id in planner_invoked and planner_invoked[item_id]:
            bucket["planner_invoked_count"] += 1
        if item_id in replay_used and replay_used[item_id]:
            bucket["replay_used_count"] += 1

    for bucket in per_layer.values():
        total = int(bucket["case_count"])
        bucket["override_ratio"] = _ratio(int(bucket["override_count"]), total)
        bucket["inferred_ratio"] = _ratio(int(bucket["inferred_count"]), total)
        bucket["gateforge_success_rate_pct"] = _ratio(int(bucket["gateforge_success_count"]), total)
        bucket["bare_success_rate_pct"] = _ratio(int(bucket["bare_success_count"]), total)
        bucket["planner_invoked_rate_pct"] = _ratio(int(bucket["planner_invoked_count"]), total)
        bucket["replay_used_rate_pct"] = _ratio(int(bucket["replay_used_count"]), total)

    present_layers = sorted(per_layer.keys())
    missing_layers = [layer for layer in ("layer_1", "layer_2", "layer_3", "layer_4") if layer not in per_layer]
    return {
        "lane_id": lane_id,
        "label": str(lane.get("label") or lane_id),
        "sidecar": str(lane.get("sidecar") or ""),
        "per_layer": {key: per_layer[key] for key in sorted(per_layer.keys())},
        "present_layers": present_layers,
        "missing_layers": missing_layers,
    }


def build_summary(spec: dict) -> dict:
    lanes = spec.get("lanes") if isinstance(spec.get("lanes"), list) else []
    lane_summaries = [summarize_lane(lane) for lane in lanes if isinstance(lane, dict)]
    aggregate_layer_counts: dict[str, int] = {}
    aggregate_missing: dict[str, list[str]] = {}
    for lane in lane_summaries:
        for layer, bucket in (lane.get("per_layer") or {}).items():
            aggregate_layer_counts[layer] = int(aggregate_layer_counts.get(layer, 0)) + int(bucket.get("case_count") or 0)
        for layer in lane.get("missing_layers") or []:
            rows = aggregate_missing.setdefault(str(layer), [])
            rows.append(str(lane.get("lane_id") or ""))
    coverage_gap = {
        "aggregate_layer_counts": {key: aggregate_layer_counts[key] for key in sorted(aggregate_layer_counts.keys())},
        "missing_by_layer": {key: sorted(value) for key, value in sorted(aggregate_missing.items())},
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "lane_count": len(lane_summaries),
        "lanes": lane_summaries,
        "coverage_gap": coverage_gap,
    }


def _write_markdown(path: str | Path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent Modelica Difficulty Layer Summary v1",
        "",
        f"- lane_count: `{payload.get('lane_count')}`",
        "",
    ]
    for lane in payload.get("lanes") or []:
        if not isinstance(lane, dict):
            continue
        lines.append(f"## {lane.get('label')}")
        lines.append("")
        lines.append(f"- present_layers: `{','.join(lane.get('present_layers') or []) or 'none'}`")
        lines.append(f"- missing_layers: `{','.join(lane.get('missing_layers') or []) or 'none'}`")
        lines.append("")
        for layer, bucket in (lane.get("per_layer") or {}).items():
            lines.append(f"- {layer}: cases=`{bucket.get('case_count')}`, override_ratio=`{bucket.get('override_ratio')}`, inferred_ratio=`{bucket.get('inferred_ratio')}`, gateforge_success_rate_pct=`{bucket.get('gateforge_success_rate_pct')}`, bare_success_rate_pct=`{bucket.get('bare_success_rate_pct')}`, planner_invoked_rate_pct=`{bucket.get('planner_invoked_rate_pct')}`")
        lines.append("")
    lines.append("## Coverage Gap")
    lines.append("")
    gap = payload.get("coverage_gap") if isinstance(payload.get("coverage_gap"), dict) else {}
    for layer, lanes in (gap.get("missing_by_layer") or {}).items():
        lines.append(f"- {layer}: `{','.join(lanes)}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize difficulty-layer coverage and performance by lane")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    spec = _load_json(str(args.spec))
    payload = build_summary(spec)
    _write_json(str(args.out), payload)
    _write_markdown(str(args.report_out or _default_md_path(str(args.out))), payload)
    print(json.dumps({"status": "PASS", "lane_count": int(payload.get("lane_count") or 0)}))


if __name__ == "__main__":
    main()
