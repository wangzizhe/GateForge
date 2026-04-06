from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_3_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_ENTRY_TASKSET_OUT_DIR,
    DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V051_CLOSEOUT_PATH,
    DEFAULT_V052_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    TARGET_ENTRY_PATTERN_ID,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_3_entry_taskset import build_v053_entry_taskset
from .agent_modelica_v0_5_3_first_fix_adjudication import build_v053_first_fix_adjudication
from .agent_modelica_v0_5_3_first_fix_evidence import build_v053_first_fix_evidence
from .agent_modelica_v0_5_3_handoff_integrity import build_v053_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v053_closeout(
    *,
    v0_5_2_closeout_path: str = str(DEFAULT_V052_CLOSEOUT_PATH),
    v0_5_1_closeout_path: str = str(DEFAULT_V051_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    entry_taskset_path: str = str(DEFAULT_ENTRY_TASKSET_OUT_DIR / "summary.json"),
    first_fix_evidence_path: str = str(DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR / "summary.json"),
    adjudication_path: str = str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v053_handoff_integrity(v0_5_2_closeout_path=v0_5_2_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(entry_taskset_path).exists():
        build_v053_entry_taskset(
            v0_5_2_closeout_path=v0_5_2_closeout_path,
            v0_5_1_closeout_path=v0_5_1_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            out_dir=str(Path(entry_taskset_path).parent),
        )
    if not Path(first_fix_evidence_path).exists():
        build_v053_first_fix_evidence(
            v0_5_2_closeout_path=v0_5_2_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            entry_taskset_path=str(entry_taskset_path),
            out_dir=str(Path(first_fix_evidence_path).parent),
        )
    if not Path(adjudication_path).exists():
        build_v053_first_fix_adjudication(
            v0_5_2_closeout_path=v0_5_2_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            entry_taskset_path=str(entry_taskset_path),
            first_fix_evidence_path=str(first_fix_evidence_path),
            out_dir=str(Path(adjudication_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    taskset = load_json(entry_taskset_path)
    evidence = load_json(first_fix_evidence_path)
    adjudication = load_json(adjudication_path)

    if not bool(integrity.get("handoff_integrity_ok")):
        version_decision = "v0_5_3_handoff_substrate_invalid"
        status = "not_ready"
        handoff_mode = "return_to_boundary_mapping_for_reassessment"
    elif bool(adjudication.get("first_fix_ready")):
        version_decision = "v0_5_3_targeted_expansion_first_fix_ready"
        status = "first_fix_ready"
        handoff_mode = "run_discovery_probe_on_targeted_expansion"
    elif bool(taskset.get("entry_taskset_frozen")):
        version_decision = "v0_5_3_targeted_expansion_partial"
        status = "partial"
        handoff_mode = "repair_targeted_expansion_first_fix_gaps_first"
    else:
        version_decision = "v0_5_3_targeted_expansion_not_ready"
        status = "not_ready"
        handoff_mode = "return_to_boundary_mapping_for_reassessment"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_5_3_TARGETED_EXPANSION_FIRST_FIX_READY",
        "conclusion": {
            "version_decision": version_decision,
            "targeted_expansion_first_fix_status": status,
            "entry_pattern_id": TARGET_ENTRY_PATTERN_ID,
            "first_fix_ready": adjudication.get("first_fix_ready"),
            "v0_5_4_handoff_mode": handoff_mode,
            "v0_5_4_primary_eval_question": "Given the now-bounded first-fix lane, can the next version probe whether this targeted expansion also supports a clean discovery trajectory without scope creep?",
        },
        "handoff_integrity": integrity,
        "entry_taskset": taskset,
        "first_fix_evidence": evidence,
        "first_fix_adjudication": adjudication,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.3 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- targeted_expansion_first_fix_status: `{status}`",
                f"- v0_5_4_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.3 targeted-expansion first-fix closeout.")
    parser.add_argument("--v0-5-2-closeout", default=str(DEFAULT_V052_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-1-closeout", default=str(DEFAULT_V051_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-taskset", default=str(DEFAULT_ENTRY_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix-evidence", default=str(DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR / "summary.json"))
    parser.add_argument("--adjudication", default=str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v053_closeout(
        v0_5_2_closeout_path=str(args.v0_5_2_closeout),
        v0_5_1_closeout_path=str(args.v0_5_1_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        entry_taskset_path=str(args.entry_taskset),
        first_fix_evidence_path=str(args.first_fix_evidence),
        adjudication_path=str(args.adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
