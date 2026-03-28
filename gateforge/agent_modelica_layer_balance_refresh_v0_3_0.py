from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_difficulty_layer_summary_v1 import build_summary


SCHEMA_VERSION = "agent_modelica_layer_balance_refresh_v0_3_0"
DEFAULT_BASE_SPEC = "artifacts/agent_modelica_difficulty_layer_v0_2_6/spec.json"
DEFAULT_BASE_SUMMARY = "artifacts/agent_modelica_difficulty_layer_v0_2_6/summary.json"
DEFAULT_LAYER4_LANE_DIR = "artifacts/agent_modelica_layer4_hard_lane_v0_3_0"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_difficulty_layer_v0_3_0"


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


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _aggregate_counts(payload: dict) -> dict[str, int]:
    gap = payload.get("coverage_gap") if isinstance(payload.get("coverage_gap"), dict) else {}
    counts = gap.get("aggregate_layer_counts") if isinstance(gap.get("aggregate_layer_counts"), dict) else {}
    return {str(key): int(value or 0) for key, value in counts.items()}


def _append_lane(base_spec: dict, *, layer4_lane_dir: str) -> dict:
    lanes = [dict(row) for row in (base_spec.get("lanes") or []) if isinstance(row, dict)]
    lane_dir = Path(layer4_lane_dir)
    lanes.append(
        {
            "lane_id": "layer4_hard_v0_3_0",
            "label": "Layer 4 Hard Lane v0.3.0",
            "sidecar": str((lane_dir / "layer_metadata.json").resolve()),
        }
    )
    return {"lanes": lanes}


def build_layer_balance_refresh(
    *,
    base_spec_path: str = DEFAULT_BASE_SPEC,
    base_summary_path: str = DEFAULT_BASE_SUMMARY,
    layer4_lane_dir: str = DEFAULT_LAYER4_LANE_DIR,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    base_spec = _load_json(base_spec_path)
    base_summary = _load_json(base_summary_path)
    refresh_spec = _append_lane(base_spec, layer4_lane_dir=layer4_lane_dir)
    refresh_summary = build_summary(refresh_spec)

    before_counts = _aggregate_counts(base_summary)
    after_counts = _aggregate_counts(refresh_summary)
    all_layers = sorted(set(before_counts.keys()) | set(after_counts.keys()) | {"layer_1", "layer_2", "layer_3", "layer_4"})
    count_delta = {
        layer: {
            "before": int(before_counts.get(layer) or 0),
            "after": int(after_counts.get(layer) or 0),
            "delta": int(after_counts.get(layer) or 0) - int(before_counts.get(layer) or 0),
        }
        for layer in all_layers
    }
    before_total = sum(before_counts.values())
    after_total = sum(after_counts.values())
    before_layer4 = int(before_counts.get("layer_4") or 0)
    after_layer4 = int(after_counts.get("layer_4") or 0)
    coverage_delta = {
        "before_total_case_count": before_total,
        "after_total_case_count": after_total,
        "before_layer4_case_count": before_layer4,
        "after_layer4_case_count": after_layer4,
        "layer4_case_count_delta": after_layer4 - before_layer4,
        "before_layer4_share_pct": _ratio(before_layer4, before_total),
        "after_layer4_share_pct": _ratio(after_layer4, after_total),
        "explicit_layer4_coverage_improved": after_layer4 > before_layer4,
    }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if coverage_delta["explicit_layer4_coverage_improved"] else "FAIL",
        "base_spec_path": str(Path(base_spec_path).resolve()) if Path(base_spec_path).exists() else str(base_spec_path),
        "base_summary_path": str(Path(base_summary_path).resolve()) if Path(base_summary_path).exists() else str(base_summary_path),
        "layer4_lane_dir": str(Path(layer4_lane_dir).resolve()) if Path(layer4_lane_dir).exists() else str(layer4_lane_dir),
        "lane_count": int(refresh_summary.get("lane_count") or 0),
        "refresh_spec": refresh_spec,
        "refresh_summary": refresh_summary,
        "coverage_delta": coverage_delta,
        "count_delta_by_layer": count_delta,
    }

    out_root = Path(out_dir)
    _write_json(out_root / "spec.json", refresh_spec)
    _write_json(out_root / "summary.json", payload)
    lines = [
        "# Agent Modelica Difficulty Layer Refresh v0.3.0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- lane_count: `{payload.get('lane_count')}`",
        f"- before_layer4_case_count: `{coverage_delta.get('before_layer4_case_count')}`",
        f"- after_layer4_case_count: `{coverage_delta.get('after_layer4_case_count')}`",
        f"- layer4_case_count_delta: `{coverage_delta.get('layer4_case_count_delta')}`",
        f"- before_layer4_share_pct: `{coverage_delta.get('before_layer4_share_pct')}`",
        f"- after_layer4_share_pct: `{coverage_delta.get('after_layer4_share_pct')}`",
        "",
    ]
    (out_root / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh difficulty-layer coverage with the v0.3.0 Layer 4 hard lane")
    parser.add_argument("--base-spec", default=DEFAULT_BASE_SPEC)
    parser.add_argument("--base-summary", default=DEFAULT_BASE_SUMMARY)
    parser.add_argument("--layer4-lane-dir", default=DEFAULT_LAYER4_LANE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    payload = build_layer_balance_refresh(
        base_spec_path=str(args.base_spec),
        base_summary_path=str(args.base_summary),
        layer4_lane_dir=str(args.layer4_lane_dir),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "lane_count": int(payload.get("lane_count") or 0)}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
