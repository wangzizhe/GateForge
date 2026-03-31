from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_track_c_primary_slice_v0_3_3 import (
    _attribution_gate,
    _family_gate,
    _planner_sensitivity_gate,
)


SCHEMA_VERSION = "agent_modelica_harder_lane_gate_v0_3_4"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_harder_lane_gate_v0_3_4"
DEFAULT_MIN_FREEZE_READY_CASES = 5


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("item_id") or row.get("task_id") or row.get("mutation_id"))


def _lane_status(*, candidate_count: int, attributed_count: int, planner_sensitive_count: int, freeze_ready_count: int, min_freeze_ready_cases: int) -> str:
    if freeze_ready_count >= int(min_freeze_ready_cases):
        return "FREEZE_READY"
    if attributed_count > 0 and planner_sensitive_count > 0:
        return "ATTRIBUTION_VALID"
    if candidate_count > 0:
        return "CANDIDATE_READY"
    return "NEEDS_MORE_GENERATION"


def build_harder_lane_gate(
    *,
    refreshed_candidate_taskset_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
    min_freeze_ready_cases: int = DEFAULT_MIN_FREEZE_READY_CASES,
) -> dict:
    payload = _load_json(refreshed_candidate_taskset_path)
    rows = _task_rows(payload)
    families: dict[str, list[dict]] = {}
    for row in rows:
        family_id = _norm(row.get("v0_3_family_id")) or "unknown_family"
        families.setdefault(family_id, []).append(row)

    lane_rows: list[dict] = []
    for family_id, family_rows in sorted(families.items()):
        candidate_count = 0
        attributed_count = 0
        planner_sensitive_count = 0
        freeze_ready_count = 0
        freeze_ready_ids: list[str] = []

        for row in family_rows:
            holdout_clean = bool(row.get("holdout_clean"))
            family_ok, _ = _family_gate(row)
            attribution_ok, _ = _attribution_gate(row)
            planner_ok, _ = _planner_sensitivity_gate(row)
            if holdout_clean:
                candidate_count += 1
            if holdout_clean and attribution_ok:
                attributed_count += 1
            if holdout_clean and planner_ok:
                planner_sensitive_count += 1
            if holdout_clean and family_ok and attribution_ok and planner_ok:
                freeze_ready_count += 1
                freeze_ready_ids.append(_item_id(row))

        status = _lane_status(
            candidate_count=candidate_count,
            attributed_count=attributed_count,
            planner_sensitive_count=planner_sensitive_count,
            freeze_ready_count=freeze_ready_count,
            min_freeze_ready_cases=int(min_freeze_ready_cases),
        )
        lane_rows.append(
            {
                "family_id": family_id,
                "status": status,
                "candidate_count": candidate_count,
                "attribution_valid_count": attributed_count,
                "planner_sensitive_count": planner_sensitive_count,
                "freeze_ready_count": freeze_ready_count,
                "freeze_ready_gap": max(0, int(min_freeze_ready_cases) - freeze_ready_count),
                "freeze_ready_ids": freeze_ready_ids,
            }
        )

    overall_status = "PASS" if rows else "FAIL"
    if lane_rows and not any(_norm(row.get("status")) == "FREEZE_READY" for row in lane_rows):
        overall_status = "NEEDS_MORE_GENERATION"
    payload_out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": overall_status,
        "refreshed_candidate_taskset_path": str(Path(refreshed_candidate_taskset_path).resolve()) if Path(refreshed_candidate_taskset_path).exists() else str(refreshed_candidate_taskset_path),
        "targets": {"min_freeze_ready_cases": int(min_freeze_ready_cases)},
        "lane_rows": lane_rows,
        "notes": [
            "Candidate-ready means holdout-clean generation exists for the lane.",
            "Attribution-valid means holdout-clean candidates also carry attribution-bearing evidence and planner-sensitivity signals.",
            "Freeze-ready means a lane has enough cases to freeze as the next harder comparative lane.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload_out)
    _write_text(out_root / "summary.md", render_markdown(payload_out))
    return payload_out


def render_markdown(payload: dict) -> str:
    lines = [
        "# Agent Modelica Harder Lane Gate v0.3.4",
        "",
        f"- status: `{payload.get('status')}`",
        f"- min_freeze_ready_cases: `{(payload.get('targets') or {}).get('min_freeze_ready_cases')}`",
        "",
    ]
    for row in payload.get("lane_rows") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"## {row.get('family_id')}")
        lines.append("")
        lines.append(f"- status: `{row.get('status')}`")
        lines.append(f"- candidate_count: `{row.get('candidate_count')}`")
        lines.append(f"- attribution_valid_count: `{row.get('attribution_valid_count')}`")
        lines.append(f"- planner_sensitive_count: `{row.get('planner_sensitive_count')}`")
        lines.append(f"- freeze_ready_count: `{row.get('freeze_ready_count')}`")
        lines.append(f"- freeze_ready_gap: `{row.get('freeze_ready_gap')}`")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate candidate-ready, attribution-valid, and freeze-ready status for harder v0.3.4 lanes.")
    parser.add_argument("--refreshed-candidate-taskset", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-freeze-ready-cases", type=int, default=DEFAULT_MIN_FREEZE_READY_CASES)
    args = parser.parse_args()
    payload = build_harder_lane_gate(
        refreshed_candidate_taskset_path=str(args.refreshed_candidate_taskset),
        out_dir=str(args.out_dir),
        min_freeze_ready_cases=int(args.min_freeze_ready_cases),
    )
    print(json.dumps({"status": payload.get("status"), "lane_count": len(payload.get("lane_rows") or [])}))


if __name__ == "__main__":
    main()
