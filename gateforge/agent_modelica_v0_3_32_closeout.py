from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_32_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DISCOVERY_OUT_DIR,
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_TRIAGE_OUT_DIR,
    DEFAULT_V0331_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    handoff_substrate_valid,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_32_discovery_probe import build_v0332_discovery_probe
from .agent_modelica_v0_3_32_entry_spec import build_v0332_entry_spec
from .agent_modelica_v0_3_32_first_fix_evidence import build_v0332_first_fix_evidence
from .agent_modelica_v0_3_32_pipe_viability_triage import build_v0332_pipe_viability_triage


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0332_closeout(
    *,
    v0331_closeout_path: str = str(DEFAULT_V0331_CLOSEOUT_PATH),
    triage_path: str = str(DEFAULT_TRIAGE_OUT_DIR / "summary.json"),
    entry_spec_path: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    discovery_path: str = str(DEFAULT_DISCOVERY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(triage_path).exists():
        build_v0332_pipe_viability_triage(v0331_closeout_path=v0331_closeout_path, out_dir=str(Path(triage_path).parent))
    if not Path(entry_spec_path).exists():
        build_v0332_entry_spec(triage_path=triage_path, out_dir=str(Path(entry_spec_path).parent))
    if not Path(first_fix_path).exists():
        build_v0332_first_fix_evidence(entry_taskset_path=str(Path(entry_spec_path).parent / "taskset.json"), out_dir=str(Path(first_fix_path).parent))
    if not Path(discovery_path).exists():
        build_v0332_discovery_probe(first_fix_path=first_fix_path, entry_taskset_path=str(Path(entry_spec_path).parent / "taskset.json"), out_dir=str(Path(discovery_path).parent))

    v0331 = load_json(v0331_closeout_path)
    triage = load_json(triage_path)
    entry = load_json(entry_spec_path)
    first_fix = load_json(first_fix_path)
    discovery = load_json(discovery_path)

    if not handoff_substrate_valid(v0331):
        version_decision = "handoff_substrate_invalid"
        pipe_slice_status = "handoff_substrate_invalid"
        next_phase_recommendation = "repair_handoff_substrate"
        handoff_spec = ""
        primary_bottleneck = "handoff_substrate_invalid"
    else:
        entry_ready = (
            norm(entry.get("status")) == "PASS"
            and float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0) >= 80.0
            and float(first_fix.get("patch_applied_rate_pct") or 0.0) >= 70.0
            and float(first_fix.get("signature_advance_rate_pct") or 0.0) >= 50.0
            and float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) <= 10.0
        )
        discovery_ready = (
            entry_ready
            and norm(discovery.get("execution_status")) == "executed"
            and float(discovery.get("candidate_contains_canonical_rate_pct") or 0.0) >= 80.0
            and float(discovery.get("candidate_top1_canonical_rate_pct") or 0.0) >= 70.0
            and float(discovery.get("signature_advance_rate_pct") or 0.0) >= 50.0
        )
        if discovery_ready:
            version_decision = "stage2_medium_redeclare_pipe_slice_discovery_ready"
            pipe_slice_status = "discovery_ready"
            next_phase_recommendation = "widen_pipe_slice_confirmation"
            handoff_spec = str((Path(discovery_path)).resolve())
            primary_bottleneck = "none"
        elif entry_ready:
            version_decision = "stage2_medium_redeclare_pipe_slice_entry_ready"
            pipe_slice_status = "entry_ready"
            next_phase_recommendation = "promote_pipe_slice_discovery"
            handoff_spec = str((Path(entry_spec_path).parent / "taskset.json").resolve())
            primary_bottleneck = "discovery_not_yet_ready"
        else:
            version_decision = "stage2_medium_redeclare_pipe_slice_boundary_rejected"
            pipe_slice_status = "boundary_rejected"
            next_phase_recommendation = "prepare_v0_4_transition"
            handoff_spec = str((Path(out_dir) / "summary.json").resolve())
            if int(triage.get("accepted_pattern_count") or 0) <= 1:
                primary_bottleneck = "pipe_like_entry_triage"
            elif norm(entry.get("status")) != "PASS":
                primary_bottleneck = "entry_construction_feasibility"
            else:
                primary_bottleneck = "first_fix_viability"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_MEDIUM_REDECLARE_PIPE_SLICE_CLOSEOUT_READY",
        "conclusion": {
            "version_decision": version_decision,
            "pipe_slice_status": pipe_slice_status,
            "selected_pipe_patterns": list(triage.get("selected_pipe_patterns") or []),
            "allowed_patch_types": list(entry.get("allowed_patch_types") or []),
            "primary_bottleneck": primary_bottleneck,
            "next_phase_recommendation": next_phase_recommendation,
            "v0_3_33_handoff_spec": handoff_spec,
            "remove_pipe_slice_from_required_subtypes": bool(pipe_slice_status == "boundary_rejected"),
            "roadmap_stop_condition_supported_without_pipe_slice": bool(pipe_slice_status == "boundary_rejected"),
        },
        "triage": triage,
        "entry_spec": entry,
        "first_fix_evidence": first_fix,
        "discovery_probe": discovery,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.32 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- pipe_slice_status: `{(payload.get('conclusion') or {}).get('pipe_slice_status')}`",
                f"- next_phase_recommendation: `{(payload.get('conclusion') or {}).get('next_phase_recommendation')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.32 closeout.")
    parser.add_argument("--v0331-closeout", default=str(DEFAULT_V0331_CLOSEOUT_PATH))
    parser.add_argument("--triage", default=str(DEFAULT_TRIAGE_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-spec", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--discovery", default=str(DEFAULT_DISCOVERY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0332_closeout(
        v0331_closeout_path=str(args.v0331_closeout),
        triage_path=str(args.triage),
        entry_spec_path=str(args.entry_spec),
        first_fix_path=str(args.first_fix),
        discovery_path=str(args.discovery),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
