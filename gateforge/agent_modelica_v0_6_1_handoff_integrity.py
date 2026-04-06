from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V060_CLASSIFICATION_PATH,
    DEFAULT_V060_CLOSEOUT_PATH,
    DEFAULT_V060_DISPATCH_PATH,
    DEFAULT_V060_SUBSTRATE_PATH,
    LIVE_RUN_CASE_COUNT_REQUIRED,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def build_v061_handoff_integrity(
    *,
    v060_closeout_path: str = str(DEFAULT_V060_CLOSEOUT_PATH),
    substrate_path: str = str(DEFAULT_V060_SUBSTRATE_PATH),
    dispatch_path: str = str(DEFAULT_V060_DISPATCH_PATH),
    classification_path: str = str(DEFAULT_V060_CLASSIFICATION_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v060_closeout_path)
    substrate = load_json(substrate_path)
    dispatch = load_json(dispatch_path)
    classification = load_json(classification_path)

    conclusion = closeout.get("conclusion") or {}
    harness_integrity_ok = (
        conclusion.get("version_decision") == "v0_6_0_representative_substrate_ready"
        and conclusion.get("representative_authority_admission") == "ready"
        and bool(conclusion.get("can_enter_broader_authority_profile"))
        and bool(conclusion.get("do_not_revert_to_v0_5_boundary_pressure_by_default"))
    )
    representative_slice_integrity_ok = (
        bool(substrate.get("representative_slice_frozen"))
        and int(substrate.get("case_count") or 0) == LIVE_RUN_CASE_COUNT_REQUIRED
    )
    dispatch_gate_integrity_ok = (
        dispatch.get("dispatch_cleanliness_level") == "promoted"
        and bool(dispatch.get("policy_baseline_valid"))
    )
    legacy_mapping_integrity_ok = float(classification.get("legacy_bucket_mapping_rate_pct") or 0.0) >= 60.0
    overall_ok = all(
        [
            harness_integrity_ok,
            representative_slice_integrity_ok,
            dispatch_gate_integrity_ok,
            legacy_mapping_integrity_ok,
        ]
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if overall_ok else "FAIL",
        "harness_integrity_ok": harness_integrity_ok,
        "representative_slice_integrity_ok": representative_slice_integrity_ok,
        "dispatch_gate_integrity_ok": dispatch_gate_integrity_ok,
        "legacy_mapping_integrity_ok": legacy_mapping_integrity_ok,
        "upstream_closeout_path": str(Path(v060_closeout_path).resolve()),
        "upstream_case_count": substrate.get("case_count"),
        "upstream_dispatch_cleanliness_level": dispatch.get("dispatch_cleanliness_level"),
        "upstream_legacy_bucket_mapping_rate_pct": classification.get("legacy_bucket_mapping_rate_pct"),
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.1 Handoff Integrity",
                "",
                f"- harness_integrity_ok: `{harness_integrity_ok}`",
                f"- representative_slice_integrity_ok: `{representative_slice_integrity_ok}`",
                f"- dispatch_gate_integrity_ok: `{dispatch_gate_integrity_ok}`",
                f"- legacy_mapping_integrity_ok: `{legacy_mapping_integrity_ok}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.1 handoff integrity check.")
    parser.add_argument("--v060-closeout", default=str(DEFAULT_V060_CLOSEOUT_PATH))
    parser.add_argument("--substrate", default=str(DEFAULT_V060_SUBSTRATE_PATH))
    parser.add_argument("--dispatch", default=str(DEFAULT_V060_DISPATCH_PATH))
    parser.add_argument("--classification", default=str(DEFAULT_V060_CLASSIFICATION_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v061_handoff_integrity(
        v060_closeout_path=str(args.v060_closeout),
        substrate_path=str(args.substrate),
        dispatch_path=str(args.dispatch),
        classification_path=str(args.classification),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "harness_integrity_ok": payload.get("harness_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
