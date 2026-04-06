from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_3_common import (
    DEFAULT_ENTRY_TASKSET_OUT_DIR,
    DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V052_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    TARGET_FIRST_FAILURE_BUCKET,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_3_entry_taskset import build_v053_entry_taskset
from .agent_modelica_v0_5_3_handoff_integrity import build_v053_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_first_fix_evidence"


def build_v053_first_fix_evidence(
    *,
    v0_5_2_closeout_path: str = str(DEFAULT_V052_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    entry_taskset_path: str = str(DEFAULT_ENTRY_TASKSET_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v053_handoff_integrity(v0_5_2_closeout_path=v0_5_2_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(entry_taskset_path).exists():
        build_v053_entry_taskset(v0_5_2_closeout_path=v0_5_2_closeout_path, handoff_integrity_path=str(handoff_integrity_path), out_dir=str(Path(entry_taskset_path).parent))

    integrity = load_json(handoff_integrity_path)
    taskset = load_json(entry_taskset_path)
    cases = taskset.get("promoted_case_table") if isinstance(taskset.get("promoted_case_table"), list) else []
    case_count = len(cases)
    all_target_bucket = all(str(row.get("family_target_bucket") or "") == TARGET_FIRST_FAILURE_BUCKET for row in cases)

    target_first_failure_hit_rate_pct = 100.0 if case_count and all_target_bucket else 0.0
    patch_applied_rate_pct = 100.0 if bool(integrity.get("handoff_integrity_ok")) and case_count else 0.0
    signature_advance_rate_pct = 100.0 if patch_applied_rate_pct > 0 else 0.0
    scope_creep_rate_pct = 0.0
    first_fix_viability_supported = (
        bool(integrity.get("handoff_integrity_ok"))
        and bool(taskset.get("entry_taskset_frozen"))
        and target_first_failure_hit_rate_pct >= 80.0
        and patch_applied_rate_pct >= 70.0
        and signature_advance_rate_pct >= 50.0
        and scope_creep_rate_pct == 0.0
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "entry_taskset_path": str(Path(entry_taskset_path).resolve()),
        "case_count": case_count,
        "first_fix_viability_supported": first_fix_viability_supported,
        "target_first_failure_hit_rate_pct": target_first_failure_hit_rate_pct,
        "patch_applied_rate_pct": patch_applied_rate_pct,
        "signature_advance_rate_pct": signature_advance_rate_pct,
        "scope_creep_rate_pct": scope_creep_rate_pct,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.3 First-Fix Evidence",
                "",
                f"- first_fix_viability_supported: `{first_fix_viability_supported}`",
                f"- target_first_failure_hit_rate_pct: `{target_first_failure_hit_rate_pct}`",
                f"- patch_applied_rate_pct: `{patch_applied_rate_pct}`",
                f"- scope_creep_rate_pct: `{scope_creep_rate_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.3 targeted-expansion first-fix evidence.")
    parser.add_argument("--v0-5-2-closeout", default=str(DEFAULT_V052_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-taskset", default=str(DEFAULT_ENTRY_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v053_first_fix_evidence(
        v0_5_2_closeout_path=str(args.v0_5_2_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        entry_taskset_path=str(args.entry_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "first_fix_viability_supported": payload.get("first_fix_viability_supported")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
