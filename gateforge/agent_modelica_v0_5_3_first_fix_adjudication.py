from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_3_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_ENTRY_TASKSET_OUT_DIR,
    DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V052_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_3_entry_taskset import build_v053_entry_taskset
from .agent_modelica_v0_5_3_first_fix_evidence import build_v053_first_fix_evidence
from .agent_modelica_v0_5_3_handoff_integrity import build_v053_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_first_fix_adjudication"


def build_v053_first_fix_adjudication(
    *,
    v0_5_2_closeout_path: str = str(DEFAULT_V052_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    entry_taskset_path: str = str(DEFAULT_ENTRY_TASKSET_OUT_DIR / "summary.json"),
    first_fix_evidence_path: str = str(DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ADJUDICATION_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v053_handoff_integrity(v0_5_2_closeout_path=v0_5_2_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(entry_taskset_path).exists():
        build_v053_entry_taskset(v0_5_2_closeout_path=v0_5_2_closeout_path, handoff_integrity_path=str(handoff_integrity_path), out_dir=str(Path(entry_taskset_path).parent))
    if not Path(first_fix_evidence_path).exists():
        build_v053_first_fix_evidence(
            v0_5_2_closeout_path=v0_5_2_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            entry_taskset_path=str(entry_taskset_path),
            out_dir=str(Path(first_fix_evidence_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    taskset = load_json(entry_taskset_path)
    evidence = load_json(first_fix_evidence_path)

    handoff_integrity_ok = bool(integrity.get("handoff_integrity_ok"))
    entry_taskset_frozen = bool(taskset.get("entry_taskset_frozen"))
    first_fix_viability_supported = bool(evidence.get("first_fix_viability_supported"))
    scope_creep_rate_pct = float(evidence.get("scope_creep_rate_pct") or 0.0)
    first_fix_ready = handoff_integrity_ok and entry_taskset_frozen and first_fix_viability_supported and scope_creep_rate_pct == 0.0

    support_gap_table = []
    if not handoff_integrity_ok:
        support_gap_table.append("handoff_integrity_not_ok")
    if not entry_taskset_frozen:
        support_gap_table.append("entry_taskset_not_frozen")
    if not first_fix_viability_supported:
        support_gap_table.append("first_fix_viability_not_supported")
    if scope_creep_rate_pct != 0.0:
        support_gap_table.append("scope_creep_detected")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "handoff_integrity_path": str(Path(handoff_integrity_path).resolve()),
        "entry_taskset_path": str(Path(entry_taskset_path).resolve()),
        "first_fix_evidence_path": str(Path(first_fix_evidence_path).resolve()),
        "first_fix_ready": first_fix_ready,
        "support_gap_table": support_gap_table,
        "entry_execution_interpretation": {
            "primary_execution_factor": (
                "Targeted medium-redeclare entry stays local enough that a bounded package-path redeclare patch can resolve the first failure cleanly."
                if first_fix_ready
                else "Either handoff integrity, taskset freeze, or first-fix execution support remains insufficient."
            ),
            "anti_expansion_boundary_preserved": scope_creep_rate_pct == 0.0,
        },
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.3 First-Fix Adjudication",
                "",
                f"- first_fix_ready: `{first_fix_ready}`",
                f"- support_gap_table: `{', '.join(support_gap_table) if support_gap_table else 'none'}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.3 targeted-expansion first-fix adjudication.")
    parser.add_argument("--v0-5-2-closeout", default=str(DEFAULT_V052_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-taskset", default=str(DEFAULT_ENTRY_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix-evidence", default=str(DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v053_first_fix_adjudication(
        v0_5_2_closeout_path=str(args.v0_5_2_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        entry_taskset_path=str(args.entry_taskset),
        first_fix_evidence_path=str(args.first_fix_evidence),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "first_fix_ready": payload.get("first_fix_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
