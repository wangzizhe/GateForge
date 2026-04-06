from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V070_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v071_handoff_integrity(
    *,
    v070_closeout_path: str = str(DEFAULT_V070_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v070 = load_json(v070_closeout_path)
    conclusion = v070.get("conclusion") or {}

    ready_version = conclusion.get("version_decision") == "v0_7_0_open_world_adjacent_substrate_ready"
    ready_admission = conclusion.get("substrate_admission_status") == "ready"
    weaker_curation_confirmed = conclusion.get("weaker_curation_confirmed") is True
    legacy_mapping_ok = float(conclusion.get("legacy_bucket_mapping_rate_pct") or 0.0) >= 70.0
    dispatch_ok = conclusion.get("dispatch_cleanliness_level") == "promoted"
    spillover_ok = float(conclusion.get("spillover_share_pct") or 100.0) <= 20.0

    integrity_ok = all(
        [
            ready_version,
            ready_admission,
            weaker_curation_confirmed,
            legacy_mapping_ok,
            dispatch_ok,
            spillover_ok,
        ]
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if integrity_ok else "FAIL",
        "ready_version": ready_version,
        "ready_admission": ready_admission,
        "weaker_curation_confirmed": weaker_curation_confirmed,
        "legacy_mapping_ok": legacy_mapping_ok,
        "dispatch_ok": dispatch_ok,
        "spillover_ok": spillover_ok,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.1 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- ready_version: `{ready_version}`",
                f"- ready_admission: `{ready_admission}`",
                f"- weaker_curation_confirmed: `{weaker_curation_confirmed}`",
                f"- legacy_mapping_ok: `{legacy_mapping_ok}`",
                f"- dispatch_ok: `{dispatch_ok}`",
                f"- spillover_ok: `{spillover_ok}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.1 handoff integrity summary.")
    parser.add_argument("--v070-closeout", default=str(DEFAULT_V070_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v071_handoff_integrity(
        v070_closeout_path=str(args.v070_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
