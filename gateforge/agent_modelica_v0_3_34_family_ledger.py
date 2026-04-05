from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_34_common import (
    DEFAULT_FAMILY_LEDGER_OUT_DIR,
    DEFAULT_V0322_CLOSEOUT_PATH,
    DEFAULT_V0328_CLOSEOUT_PATH,
    DEFAULT_V0331_CLOSEOUT_PATH,
    DEFAULT_V0333_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    conclusion_of,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_family_ledger"


def _family_entry_component_api(v0322: dict, path: str) -> dict:
    conclusion = conclusion_of(v0322)
    decision = norm(conclusion.get("version_decision"))
    return {
        "family_id": "component_api_alignment",
        "anchor_closeout_path": str(Path(path).resolve()),
        "version_decision": decision,
        "maturity_level": "widened_coverage_ready" if decision == "stage2_api_discovery_coverage_ready" else "not_ready",
        "authority_confidence": "supported_by_coverage_ready" if decision == "stage2_api_discovery_coverage_ready" else "insufficient",
        "stage_scope": "stage_2",
        "bounded_target_slice": "local_api_surface_symbol_alignment",
        "family_ready": decision == "stage2_api_discovery_coverage_ready",
    }


def _family_entry_local_interface(v0328: dict, path: str) -> dict:
    conclusion = conclusion_of(v0328)
    decision = norm(conclusion.get("version_decision"))
    authority = norm(conclusion.get("authority_confidence"))
    return {
        "family_id": "local_interface_alignment",
        "anchor_closeout_path": str(Path(path).resolve()),
        "version_decision": decision,
        "maturity_level": "neighbor_component_widened_supported"
        if decision == "stage2_neighbor_component_local_interface_discovery_coverage_ready" and authority == "supported"
        else "not_ready",
        "authority_confidence": authority or "unknown",
        "stage_scope": "stage_2",
        "bounded_target_slice": "local_and_neighbor_component_interface_endpoint_alignment",
        "family_ready": decision == "stage2_neighbor_component_local_interface_discovery_coverage_ready" and authority == "supported",
    }


def _family_entry_medium_redeclare(v0331: dict, v0333: dict, path: str) -> dict:
    conclusion = conclusion_of(v0333)
    v0331_conclusion = conclusion_of(v0331)
    decision = norm(conclusion.get("version_decision"))
    recomposition = norm(conclusion.get("third_family_recomposition_status"))
    authority = norm(conclusion.get("pipe_slice_authority_confidence"))
    return {
        "family_id": "medium_redeclare_alignment",
        "anchor_closeout_path": str(Path(path).resolve()),
        "version_decision": decision,
        "maturity_level": "full_widened_authority_ready"
        if decision == "stage2_medium_redeclare_pipe_slice_coverage_ready" and recomposition == "full_widened_authority_ready"
        else "not_ready",
        "authority_confidence": authority or norm(v0331_conclusion.get("authority_confidence")) or "unknown",
        "stage_scope": "stage_2",
        "bounded_target_slice": "local_medium_redeclare_alignment",
        "third_family_recomposition_status": recomposition,
        "v0331_cross_reference": str(DEFAULT_V0331_CLOSEOUT_PATH.resolve()),
        "family_ready": decision == "stage2_medium_redeclare_pipe_slice_coverage_ready" and recomposition == "full_widened_authority_ready",
    }


def build_v0334_family_ledger(
    *,
    v0322_closeout_path: str = str(DEFAULT_V0322_CLOSEOUT_PATH),
    v0328_closeout_path: str = str(DEFAULT_V0328_CLOSEOUT_PATH),
    v0331_closeout_path: str = str(DEFAULT_V0331_CLOSEOUT_PATH),
    v0333_closeout_path: str = str(DEFAULT_V0333_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_FAMILY_LEDGER_OUT_DIR),
) -> dict:
    v0322 = load_json(v0322_closeout_path)
    v0328 = load_json(v0328_closeout_path)
    v0331 = load_json(v0331_closeout_path)
    v0333 = load_json(v0333_closeout_path)

    families = [
        _family_entry_component_api(v0322, v0322_closeout_path),
        _family_entry_local_interface(v0328, v0328_closeout_path),
        _family_entry_medium_redeclare(v0331, v0333, v0333_closeout_path),
    ]
    ready_families = [row for row in families if bool(row.get("family_ready"))]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "family_anchor_count": len(families),
        "ready_family_anchor_count": len(ready_families),
        "all_families_ready": len(ready_families) == 3,
        "family_ready_levels": {str(row.get("family_id")): str(row.get("maturity_level")) for row in families},
        "family_authority_confidence": {str(row.get("family_id")): str(row.get("authority_confidence")) for row in families},
        "families": families,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.34 Family Ledger",
                "",
                f"- family_anchor_count: `{payload.get('family_anchor_count')}`",
                f"- ready_family_anchor_count: `{payload.get('ready_family_anchor_count')}`",
                f"- all_families_ready: `{payload.get('all_families_ready')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.34 family ledger.")
    parser.add_argument("--v0322-closeout", default=str(DEFAULT_V0322_CLOSEOUT_PATH))
    parser.add_argument("--v0328-closeout", default=str(DEFAULT_V0328_CLOSEOUT_PATH))
    parser.add_argument("--v0331-closeout", default=str(DEFAULT_V0331_CLOSEOUT_PATH))
    parser.add_argument("--v0333-closeout", default=str(DEFAULT_V0333_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_FAMILY_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0334_family_ledger(
        v0322_closeout_path=str(args.v0322_closeout),
        v0328_closeout_path=str(args.v0328_closeout),
        v0331_closeout_path=str(args.v0331_closeout),
        v0333_closeout_path=str(args.v0333_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "family_anchor_count": payload.get("family_anchor_count"), "all_families_ready": payload.get("all_families_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
