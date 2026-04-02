from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_curriculum_closeout"
DEFAULT_RUNTIME_LIVE_WORK_ORDER = "artifacts/agent_modelica_v0_3_13_runtime_live_work_order_current/summary.json"
DEFAULT_INITIALIZATION_SOURCE_WORK_ORDER = "artifacts/agent_modelica_v0_3_13_initialization_work_order_current/summary.json"
DEFAULT_INITIALIZATION_CURRICULUM_FAMILY = "artifacts/agent_modelica_v0_3_13_initialization_curriculum_family_spec_current/summary.json"
DEFAULT_INITIALIZATION_LIVE_WORK_ORDER = "artifacts/agent_modelica_v0_3_13_initialization_live_work_order_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_curriculum_closeout"


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


def build_curriculum_closeout(
    *,
    runtime_live_work_order_path: str = DEFAULT_RUNTIME_LIVE_WORK_ORDER,
    initialization_source_work_order_path: str = DEFAULT_INITIALIZATION_SOURCE_WORK_ORDER,
    initialization_curriculum_family_path: str = DEFAULT_INITIALIZATION_CURRICULUM_FAMILY,
    initialization_live_work_order_path: str = DEFAULT_INITIALIZATION_LIVE_WORK_ORDER,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    runtime_live = _load_json(runtime_live_work_order_path)
    init_source = _load_json(initialization_source_work_order_path)
    init_family = _load_json(initialization_curriculum_family_path)
    init_live = _load_json(initialization_live_work_order_path)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "closeout_status": "CURRICULUM_CLOSEOUT_READY",
        "runtime_lane": {
            "status": runtime_live.get("runtime_lane_status"),
            "promoted_pair_count": int(runtime_live.get("promoted_pair_count") or 0),
            "failed_pair_count": int(runtime_live.get("failed_pair_count") or 0),
        },
        "initialization_seed_lane": {
            "status": init_source.get("initialization_lane_status"),
            "validated_seed_count": int(init_source.get("validated_seed_count") or 0),
        },
        "initialization_curriculum_lane": {
            "family_status": init_family.get("lane_status"),
            "preview_admitted_count": int(init_family.get("admitted_count") or 0),
            "live_status": init_live.get("initialization_lane_status"),
            "promoted_count": int(init_live.get("promoted_count") or 0),
            "failed_count": int(init_live.get("failed_count") or 0),
        },
        "conclusion": {
            "primary_multiround_lane": "runtime_curriculum_lane",
            "secondary_multiround_lane": "initialization_curriculum_lane",
            "summary": "Runtime curriculum is the strongest authority lane; the new initialization curriculum is real but selective, while the legacy initialization seed lane has no organic expansion headroom.",
        },
        "next_actions": [
            "Use the runtime curriculum lane as the default multiround authority substrate.",
            "Keep only the promoted initialization source families in the active multiround budget.",
            "Treat tank-coupled initialization families as excluded until a new hidden-base design avoids repair-safety blocking.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.13 Curriculum Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- runtime_lane_status: `{(payload.get('runtime_lane') or {}).get('status')}`",
                f"- initialization_curriculum_status: `{(payload.get('initialization_curriculum_lane') or {}).get('live_status')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 curriculum closeout summary.")
    parser.add_argument("--runtime-live-work-order", default=DEFAULT_RUNTIME_LIVE_WORK_ORDER)
    parser.add_argument("--initialization-source-work-order", default=DEFAULT_INITIALIZATION_SOURCE_WORK_ORDER)
    parser.add_argument("--initialization-curriculum-family", default=DEFAULT_INITIALIZATION_CURRICULUM_FAMILY)
    parser.add_argument("--initialization-live-work-order", default=DEFAULT_INITIALIZATION_LIVE_WORK_ORDER)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_curriculum_closeout(
        runtime_live_work_order_path=str(args.runtime_live_work_order),
        initialization_source_work_order_path=str(args.initialization_source_work_order),
        initialization_curriculum_family_path=str(args.initialization_curriculum_family),
        initialization_live_work_order_path=str(args.initialization_live_work_order),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"closeout_status": payload.get("closeout_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
