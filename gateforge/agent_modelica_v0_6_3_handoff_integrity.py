from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_3_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V062_CLOSEOUT_PATH,
    DEFAULT_V062_PROFILE_STABILITY_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def build_v063_handoff_integrity(
    *,
    v062_closeout_path: str = str(DEFAULT_V062_CLOSEOUT_PATH),
    profile_stability_path: str = str(DEFAULT_V062_PROFILE_STABILITY_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v062_closeout_path)
    stability = load_json(profile_stability_path)

    conclusion = closeout.get("conclusion") or {}
    harness_integrity_ok = (
        conclusion.get("version_decision") == "v0_6_2_authority_profile_stable"
        and conclusion.get("profile_stability_status") == "stable"
        and conclusion.get("primary_profile_gap") == "none"
        and bool(conclusion.get("do_not_reopen_v0_5_boundary_pressure_by_default"))
    )
    profile_integrity_ok = bool(stability.get("status") == "PASS") and stability.get("profile_stability_status") == "stable"
    taxonomy_integrity_ok = bool(stability.get("legacy_taxonomy_still_sufficient"))
    extension_status_integrity_ok = str(
        conclusion.get("fluid_network_extension_status_under_representative_pressure") or ""
    ) in {"stable", "fragile_but_real"}
    overall_ok = all(
        [
            harness_integrity_ok,
            profile_integrity_ok,
            taxonomy_integrity_ok,
            extension_status_integrity_ok,
        ]
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if overall_ok else "FAIL",
        "harness_integrity_ok": harness_integrity_ok,
        "profile_integrity_ok": profile_integrity_ok,
        "taxonomy_integrity_ok": taxonomy_integrity_ok,
        "extension_status_integrity_ok": extension_status_integrity_ok,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.3 Handoff Integrity",
                "",
                f"- harness_integrity_ok: `{harness_integrity_ok}`",
                f"- profile_integrity_ok: `{profile_integrity_ok}`",
                f"- taxonomy_integrity_ok: `{taxonomy_integrity_ok}`",
                f"- extension_status_integrity_ok: `{extension_status_integrity_ok}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.3 handoff integrity check.")
    parser.add_argument("--v062-closeout", default=str(DEFAULT_V062_CLOSEOUT_PATH))
    parser.add_argument("--profile-stability", default=str(DEFAULT_V062_PROFILE_STABILITY_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v063_handoff_integrity(
        v062_closeout_path=str(args.v062_closeout),
        profile_stability_path=str(args.profile_stability),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "harness_integrity_ok": payload.get("harness_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
