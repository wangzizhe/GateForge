from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_30_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DISCOVERY_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_30_discovery_evidence import build_v0330_discovery_evidence
from .agent_modelica_v0_3_30_dual_recheck import build_v0330_dual_recheck
from .agent_modelica_v0_3_30_first_fix_evidence import build_v0330_first_fix_evidence
from .agent_modelica_v0_3_30_handoff_integrity import build_v0330_handoff_integrity
from .agent_modelica_v0_3_30_surface_index import build_v0330_surface_index


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0330_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    discovery_path: str = str(DEFAULT_DISCOVERY_OUT_DIR / "summary.json"),
    dual_recheck_path: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v0330_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    handoff = load_json(handoff_integrity_path)
    if not Path(surface_index_path).exists():
        build_v0330_surface_index(out_dir=str(Path(surface_index_path).parent))
    if not Path(first_fix_path).exists():
        build_v0330_first_fix_evidence(out_dir=str(Path(first_fix_path).parent))
    if not Path(discovery_path).exists():
        build_v0330_discovery_evidence(out_dir=str(Path(discovery_path).parent))
    if not Path(dual_recheck_path).exists():
        build_v0330_dual_recheck(out_dir=str(Path(dual_recheck_path).parent))

    surface = load_json(surface_index_path)
    first_fix = load_json(first_fix_path)
    discovery = load_json(discovery_path)
    dual = load_json(dual_recheck_path)

    handoff_valid = bool(handoff.get("handoff_substrate_valid"))
    first_fix_ready = (
        float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0) >= 80.0
        and float(first_fix.get("patch_applied_rate_pct") or 0.0) >= 70.0
        and float(first_fix.get("focal_patch_hit_rate_pct") or 0.0) >= 80.0
        and float(first_fix.get("signature_advance_rate_pct") or 0.0) >= 50.0
        and float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) <= 10.0
    )
    discovery_ready = (
        handoff_valid
        and first_fix_ready
        and load_json(discovery_path).get("execution_status") == "executed"
        and float(discovery.get("candidate_contains_canonical_rate_pct") or 0.0) >= 80.0
        and float(discovery.get("candidate_top1_canonical_rate_pct") or 0.0) >= 70.0
        and float(discovery.get("patch_applied_rate_pct") or 0.0) >= 70.0
        and float(discovery.get("signature_advance_rate_pct") or 0.0) >= 50.0
    )
    dual_ready = (
        load_json(dual_recheck_path).get("execution_status") == "executed"
        and float(dual.get("post_first_fix_target_bucket_hit_rate_pct") or 0.0) >= 60.0
        and float(dual.get("second_residual_medium_redeclare_retained_rate_pct") or 0.0) >= 60.0
        and float(dual.get("dual_full_resolution_rate_pct") or 0.0) >= 40.0
    )

    if not handoff_valid:
        version_decision = "handoff_substrate_invalid"
        v031_next = "repair_handoff_substrate"
        v031_handoff_spec = ""
    elif discovery_ready and dual_ready:
        version_decision = "stage2_medium_redeclare_discovery_ready"
        v031_next = "widened_coverage"
        v031_handoff_spec = str(Path(DEFAULT_DISCOVERY_OUT_DIR / "summary.json").resolve())
    elif first_fix_ready:
        version_decision = "stage2_medium_redeclare_first_fix_ready"
        v031_next = "discovery_hardening"
        v031_handoff_spec = str(Path(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json").resolve())
    else:
        version_decision = "stage2_medium_redeclare_family_not_ready"
        v031_next = "first_fix_hardening"
        v031_handoff_spec = str(Path(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json").resolve())

    if not handoff_valid:
        primary_bottleneck = "handoff_substrate_invalid"
    elif not first_fix_ready:
        primary_bottleneck = "first_fix_execution"
    elif norm(discovery.get("execution_status")) != "executed":
        primary_bottleneck = "discovery_gate_blocked"
    elif not discovery_ready:
        if float(discovery.get("candidate_contains_canonical_rate_pct") or 0.0) < 80.0:
            primary_bottleneck = "candidate_source_failure"
        elif float(discovery.get("candidate_top1_canonical_rate_pct") or 0.0) < 70.0:
            primary_bottleneck = "candidate_ranking_failure"
        elif float(discovery.get("patch_applied_rate_pct") or 0.0) < 70.0:
            primary_bottleneck = "patch_application_failure"
        else:
            primary_bottleneck = "signature_advance_failure"
    elif not dual_ready:
        primary_bottleneck = "dual_residual_retention"
    else:
        primary_bottleneck = "none"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_MEDIUM_REDECLARE_CLOSEOUT_READY",
        "handoff_integrity": handoff,
        "surface_index": surface,
        "first_fix_evidence": first_fix,
        "discovery_evidence": discovery,
        "dual_recheck": dual,
        "conclusion": {
            "version_decision": version_decision,
            "first_fix_ready": first_fix_ready,
            "discovery_ready": discovery_ready,
            "dual_residual_ready": dual_ready,
            "primary_bottleneck": primary_bottleneck,
            "v0_3_31_next_mode": v031_next,
            "v0_3_31_handoff_spec": v031_handoff_spec,
            "summary": (
                "The v0.3.29 handoff remains valid and medium_redeclare_alignment now supports bounded first-fix execution plus first-pass local discovery."
                if version_decision == "stage2_medium_redeclare_discovery_ready"
                else (
                    "The handoff and first-fix execution are stable, but bounded medium discovery still needs hardening before widened coverage."
                    if version_decision == "stage2_medium_redeclare_first_fix_ready"
                    else (
                        "The frozen v0.3.29 handoff substrate is invalid and must be repaired before medium-redeclare family capability can be judged."
                        if version_decision == "handoff_substrate_invalid"
                        else "The medium-redeclare third-family entry exists, but first-fix execution is not yet stable enough to promote."
                    )
                )
            ),
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.30 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- v0.3.31_next_mode: `{(payload.get('conclusion') or {}).get('v0_3_31_next_mode')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.30 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--discovery", default=str(DEFAULT_DISCOVERY_OUT_DIR / "summary.json"))
    parser.add_argument("--dual-recheck", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0330_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        surface_index_path=str(args.surface_index),
        first_fix_path=str(args.first_fix),
        discovery_path=str(args.discovery),
        dual_recheck_path=str(args.dual_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
