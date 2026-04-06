from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_0_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V060_CLOSEOUT_PATH,
    DEFAULT_V061_CLOSEOUT_PATH,
    DEFAULT_V062_CLOSEOUT_PATH,
    DEFAULT_V066_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v070_handoff_integrity(
    *,
    v060_closeout_path: str = str(DEFAULT_V060_CLOSEOUT_PATH),
    v061_closeout_path: str = str(DEFAULT_V061_CLOSEOUT_PATH),
    v062_closeout_path: str = str(DEFAULT_V062_CLOSEOUT_PATH),
    v066_closeout_path: str = str(DEFAULT_V066_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v060 = load_json(v060_closeout_path)
    v061 = load_json(v061_closeout_path)
    v062 = load_json(v062_closeout_path)
    v066 = load_json(v066_closeout_path)

    upstream_chain_integrity_ok = all(
        [
            (v060.get("conclusion") or {}).get("version_decision")
            == "v0_6_0_representative_substrate_ready",
            (v061.get("conclusion") or {}).get("version_decision")
            == "v0_6_1_authority_profile_ready",
            (v062.get("conclusion") or {}).get("version_decision")
            == "v0_6_2_authority_profile_stable",
            (v066.get("conclusion") or {}).get("version_decision")
            == "v0_6_6_phase_closeout_supported",
        ]
    )
    representative_logic_preserved = (
        (v066.get("conclusion") or {}).get("do_not_reopen_v0_5_boundary_pressure_by_default")
        is True
    )
    single_gap_integrity_ok = (
        (v066.get("conclusion") or {}).get("remaining_gap_still_single") is True
    )
    integrity_ok = (
        upstream_chain_integrity_ok
        and representative_logic_preserved
        and single_gap_integrity_ok
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if integrity_ok else "FAIL",
        "upstream_chain_integrity_ok": upstream_chain_integrity_ok,
        "representative_logic_preserved": representative_logic_preserved,
        "single_gap_integrity_ok": single_gap_integrity_ok,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.0 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_chain_integrity_ok: `{upstream_chain_integrity_ok}`",
                f"- representative_logic_preserved: `{representative_logic_preserved}`",
                f"- single_gap_integrity_ok: `{single_gap_integrity_ok}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.0 handoff integrity summary.")
    parser.add_argument("--v060-closeout", default=str(DEFAULT_V060_CLOSEOUT_PATH))
    parser.add_argument("--v061-closeout", default=str(DEFAULT_V061_CLOSEOUT_PATH))
    parser.add_argument("--v062-closeout", default=str(DEFAULT_V062_CLOSEOUT_PATH))
    parser.add_argument("--v066-closeout", default=str(DEFAULT_V066_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v070_handoff_integrity(
        v060_closeout_path=str(args.v060_closeout),
        v061_closeout_path=str(args.v061_closeout),
        v062_closeout_path=str(args.v062_closeout),
        v066_closeout_path=str(args.v066_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
