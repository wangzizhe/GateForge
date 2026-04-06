from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_4_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
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
from .agent_modelica_v0_5_4_residual_exposure import build_v054_residual_exposure


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_discovery_adjudication"


def build_v054_discovery_adjudication(
    *,
    v0_5_3_closeout_path: str = str(DEFAULT_V053_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    discovery_probe_taskset_path: str = str(DEFAULT_DISCOVERY_TASKSET_OUT_DIR / "summary.json"),
    residual_exposure_path: str = str(DEFAULT_RESIDUAL_EVIDENCE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ADJUDICATION_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v054_handoff_integrity(v0_5_3_closeout_path=v0_5_3_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(discovery_probe_taskset_path).exists():
        build_v054_discovery_probe_taskset(
            v0_5_3_closeout_path=v0_5_3_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            out_dir=str(Path(discovery_probe_taskset_path).parent),
        )
    if not Path(residual_exposure_path).exists():
        build_v054_residual_exposure(
            v0_5_3_closeout_path=v0_5_3_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            discovery_probe_taskset_path=str(discovery_probe_taskset_path),
            out_dir=str(Path(residual_exposure_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    taskset = load_json(discovery_probe_taskset_path)
    evidence = load_json(residual_exposure_path)

    handoff_integrity_ok = bool(integrity.get("handoff_integrity_ok"))
    discovery_probe_taskset_frozen = bool(taskset.get("discovery_probe_taskset_frozen"))
    discovery_probe_supported = bool(evidence.get("discovery_probe_supported"))
    scope_creep_rate_pct = float(evidence.get("scope_creep_rate_pct") or 0.0)
    discovery_ready = handoff_integrity_ok and discovery_probe_taskset_frozen and discovery_probe_supported and scope_creep_rate_pct == 0.0

    support_gap_table = []
    if not handoff_integrity_ok:
        support_gap_table.append("handoff_integrity_not_ok")
    if not discovery_probe_taskset_frozen:
        support_gap_table.append("discovery_probe_taskset_not_frozen")
    if not discovery_probe_supported:
        support_gap_table.append("discovery_probe_not_supported")
    if scope_creep_rate_pct != 0.0:
        support_gap_table.append("scope_creep_detected")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "handoff_integrity_path": str(Path(handoff_integrity_path).resolve()),
        "discovery_probe_taskset_path": str(Path(discovery_probe_taskset_path).resolve()),
        "residual_exposure_path": str(Path(residual_exposure_path).resolve()),
        "discovery_ready": discovery_ready,
        "support_gap_table": support_gap_table,
        "residual_interpretation": {
            "primary_residual_factor": (
                "After the first bounded redeclare fix, the next residual still presents as a local medium-redeclare pressure rather than a topology-heavy spillover."
                if discovery_ready
                else "Residual exposure or boundedness remains insufficient to support a clean discovery claim."
            ),
            "residual_stays_bounded": scope_creep_rate_pct == 0.0 and bool(evidence.get("second_residual_bounded_rate_pct", 0.0) >= 50.0),
        },
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.4 Discovery Adjudication",
                "",
                f"- discovery_ready: `{discovery_ready}`",
                f"- support_gap_table: `{', '.join(support_gap_table) if support_gap_table else 'none'}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.4 discovery adjudication.")
    parser.add_argument("--v0-5-3-closeout", default=str(DEFAULT_V053_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--discovery-probe-taskset", default=str(DEFAULT_DISCOVERY_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--residual-exposure", default=str(DEFAULT_RESIDUAL_EVIDENCE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v054_discovery_adjudication(
        v0_5_3_closeout_path=str(args.v0_5_3_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        discovery_probe_taskset_path=str(args.discovery_probe_taskset),
        residual_exposure_path=str(args.residual_exposure),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "discovery_ready": payload.get("discovery_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
