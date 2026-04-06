from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_4_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V060_CLOSEOUT_PATH,
    DEFAULT_V062_CLOSEOUT_PATH,
    DEFAULT_V063_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def _conclusion(payload: dict) -> dict:
    return payload.get("conclusion") if isinstance(payload.get("conclusion"), dict) else {}


def build_v064_handoff_integrity(
    *,
    v060_closeout_path: str = str(DEFAULT_V060_CLOSEOUT_PATH),
    v062_closeout_path: str = str(DEFAULT_V062_CLOSEOUT_PATH),
    v063_closeout_path: str = str(DEFAULT_V063_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v060 = load_json(v060_closeout_path)
    v062 = load_json(v062_closeout_path)
    v063 = load_json(v063_closeout_path)

    c060 = _conclusion(v060)
    c062 = _conclusion(v062)
    c063 = _conclusion(v063)

    upstream_chain_integrity_ok = (
        c060.get("version_decision") == "v0_6_0_representative_substrate_ready"
        and c062.get("version_decision") == "v0_6_2_authority_profile_stable"
        and c063.get("version_decision") == "v0_6_3_phase_decision_basis_partial"
    )
    representative_logic_preserved = bool(c063.get("do_not_reopen_v0_5_boundary_pressure_by_default"))
    partial_gap_integrity_ok = c063.get("phase_decision_basis_gap") == "neither_candidate_threshold_met"

    integrity_ok = upstream_chain_integrity_ok and representative_logic_preserved and partial_gap_integrity_ok

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if integrity_ok else "FAIL",
        "upstream_chain_integrity_ok": upstream_chain_integrity_ok,
        "representative_logic_preserved": representative_logic_preserved,
        "partial_gap_integrity_ok": partial_gap_integrity_ok,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.4 Handoff Integrity",
                "",
                f"- upstream_chain_integrity_ok: `{upstream_chain_integrity_ok}`",
                f"- representative_logic_preserved: `{representative_logic_preserved}`",
                f"- partial_gap_integrity_ok: `{partial_gap_integrity_ok}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.4 handoff integrity gate.")
    parser.add_argument("--v060-closeout", default=str(DEFAULT_V060_CLOSEOUT_PATH))
    parser.add_argument("--v062-closeout", default=str(DEFAULT_V062_CLOSEOUT_PATH))
    parser.add_argument("--v063-closeout", default=str(DEFAULT_V063_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v064_handoff_integrity(
        v060_closeout_path=str(args.v060_closeout),
        v062_closeout_path=str(args.v062_closeout),
        v063_closeout_path=str(args.v063_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "upstream_chain_integrity_ok": payload.get("upstream_chain_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
