from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_initialization_work_order"
DEFAULT_SOURCE_SUMMARY = "artifacts/agent_modelica_v0_3_13_initialization_generation_source_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_initialization_work_order"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def build_initialization_work_order(
    *,
    source_summary_path: str = DEFAULT_SOURCE_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    source_summary = _load_json(source_summary_path)
    preview_queue_count = int(source_summary.get("preview_queue_count") or 0)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "initialization_lane_status": "SEED_ONLY_NO_EXPANSION_HEADROOM" if preview_queue_count == 0 else "EXPANSION_CANDIDATES_PRESENT",
        "source_count": int(source_summary.get("source_count") or 0),
        "validated_seed_count": int((source_summary.get("target_status_counts") or {}).get("validated_initialization_seed") or 0),
        "preview_queue_count": preview_queue_count,
        "next_actions": [
            "Preserve the four audited initialization seeds as the current authority lane.",
            "Do not spend budget on synthetic initialization expansion until new source models expose more than one viable initial-equation target.",
            "Design a new initialization family around multi-assignment initial equation blocks or a second hidden-base operator beyond init_equation_sign_flip.",
        ],
        "evidence": {
            "source_summary_path": str(Path(source_summary_path).resolve()) if Path(source_summary_path).exists() else str(source_summary_path),
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.13 Initialization Work Order",
                "",
                f"- initialization_lane_status: `{payload.get('initialization_lane_status')}`",
                f"- validated_seed_count: `{payload.get('validated_seed_count')}`",
                f"- preview_queue_count: `{payload.get('preview_queue_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 initialization work order.")
    parser.add_argument("--source-summary", default=DEFAULT_SOURCE_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_initialization_work_order(
        source_summary_path=str(args.source_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"initialization_lane_status": payload.get("initialization_lane_status"), "preview_queue_count": payload.get("preview_queue_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
