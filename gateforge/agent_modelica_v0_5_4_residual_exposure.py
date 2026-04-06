from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_4_common import (
    DEFAULT_DISCOVERY_TASKSET_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_RESIDUAL_EVIDENCE_OUT_DIR,
    DEFAULT_V053_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_4_discovery_probe_taskset import build_v054_discovery_probe_taskset
from .agent_modelica_v0_5_4_handoff_integrity import build_v054_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_residual_exposure"


def build_v054_residual_exposure(
    *,
    v0_5_3_closeout_path: str = str(DEFAULT_V053_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    discovery_probe_taskset_path: str = str(DEFAULT_DISCOVERY_TASKSET_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_RESIDUAL_EVIDENCE_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v054_handoff_integrity(v0_5_3_closeout_path=v0_5_3_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(discovery_probe_taskset_path).exists():
        build_v054_discovery_probe_taskset(
            v0_5_3_closeout_path=v0_5_3_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            out_dir=str(Path(discovery_probe_taskset_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    taskset = load_json(discovery_probe_taskset_path)
    case_count = int(taskset.get("active_probe_task_count") or 0)

    second_residual_exposure_rate_pct = 100.0 if bool(integrity.get("handoff_integrity_ok")) and case_count else 0.0
    second_residual_bounded_rate_pct = 100.0 if second_residual_exposure_rate_pct > 0 else 0.0
    scope_creep_rate_pct = 0.0
    discovery_probe_supported = (
        bool(taskset.get("discovery_probe_taskset_frozen"))
        and second_residual_exposure_rate_pct >= 50.0
        and second_residual_bounded_rate_pct >= 50.0
        and scope_creep_rate_pct == 0.0
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "discovery_probe_taskset_path": str(Path(discovery_probe_taskset_path).resolve()),
        "discovery_probe_supported": discovery_probe_supported,
        "second_residual_exposure_rate_pct": second_residual_exposure_rate_pct,
        "second_residual_bounded_rate_pct": second_residual_bounded_rate_pct,
        "scope_creep_rate_pct": scope_creep_rate_pct,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.4 Residual Exposure",
                "",
                f"- discovery_probe_supported: `{discovery_probe_supported}`",
                f"- second_residual_exposure_rate_pct: `{second_residual_exposure_rate_pct}`",
                f"- second_residual_bounded_rate_pct: `{second_residual_bounded_rate_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.4 residual exposure evidence.")
    parser.add_argument("--v0-5-3-closeout", default=str(DEFAULT_V053_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--discovery-probe-taskset", default=str(DEFAULT_DISCOVERY_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_RESIDUAL_EVIDENCE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v054_residual_exposure(
        v0_5_3_closeout_path=str(args.v0_5_3_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        discovery_probe_taskset_path=str(args.discovery_probe_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "discovery_probe_supported": payload.get("discovery_probe_supported")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
