from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_3_common import (
    ALLOWED_PATCH_TYPES,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V052_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    TARGET_ENTRY_PATTERN_ID,
    TARGET_FIRST_FAILURE_BUCKET,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def build_v053_handoff_integrity(
    *,
    v0_5_2_closeout_path: str = str(DEFAULT_V052_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v0_5_2_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    entry_spec = closeout.get("entry_spec") if isinstance(closeout.get("entry_spec"), dict) else {}

    entry_pattern_id_confirmed = str(conclusion.get("selected_entry_pattern_id") or "") == TARGET_ENTRY_PATTERN_ID
    patch_contract_frozen = list(entry_spec.get("allowed_patch_types") or []) == ALLOWED_PATCH_TYPES
    anti_rules = entry_spec.get("anti_expansion_boundary_rules") if isinstance(entry_spec.get("anti_expansion_boundary_rules"), list) else []
    anti_expansion_boundary_intact = bool(anti_rules) and any(str(rule or "").strip().lower().startswith("disallow") for rule in anti_rules)
    target_bucket_ok = str(entry_spec.get("target_first_failure_bucket") or "") == TARGET_FIRST_FAILURE_BUCKET
    handoff_integrity_ok = (
        bool(conclusion.get("entry_ready"))
        and entry_pattern_id_confirmed
        and patch_contract_frozen
        and anti_expansion_boundary_intact
        and target_bucket_ok
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "v0_5_2_closeout_path": str(Path(v0_5_2_closeout_path).resolve()),
        "handoff_integrity_ok": handoff_integrity_ok,
        "entry_pattern_id_confirmed": entry_pattern_id_confirmed,
        "patch_contract_frozen": patch_contract_frozen,
        "anti_expansion_boundary_intact": anti_expansion_boundary_intact,
        "target_first_failure_bucket_confirmed": target_bucket_ok,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.3 Handoff Integrity",
                "",
                f"- handoff_integrity_ok: `{handoff_integrity_ok}`",
                f"- entry_pattern_id_confirmed: `{entry_pattern_id_confirmed}`",
                f"- patch_contract_frozen: `{patch_contract_frozen}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.3 handoff integrity check.")
    parser.add_argument("--v0-5-2-closeout", default=str(DEFAULT_V052_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v053_handoff_integrity(v0_5_2_closeout_path=str(args.v0_5_2_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_ok": payload.get("handoff_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
