from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_initialization_live_work_order"
DEFAULT_LIVE_SUMMARY = "artifacts/agent_modelica_v0_3_13_initialization_live_evidence_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_initialization_live_work_order_current"


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


def build_initialization_live_work_order(
    *,
    live_summary_path: str = DEFAULT_LIVE_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    live_summary = _load_json(live_summary_path)
    rows = [row for row in (live_summary.get("results") or []) if isinstance(row, dict)]
    progressive_rows = [row for row in rows if bool(row.get("progressive_solve"))]
    failed_rows = [row for row in rows if _norm(row.get("verdict")) == "FAIL"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "initialization_lane_status": "LIVE_EVIDENCE_READY" if progressive_rows else "NEEDS_MORE_LIVE_EVIDENCE",
        "promoted_count": len(progressive_rows),
        "failed_count": len(failed_rows),
        "promoted_targets": [
            {
                "task_id": _norm(row.get("task_id")),
                "source_id": _norm(row.get("v0_3_13_source_id")),
                "lhs": _norm(row.get("v0_3_13_initialization_target_lhs")),
                "rounds_used": int(row.get("rounds_used") or 0),
            }
            for row in progressive_rows
        ],
        "failed_targets": [
            {
                "task_id": _norm(row.get("task_id")),
                "source_id": _norm(row.get("v0_3_13_source_id")),
                "lhs": _norm(row.get("v0_3_13_initialization_target_lhs")),
                "rounds_used": int(row.get("rounds_used") or 0),
            }
            for row in failed_rows
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.13 Initialization Live Work Order",
                "",
                f"- initialization_lane_status: `{payload.get('initialization_lane_status')}`",
                f"- promoted_count: `{payload.get('promoted_count')}`",
                f"- failed_count: `{payload.get('failed_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 initialization live work order.")
    parser.add_argument("--live-summary", default=DEFAULT_LIVE_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_initialization_live_work_order(
        live_summary_path=str(args.live_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"initialization_lane_status": payload.get("initialization_lane_status"), "promoted_count": payload.get("promoted_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
