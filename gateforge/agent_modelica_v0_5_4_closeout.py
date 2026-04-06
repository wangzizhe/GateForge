from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_4_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DISCOVERY_TASKSET_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_RESIDUAL_EVIDENCE_OUT_DIR,
    DEFAULT_V053_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    TARGET_ENTRY_PATTERN_ID,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_4_discovery_adjudication import build_v054_discovery_adjudication
from .agent_modelica_v0_5_4_discovery_probe_taskset import build_v054_discovery_probe_taskset
from .agent_modelica_v0_5_4_handoff_integrity import build_v054_handoff_integrity
from .agent_modelica_v0_5_4_residual_exposure import build_v054_residual_exposure


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v054_closeout(
    *,
    v0_5_3_closeout_path: str = str(DEFAULT_V053_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    discovery_probe_taskset_path: str = str(DEFAULT_DISCOVERY_TASKSET_OUT_DIR / "summary.json"),
    residual_exposure_path: str = str(DEFAULT_RESIDUAL_EVIDENCE_OUT_DIR / "summary.json"),
    adjudication_path: str = str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
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
    if not Path(adjudication_path).exists():
        build_v054_discovery_adjudication(
            v0_5_3_closeout_path=v0_5_3_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            discovery_probe_taskset_path=str(discovery_probe_taskset_path),
            residual_exposure_path=str(residual_exposure_path),
            out_dir=str(Path(adjudication_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    taskset = load_json(discovery_probe_taskset_path)
    evidence = load_json(residual_exposure_path)
    adjudication = load_json(adjudication_path)

    if not bool(integrity.get("handoff_integrity_ok")):
        version_decision = "v0_5_4_handoff_substrate_invalid"
        status = "not_ready"
        handoff_mode = "return_to_boundary_mapping_for_reassessment"
    elif bool(adjudication.get("discovery_ready")):
        version_decision = "v0_5_4_targeted_expansion_discovery_ready"
        status = "discovery_ready"
        handoff_mode = "run_widened_confirmation_on_targeted_expansion"
    elif bool(taskset.get("discovery_probe_taskset_frozen")):
        version_decision = "v0_5_4_targeted_expansion_partial"
        status = "partial"
        handoff_mode = "repair_targeted_expansion_discovery_gaps_first"
    else:
        version_decision = "v0_5_4_targeted_expansion_not_ready"
        status = "not_ready"
        handoff_mode = "return_to_boundary_mapping_for_reassessment"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_5_4_TARGETED_EXPANSION_DISCOVERY_READY",
        "conclusion": {
            "version_decision": version_decision,
            "targeted_expansion_discovery_status": status,
            "entry_pattern_id": TARGET_ENTRY_PATTERN_ID,
            "discovery_ready": adjudication.get("discovery_ready"),
            "v0_5_5_handoff_mode": handoff_mode,
            "v0_5_5_primary_eval_question": "Given the now-bounded discovery probe, can the next version confirm this targeted expansion on a wider slice without losing interpretability or boundedness?",
        },
        "handoff_integrity": integrity,
        "discovery_probe_taskset": taskset,
        "residual_exposure": evidence,
        "discovery_adjudication": adjudication,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.4 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- targeted_expansion_discovery_status: `{status}`",
                f"- v0_5_5_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.4 targeted-expansion discovery closeout.")
    parser.add_argument("--v0-5-3-closeout", default=str(DEFAULT_V053_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--discovery-probe-taskset", default=str(DEFAULT_DISCOVERY_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--residual-exposure", default=str(DEFAULT_RESIDUAL_EVIDENCE_OUT_DIR / "summary.json"))
    parser.add_argument("--adjudication", default=str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v054_closeout(
        v0_5_3_closeout_path=str(args.v0_5_3_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        discovery_probe_taskset_path=str(args.discovery_probe_taskset),
        residual_exposure_path=str(args.residual_exposure),
        adjudication_path=str(args.adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
