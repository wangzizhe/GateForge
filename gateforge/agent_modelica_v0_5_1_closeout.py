from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_1_boundary_readiness import build_v051_boundary_readiness
from .agent_modelica_v0_5_1_boundary_taxonomy import build_v051_boundary_taxonomy
from .agent_modelica_v0_5_1_case_classification import build_v051_case_classification
from .agent_modelica_v0_5_1_common import (
    DEFAULT_CLASSIFICATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_INTEGRITY_OUT_DIR,
    DEFAULT_READINESS_OUT_DIR,
    DEFAULT_TAXONOMY_OUT_DIR,
    DEFAULT_V050_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_1_frozen_slice_integrity import build_v051_frozen_slice_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v051_closeout(
    *,
    v0_5_0_closeout_path: str = str(DEFAULT_V050_CLOSEOUT_PATH),
    frozen_slice_integrity_path: str = str(DEFAULT_INTEGRITY_OUT_DIR / "summary.json"),
    boundary_taxonomy_path: str = str(DEFAULT_TAXONOMY_OUT_DIR / "summary.json"),
    case_classification_path: str = str(DEFAULT_CLASSIFICATION_OUT_DIR / "summary.json"),
    boundary_readiness_path: str = str(DEFAULT_READINESS_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(frozen_slice_integrity_path).exists():
        build_v051_frozen_slice_integrity(v0_5_0_closeout_path=v0_5_0_closeout_path, out_dir=str(Path(frozen_slice_integrity_path).parent))
    if not Path(boundary_taxonomy_path).exists():
        build_v051_boundary_taxonomy(out_dir=str(Path(boundary_taxonomy_path).parent))
    if not Path(case_classification_path).exists():
        build_v051_case_classification(
            v0_5_0_closeout_path=str(v0_5_0_closeout_path),
            frozen_slice_integrity_path=str(frozen_slice_integrity_path),
            boundary_taxonomy_path=str(boundary_taxonomy_path),
            out_dir=str(Path(case_classification_path).parent),
        )
    if not Path(boundary_readiness_path).exists():
        build_v051_boundary_readiness(
            v0_5_0_closeout_path=str(v0_5_0_closeout_path),
            case_classification_path=str(case_classification_path),
            out_dir=str(Path(boundary_readiness_path).parent),
        )

    integrity = load_json(frozen_slice_integrity_path)
    taxonomy = load_json(boundary_taxonomy_path)
    classification = load_json(case_classification_path)
    readiness = load_json(boundary_readiness_path)

    if not bool(integrity.get("frozen_slice_integrity_ok")):
        version_decision = "v0_5_1_boundary_map_not_ready"
        boundary_map_status = "not_ready"
        handoff_mode = "run_broader_real_validation_with_boundary_map"
    elif bool(readiness.get("boundary_map_ready")):
        version_decision = "v0_5_1_boundary_map_ready"
        boundary_map_status = "ready"
        handoff_mode = (
            "run_targeted_expansion_on_bounded_uncovered_slice"
            if float(readiness.get("bounded_uncovered_case_share_pct") or 0.0) >= 15.0
            else "run_broader_real_validation_with_boundary_map"
        )
    elif str(integrity.get("dispatch_cleanliness_level") or "") == "promoted":
        version_decision = "v0_5_1_boundary_map_partial"
        boundary_map_status = "partial"
        handoff_mode = "repair_boundary_taxonomy_or_classification_noise_first"
    else:
        version_decision = "v0_5_1_boundary_map_not_ready"
        boundary_map_status = "not_ready"
        handoff_mode = "run_broader_real_validation_with_boundary_map"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_5_1_BOUNDARY_MAP_SYNTHESIS_READY",
        "conclusion": {
            "version_decision": version_decision,
            "boundary_map_status": boundary_map_status,
            "covered_region_stability": readiness.get("covered_region_stable"),
            "bounded_uncovered_signal_present": readiness.get("bounded_uncovered_signal_present"),
            "open_world_spillover_signal_present": readiness.get("open_world_spillover_signal_present"),
            "v0_5_2_handoff_mode": handoff_mode,
            "v0_5_2_primary_eval_question": "Given the first widened boundary map, should the next step validate the map on a broader slice, target a recurring bounded uncovered slice, or first repair classification noise?",
        },
        "frozen_slice_integrity": integrity,
        "boundary_taxonomy": taxonomy,
        "case_classification": classification,
        "boundary_readiness": readiness,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.1 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- boundary_map_status: `{boundary_map_status}`",
                f"- v0_5_2_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.1 capability-boundary map closeout.")
    parser.add_argument("--v0-5-0-closeout", default=str(DEFAULT_V050_CLOSEOUT_PATH))
    parser.add_argument("--frozen-slice-integrity", default=str(DEFAULT_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--boundary-taxonomy", default=str(DEFAULT_TAXONOMY_OUT_DIR / "summary.json"))
    parser.add_argument("--case-classification", default=str(DEFAULT_CLASSIFICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--boundary-readiness", default=str(DEFAULT_READINESS_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v051_closeout(
        v0_5_0_closeout_path=str(args.v0_5_0_closeout),
        frozen_slice_integrity_path=str(args.frozen_slice_integrity),
        boundary_taxonomy_path=str(args.boundary_taxonomy),
        case_classification_path=str(args.case_classification),
        boundary_readiness_path=str(args.boundary_readiness),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
