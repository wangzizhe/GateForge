from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_1_common import (
    DEFAULT_INTEGRITY_OUT_DIR,
    DEFAULT_V050_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_frozen_slice_integrity"


def build_v051_frozen_slice_integrity(
    *,
    v0_5_0_closeout_path: str = str(DEFAULT_V050_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v0_5_0_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    dispatch = closeout.get("dispatch_cleanliness_audit") if isinstance(closeout.get("dispatch_cleanliness_audit"), dict) else {}
    pack = closeout.get("candidate_pack") if isinstance(closeout.get("candidate_pack"), dict) else {}

    qualitative_widening_still_present = bool(conclusion.get("qualitative_widening_confirmed"))
    dispatch_cleanliness_level = str(dispatch.get("dispatch_cleanliness_admission") or "")
    frozen_slice_integrity_ok = (
        str(conclusion.get("widened_real_substrate_status") or "") == "ready"
        and qualitative_widening_still_present
        and dispatch_cleanliness_level == "promoted"
        and bool(pack.get("candidate_slice_classification_rules_frozen"))
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if frozen_slice_integrity_ok else "FAIL",
        "v0_5_0_closeout_path": str(Path(v0_5_0_closeout_path).resolve()),
        "frozen_slice_integrity_ok": frozen_slice_integrity_ok,
        "qualitative_widening_still_present": qualitative_widening_still_present,
        "dispatch_cleanliness_level": dispatch_cleanliness_level,
        "slice_recomposition_not_required": frozen_slice_integrity_ok,
        "must_not_enter_boundary_mapping_mainline": dispatch_cleanliness_level != "promoted",
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.1 Frozen Slice Integrity",
                "",
                f"- frozen_slice_integrity_ok: `{frozen_slice_integrity_ok}`",
                f"- qualitative_widening_still_present: `{qualitative_widening_still_present}`",
                f"- dispatch_cleanliness_level: `{dispatch_cleanliness_level}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.1 frozen widened slice integrity check.")
    parser.add_argument("--v0-5-0-closeout", default=str(DEFAULT_V050_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v051_frozen_slice_integrity(
        v0_5_0_closeout_path=str(args.v0_5_0_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "frozen_slice_integrity_ok": payload.get("frozen_slice_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
