from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_0_common import PRIORITY_BARRIERS
from .agent_modelica_v0_9_2_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_EXPANDED_SUBSTRATE_ADMISSION_OUT_DIR,
    DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V091_CLOSEOUT_PATH,
    DEFAULT_V091_POOL_DELTA_PATH,
    MAX_SUBSTRATE_SIZE,
    MIN_SUBSTRATE_SIZE,
    READY_BARRIER_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_2_expanded_substrate_admission import build_v092_expanded_substrate_admission
from .agent_modelica_v0_9_2_expanded_substrate_builder import build_v092_expanded_substrate_builder
from .agent_modelica_v0_9_2_handoff_integrity import build_v092_handoff_integrity


def build_v092_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    expanded_substrate_builder_path: str = str(DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"),
    expanded_substrate_admission_path: str = str(DEFAULT_EXPANDED_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"),
    v091_closeout_path: str = str(DEFAULT_V091_CLOSEOUT_PATH),
    v091_pool_delta_path: str = str(DEFAULT_V091_POOL_DELTA_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    build_v092_handoff_integrity(v091_closeout_path=v091_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_9_2_EXPANDED_SUBSTRATE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_9_2_expanded_substrate_inputs_invalid",
                "expanded_substrate_status": "invalid",
                "v0_9_3_handoff_mode": "rebuild_v0_9_2_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.9.2 Closeout\n\n- version_decision: `v0_9_2_expanded_substrate_inputs_invalid`\n")
        return payload

    if not Path(expanded_substrate_builder_path).exists():
        build_v092_expanded_substrate_builder(
            v091_pool_delta_path=v091_pool_delta_path,
            out_dir=str(Path(expanded_substrate_builder_path).parent),
        )
    builder = load_json(expanded_substrate_builder_path)
    if not Path(expanded_substrate_admission_path).exists():
        build_v092_expanded_substrate_admission(
            expanded_substrate_builder_path=expanded_substrate_builder_path,
            out_dir=str(Path(expanded_substrate_admission_path).parent),
        )
    admission = load_json(expanded_substrate_admission_path)

    size = int(admission.get("expanded_substrate_size") or 0)
    barrier_counts = admission.get("priority_barrier_coverage_table") if isinstance(admission.get("priority_barrier_coverage_table"), dict) else {}
    admission_pass = admission.get("expanded_substrate_admission_status") == "PASS"
    all_barriers_ready = all(int(barrier_counts.get(barrier) or 0) >= READY_BARRIER_MIN for barrier in PRIORITY_BARRIERS)
    no_zero_barrier = all(int(barrier_counts.get(barrier) or 0) > 0 for barrier in PRIORITY_BARRIERS)
    size_in_range = MIN_SUBSTRATE_SIZE <= size <= MAX_SUBSTRATE_SIZE
    family_breadth_ok = bool(admission.get("family_breadth_ok"))
    complexity_breadth_ok = bool(admission.get("complexity_breadth_ok"))
    template_breadth_ok = bool(admission.get("template_breadth_ok"))

    if admission_pass and all_barriers_ready and size_in_range and family_breadth_ok and complexity_breadth_ok and template_breadth_ok:
        version_decision = "v0_9_2_first_expanded_authentic_workflow_substrate_ready"
        substrate_status = "ready"
        handoff_mode = "characterize_expanded_workflow_profile"
        status = "PASS"
    elif admission_pass and no_zero_barrier:
        version_decision = "v0_9_2_first_expanded_authentic_workflow_substrate_partial"
        substrate_status = "partial"
        handoff_mode = "refine_expanded_substrate_composition_before_profile_characterization"
        status = "PASS"
    else:
        version_decision = "v0_9_2_expanded_substrate_inputs_invalid"
        substrate_status = "invalid"
        handoff_mode = "rebuild_v0_9_2_inputs_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "expanded_substrate_status": substrate_status,
            "expanded_substrate_size": size,
            "priority_barrier_coverage_table": barrier_counts,
            "workflow_family_mix": builder.get("workflow_family_mix"),
            "complexity_mix": builder.get("complexity_mix"),
            "workflow_task_template_mix": builder.get("workflow_task_template_mix"),
            "v0_9_3_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "expanded_substrate_builder": builder,
        "expanded_substrate_admission": admission,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.2 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- expanded_substrate_size: `{size}`",
                f"- v0_9_3_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.2 expanded substrate closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--expanded-substrate-builder", default=str(DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"))
    parser.add_argument("--expanded-substrate-admission", default=str(DEFAULT_EXPANDED_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"))
    parser.add_argument("--v091-closeout", default=str(DEFAULT_V091_CLOSEOUT_PATH))
    parser.add_argument("--v091-pool-delta", default=str(DEFAULT_V091_POOL_DELTA_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v092_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        expanded_substrate_builder_path=str(args.expanded_substrate_builder),
        expanded_substrate_admission_path=str(args.expanded_substrate_admission),
        v091_closeout_path=str(args.v091_closeout),
        v091_pool_delta_path=str(args.v091_pool_delta),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
