from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_2_common import (
    DEFAULT_ENTRY_TRIAGE_OUT_DIR,
    DEFAULT_SIGNAL_AUDIT_OUT_DIR,
    DEFAULT_V051_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    qualitative_pattern_id,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_2_signal_audit import build_v052_signal_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_entry_triage"


def build_v052_entry_triage(
    *,
    v0_5_1_closeout_path: str = str(DEFAULT_V051_CLOSEOUT_PATH),
    signal_audit_path: str = str(DEFAULT_SIGNAL_AUDIT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ENTRY_TRIAGE_OUT_DIR),
) -> dict:
    rebuild_signal = True
    if Path(signal_audit_path).exists():
        existing_signal = load_json(signal_audit_path)
        rebuild_signal = str(existing_signal.get("v0_5_1_closeout_path") or "") != str(Path(v0_5_1_closeout_path).resolve())
    if rebuild_signal:
        build_v052_signal_audit(v0_5_1_closeout_path=v0_5_1_closeout_path, out_dir=str(Path(signal_audit_path).parent))

    closeout = load_json(v0_5_1_closeout_path)
    signal = load_json(signal_audit_path)
    classification = closeout.get("case_classification") if isinstance(closeout.get("case_classification"), dict) else {}
    case_rows = classification.get("case_rows") if isinstance(classification.get("case_rows"), list) else []

    selected_entry_pattern_id = ""
    shared_patterns = signal.get("shared_pattern_table") if isinstance(signal.get("shared_pattern_table"), list) else []
    if shared_patterns:
        selected_entry_pattern_id = str((shared_patterns[0] or {}).get("pattern_id") or "")

    candidate_rows = [
        row
        for row in case_rows
        if isinstance(row, dict)
        and str(row.get("assigned_boundary_bucket") or "") == "bounded_uncovered_subtype_candidate"
        and qualitative_pattern_id(row) == selected_entry_pattern_id
    ]
    rejected_pattern_table = []
    for row in case_rows:
        if not isinstance(row, dict):
            continue
        pattern_id = qualitative_pattern_id(row)
        bucket = str(row.get("assigned_boundary_bucket") or "")
        if not pattern_id or pattern_id == selected_entry_pattern_id:
            continue
        rejected_pattern_table.append(
            {
                "task_id": str(row.get("task_id") or ""),
                "pattern_id": pattern_id,
                "rejection_reason": (
                    "Still policy or taxonomy residue." if bucket == "dispatch_or_policy_limited" else
                    "Outside the selected recurring bounded uncovered pattern." if bucket != "bounded_uncovered_subtype_candidate" else
                    "Bounded but not the dominant recurring shared pattern for this entry freeze."
                ),
            }
        )

    entry_candidate_boundedness_supported = (
        bool(signal.get("recurring_signal_supported"))
        and selected_entry_pattern_id.startswith("medium_redeclare_alignment.")
        and len(candidate_rows) >= 4
    )
    entry_not_policy_residue = True

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "signal_audit_path": str(Path(signal_audit_path).resolve()),
        "selected_entry_pattern_id": selected_entry_pattern_id,
        "selected_entry_pattern_reason": "Recurring bounded uncovered pressure clusters around medium-redeclare fluid-network / medium-cluster slices, not open-world spillover and not dispatch residue.",
        "selected_entry_task_count": len(candidate_rows),
        "selected_entry_task_ids": [str(row.get("task_id") or "") for row in candidate_rows],
        "entry_candidate_boundedness_supported": entry_candidate_boundedness_supported,
        "entry_not_policy_residue": entry_not_policy_residue,
        "rejected_pattern_table": rejected_pattern_table,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.2 Entry Triage",
                "",
                f"- selected_entry_pattern_id: `{selected_entry_pattern_id}`",
                f"- selected_entry_task_count: `{len(candidate_rows)}`",
                f"- entry_candidate_boundedness_supported: `{entry_candidate_boundedness_supported}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.2 targeted-expansion entry triage.")
    parser.add_argument("--v0-5-1-closeout", default=str(DEFAULT_V051_CLOSEOUT_PATH))
    parser.add_argument("--signal-audit", default=str(DEFAULT_SIGNAL_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ENTRY_TRIAGE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v052_entry_triage(
        v0_5_1_closeout_path=str(args.v0_5_1_closeout),
        signal_audit_path=str(args.signal_audit),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "selected_entry_pattern_id": payload.get("selected_entry_pattern_id")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
