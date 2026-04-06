from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_5_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V062_CLOSEOUT_PATH,
    DEFAULT_V064_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def _conclusion(payload: dict) -> dict:
    return payload.get("conclusion") if isinstance(payload.get("conclusion"), dict) else {}


def build_v065_handoff_integrity(
    *,
    v062_closeout_path: str = str(DEFAULT_V062_CLOSEOUT_PATH),
    v064_closeout_path: str = str(DEFAULT_V064_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v062 = load_json(v062_closeout_path)
    v064 = load_json(v064_closeout_path)
    c062 = _conclusion(v062)
    c064 = _conclusion(v064)

    upstream_chain_integrity_ok = (
        c062.get("version_decision") == "v0_6_2_authority_profile_stable"
        and c064.get("version_decision") == "v0_6_4_phase_decision_input_partial"
    )
    near_miss_integrity_ok = (
        c064.get("near_miss_open_world_candidate") is True
        and c064.get("fluid_network_extension_blocking_open_world") is False
    )
    representative_logic_preserved = bool(c064.get("do_not_reopen_v0_5_boundary_pressure_by_default"))

    status = "PASS" if upstream_chain_integrity_ok and near_miss_integrity_ok and representative_logic_preserved else "FAIL"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": status,
        "upstream_chain_integrity_ok": upstream_chain_integrity_ok,
        "near_miss_integrity_ok": near_miss_integrity_ok,
        "representative_logic_preserved": representative_logic_preserved,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.5 Handoff Integrity",
                "",
                f"- upstream_chain_integrity_ok: `{upstream_chain_integrity_ok}`",
                f"- near_miss_integrity_ok: `{near_miss_integrity_ok}`",
                f"- representative_logic_preserved: `{representative_logic_preserved}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.5 handoff integrity gate.")
    parser.add_argument("--v062-closeout", default=str(DEFAULT_V062_CLOSEOUT_PATH))
    parser.add_argument("--v064-closeout", default=str(DEFAULT_V064_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v065_handoff_integrity(
        v062_closeout_path=str(args.v062_closeout),
        v064_closeout_path=str(args.v064_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "near_miss_integrity_ok": payload.get("near_miss_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
