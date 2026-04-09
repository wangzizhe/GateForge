from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_3_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V092_CLOSEOUT_PATH,
    DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH,
    MIN_EXPANDED_SUBSTRATE_SIZE,
    MIN_READY_BARRIER_COUNT,
    PRIORITY_BARRIERS,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v093_handoff_integrity(
    *,
    v092_closeout_path: str = str(DEFAULT_V092_CLOSEOUT_PATH),
    v092_expanded_substrate_builder_path: str = str(DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    closeout = load_json(v092_closeout_path)
    builder = load_json(v092_expanded_substrate_builder_path)

    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    builder_rows = (
        builder.get("expanded_substrate_candidate_table")
        if isinstance(builder.get("expanded_substrate_candidate_table"), list)
        else []
    )
    builder_barriers = (
        builder.get("priority_barrier_coverage_table")
        if isinstance(builder.get("priority_barrier_coverage_table"), dict)
        else {}
    )

    checks = {
        "closeout_version_ready": conclusion.get("version_decision")
        == "v0_9_2_first_expanded_authentic_workflow_substrate_ready",
        "closeout_status_ready": conclusion.get("expanded_substrate_status") == "ready",
        "closeout_size_floor_met": int(conclusion.get("expanded_substrate_size") or 0) >= MIN_EXPANDED_SUBSTRATE_SIZE,
        "closeout_handoff_mode_expected": conclusion.get("v0_9_3_handoff_mode") == "characterize_expanded_workflow_profile",
        "builder_exists_and_size_floor_met": len(builder_rows) >= MIN_EXPANDED_SUBSTRATE_SIZE,
        "builder_priority_barrier_floor_met": all(
            int(builder_barriers.get(barrier) or 0) >= MIN_READY_BARRIER_COUNT
            for barrier in PRIORITY_BARRIERS
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "v092_closeout_summary": {
            "version_decision": conclusion.get("version_decision"),
            "expanded_substrate_status": conclusion.get("expanded_substrate_status"),
            "expanded_substrate_size": conclusion.get("expanded_substrate_size"),
            "priority_barrier_coverage_table": conclusion.get("priority_barrier_coverage_table"),
            "v0_9_3_handoff_mode": conclusion.get("v0_9_3_handoff_mode"),
        },
        "v092_expanded_substrate_builder_summary": {
            "expanded_substrate_candidate_count": len(builder_rows),
            "priority_barrier_coverage_table": builder_barriers,
        },
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.3 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- expanded_substrate_candidate_count: `{len(builder_rows)}`",
                f"- priority_barrier_coverage_table: `{builder_barriers}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.3 handoff integrity artifact.")
    parser.add_argument("--v092-closeout", default=str(DEFAULT_V092_CLOSEOUT_PATH))
    parser.add_argument("--v092-expanded-substrate-builder", default=str(DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v093_handoff_integrity(
        v092_closeout_path=str(args.v092_closeout),
        v092_expanded_substrate_builder_path=str(args.v092_expanded_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
