from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_7_0_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR,
    DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR,
    DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_7_0_handoff_integrity import build_v070_handoff_integrity
from .agent_modelica_v0_7_0_legacy_bucket_audit import build_v070_legacy_bucket_audit
from .agent_modelica_v0_7_0_open_world_adjacent_substrate import (
    build_v070_open_world_adjacent_substrate,
)
from .agent_modelica_v0_7_0_substrate_admission import build_v070_substrate_admission


def build_v070_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    substrate_path: str = str(DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR / "summary.json"),
    audit_path: str = str(DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR / "summary.json"),
    admission_path: str = str(DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v070_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_7_0_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": "v0_7_0_handoff_substrate_invalid",
                "substrate_admission_status": "invalid",
                "weaker_curation_confirmed": None,
                "weaker_curation_metric": None,
                "weaker_curation_metric_vs_v0_6": None,
                "legacy_bucket_mapping_rate_pct": None,
                "dispatch_cleanliness_level": None,
                "spillover_share_pct": None,
                "unclassified_pending_taxonomy_count": None,
                "representativeness_vs_workflow_boundary": None,
                "v0_7_1_handoff_mode": "repair_open_world_adjacent_substrate_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(
            out_root / "summary.md",
            "# v0.7.0 Closeout\n\n- version_decision: `v0_7_0_handoff_substrate_invalid`\n",
        )
        return payload

    if not Path(substrate_path).exists():
        build_v070_open_world_adjacent_substrate(out_dir=str(Path(substrate_path).parent))
    if not Path(audit_path).exists():
        build_v070_legacy_bucket_audit(
            substrate_path=substrate_path,
            out_dir=str(Path(audit_path).parent),
        )
    if not Path(admission_path).exists():
        build_v070_substrate_admission(
            substrate_path=substrate_path,
            audit_path=audit_path,
            out_dir=str(Path(admission_path).parent),
        )

    substrate = load_json(substrate_path)
    audit = load_json(audit_path)
    admission = load_json(admission_path)
    status = str(admission["substrate_admission_status"])
    if status == "ready":
        version_decision = "v0_7_0_open_world_adjacent_substrate_ready"
        handoff = "characterize_readiness_profile_on_frozen_substrate"
    elif status == "partial":
        version_decision = "v0_7_0_open_world_adjacent_substrate_partial"
        handoff = "stabilize_open_world_adjacent_substrate_first"
    else:
        version_decision = "v0_7_0_handoff_substrate_invalid"
        handoff = "repair_open_world_adjacent_substrate_first"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"ready", "partial"} else "FAIL",
        "closeout_status": {
            "ready": "V0_7_0_OPEN_WORLD_ADJACENT_SUBSTRATE_READY",
            "partial": "V0_7_0_OPEN_WORLD_ADJACENT_SUBSTRATE_PARTIAL",
            "invalid": "V0_7_0_HANDOFF_SUBSTRATE_INVALID",
        }[status],
        "conclusion": {
            "version_decision": version_decision,
            "substrate_admission_status": status,
            "weaker_curation_confirmed": substrate["weaker_curation_confirmed"],
            "weaker_curation_metric": substrate["weaker_curation_metric"],
            "weaker_curation_metric_vs_v0_6": substrate["weaker_curation_metric_vs_v0_6"],
            "legacy_bucket_mapping_rate_pct": audit["legacy_bucket_mapping_rate_pct"],
            "dispatch_cleanliness_level": audit["dispatch_cleanliness_level"],
            "spillover_share_pct": audit["spillover_share_pct"],
            "unclassified_pending_taxonomy_count": audit["unclassified_pending_taxonomy_count"],
            "representativeness_vs_workflow_boundary": substrate["representativeness_vs_workflow_boundary"],
            "v0_7_1_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "open_world_adjacent_substrate": substrate,
        "legacy_bucket_audit": audit,
        "substrate_admission": admission,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- substrate_admission_status: `{status}`",
                f"- weaker_curation_metric: `{substrate['weaker_curation_metric']}`",
                f"- legacy_bucket_mapping_rate_pct: `{audit['legacy_bucket_mapping_rate_pct']}`",
                f"- dispatch_cleanliness_level: `{audit['dispatch_cleanliness_level']}`",
                f"- spillover_share_pct: `{audit['spillover_share_pct']}`",
                f"- v0_7_1_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.0 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--substrate-path", default=str(DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR / "summary.json"))
    parser.add_argument("--audit-path", default=str(DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--admission-path", default=str(DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v070_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        substrate_path=str(args.substrate_path),
        audit_path=str(args.audit_path),
        admission_path=str(args.admission_path),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
