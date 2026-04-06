from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_2_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V061_CLOSEOUT_PATH,
    DEFAULT_V061_PROFILE_ADJUDICATION_PATH,
    DEFAULT_V061_PROFILE_CLASSIFICATION_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def build_v062_handoff_integrity(
    *,
    v061_closeout_path: str = str(DEFAULT_V061_CLOSEOUT_PATH),
    profile_adjudication_path: str = str(DEFAULT_V061_PROFILE_ADJUDICATION_PATH),
    profile_classification_path: str = str(DEFAULT_V061_PROFILE_CLASSIFICATION_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v061_closeout_path)
    adjudication = load_json(profile_adjudication_path)
    classification = load_json(profile_classification_path)

    conclusion = closeout.get("conclusion") or {}
    harness_integrity_ok = (
        conclusion.get("version_decision") == "v0_6_1_authority_profile_ready"
        and conclusion.get("profile_status") == "ready"
        and conclusion.get("primary_profile_gap") == "none"
        and bool(conclusion.get("do_not_reopen_v0_5_style_boundary_pressure_by_default"))
    )
    profile_integrity_ok = bool(adjudication.get("status") == "PASS") and adjudication.get("profile_status") == "ready"
    dispatch_integrity_ok = adjudication.get("dispatch_cleanliness_level_effective") == "promoted"
    classification_integrity_ok = float(classification.get("legacy_bucket_mapping_rate_pct") or 0.0) >= 80.0
    overall_ok = all(
        [
            harness_integrity_ok,
            profile_integrity_ok,
            dispatch_integrity_ok,
            classification_integrity_ok,
        ]
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if overall_ok else "FAIL",
        "harness_integrity_ok": harness_integrity_ok,
        "profile_integrity_ok": profile_integrity_ok,
        "dispatch_integrity_ok": dispatch_integrity_ok,
        "classification_integrity_ok": classification_integrity_ok,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.2 Handoff Integrity",
                "",
                f"- harness_integrity_ok: `{harness_integrity_ok}`",
                f"- profile_integrity_ok: `{profile_integrity_ok}`",
                f"- dispatch_integrity_ok: `{dispatch_integrity_ok}`",
                f"- classification_integrity_ok: `{classification_integrity_ok}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.2 handoff integrity check.")
    parser.add_argument("--v061-closeout", default=str(DEFAULT_V061_CLOSEOUT_PATH))
    parser.add_argument("--profile-adjudication", default=str(DEFAULT_V061_PROFILE_ADJUDICATION_PATH))
    parser.add_argument("--profile-classification", default=str(DEFAULT_V061_PROFILE_CLASSIFICATION_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v062_handoff_integrity(
        v061_closeout_path=str(args.v061_closeout),
        profile_adjudication_path=str(args.profile_adjudication),
        profile_classification_path=str(args.profile_classification),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "harness_integrity_ok": payload.get("harness_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
