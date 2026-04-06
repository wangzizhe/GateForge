from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_6_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V062_CLOSEOUT_PATH,
    DEFAULT_V064_CLOSEOUT_PATH,
    DEFAULT_V065_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def _conclusion(payload: dict) -> dict:
    return payload.get("conclusion") if isinstance(payload.get("conclusion"), dict) else {}


def build_v066_handoff_integrity(
    *,
    v062_closeout_path: str = str(DEFAULT_V062_CLOSEOUT_PATH),
    v064_closeout_path: str = str(DEFAULT_V064_CLOSEOUT_PATH),
    v065_closeout_path: str = str(DEFAULT_V065_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v062 = load_json(v062_closeout_path)
    v064 = load_json(v064_closeout_path)
    v065 = load_json(v065_closeout_path)

    c062 = _conclusion(v062)
    c064 = _conclusion(v064)
    c065 = _conclusion(v065)

    upstream_chain_integrity_ok = (
        c062.get("version_decision") == "v0_6_2_authority_profile_stable"
        and c064.get("version_decision") == "v0_6_4_phase_decision_input_partial"
        and c065.get("version_decision") == "v0_6_5_phase_decision_partial"
    )
    single_gap_integrity_ok = (
        c065.get("dominant_remaining_authority_gap") == "complex_tier_pressure_under_representative_logic"
        and c065.get("fluid_network_still_not_blocking") is True
    )
    representative_logic_preserved = bool(c065.get("do_not_reopen_v0_5_boundary_pressure_by_default"))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if upstream_chain_integrity_ok and single_gap_integrity_ok and representative_logic_preserved else "FAIL",
        "upstream_chain_integrity_ok": upstream_chain_integrity_ok,
        "single_gap_integrity_ok": single_gap_integrity_ok,
        "representative_logic_preserved": representative_logic_preserved,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.6 Handoff Integrity",
                "",
                f"- upstream_chain_integrity_ok: `{upstream_chain_integrity_ok}`",
                f"- single_gap_integrity_ok: `{single_gap_integrity_ok}`",
                f"- representative_logic_preserved: `{representative_logic_preserved}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.6 handoff integrity gate.")
    parser.add_argument("--v062-closeout", default=str(DEFAULT_V062_CLOSEOUT_PATH))
    parser.add_argument("--v064-closeout", default=str(DEFAULT_V064_CLOSEOUT_PATH))
    parser.add_argument("--v065-closeout", default=str(DEFAULT_V065_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v066_handoff_integrity(
        v062_closeout_path=str(args.v062_closeout),
        v064_closeout_path=str(args.v064_closeout),
        v065_closeout_path=str(args.v065_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "single_gap_integrity_ok": payload.get("single_gap_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
