from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_5_2_common import (
    DEFAULT_SIGNAL_AUDIT_OUT_DIR,
    DEFAULT_V051_CLOSEOUT_PATH,
    MINIMUM_BOUNDED_UNCOVERED_CASE_COUNT,
    MINIMUM_BOUNDED_UNCOVERED_CASE_SHARE_PCT,
    MINIMUM_SHARED_PATTERN_COUNT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    qualitative_pattern_id,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_signal_audit"


def build_v052_signal_audit(
    *,
    v0_5_1_closeout_path: str = str(DEFAULT_V051_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_SIGNAL_AUDIT_OUT_DIR),
) -> dict:
    closeout = load_json(v0_5_1_closeout_path)
    integrity = closeout.get("frozen_slice_integrity") if isinstance(closeout.get("frozen_slice_integrity"), dict) else {}
    classification = closeout.get("case_classification") if isinstance(closeout.get("case_classification"), dict) else {}
    case_rows = classification.get("case_rows") if isinstance(classification.get("case_rows"), list) else []

    bounded_rows = [
        row
        for row in case_rows
        if isinstance(row, dict) and str(row.get("assigned_boundary_bucket") or "") == "bounded_uncovered_subtype_candidate"
    ]
    pattern_counts = Counter(qualitative_pattern_id(row) for row in bounded_rows)
    shared_patterns = [
        {"pattern_id": pattern_id, "case_count": count}
        for pattern_id, count in pattern_counts.items()
        if count >= 2
    ]
    shared_patterns.sort(key=lambda item: (-int(item["case_count"]), str(item["pattern_id"])))

    bounded_case_count = len(bounded_rows)
    total_case_count = len(case_rows)
    share_pct = round((100.0 * bounded_case_count / total_case_count), 1) if total_case_count else 0.0
    recurring_signal_supported = (
        bool(integrity.get("dispatch_cleanliness_level") == "promoted")
        and bounded_case_count >= MINIMUM_BOUNDED_UNCOVERED_CASE_COUNT
        and share_pct >= MINIMUM_BOUNDED_UNCOVERED_CASE_SHARE_PCT
        and len(shared_patterns) >= MINIMUM_SHARED_PATTERN_COUNT
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if bool(closeout.get("status") == "PASS") else "FAIL",
        "v0_5_1_closeout_path": str(Path(v0_5_1_closeout_path).resolve()),
        "bounded_uncovered_signal_audited": True,
        "bounded_uncovered_case_count": bounded_case_count,
        "bounded_uncovered_case_share_pct": share_pct,
        "shared_pattern_count": len(shared_patterns),
        "shared_pattern_table": shared_patterns,
        "bounded_uncovered_case_task_ids": [str(row.get("task_id") or "") for row in bounded_rows],
        "recurring_signal_supported": recurring_signal_supported,
        "minimum_floor_note": "Thresholds are minimum acceptable floors, not finely calibrated expectations. Near-threshold misses default to substrate insufficiency rather than threshold renegotiation.",
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.2 Signal Audit",
                "",
                f"- bounded_uncovered_case_count: `{bounded_case_count}`",
                f"- bounded_uncovered_case_share_pct: `{share_pct}`",
                f"- shared_pattern_count: `{len(shared_patterns)}`",
                f"- recurring_signal_supported: `{recurring_signal_supported}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.2 recurring bounded-uncovered signal audit.")
    parser.add_argument("--v0-5-1-closeout", default=str(DEFAULT_V051_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_SIGNAL_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v052_signal_audit(v0_5_1_closeout_path=str(args.v0_5_1_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "recurring_signal_supported": payload.get("recurring_signal_supported")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
