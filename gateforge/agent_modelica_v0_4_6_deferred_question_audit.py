from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_6_common import (
    DEFAULT_DEFERRED_AUDIT_OUT_DIR,
    SCHEMA_PREFIX,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_deferred_question_audit"


def build_v046_deferred_question_audit(*, out_dir: str = str(DEFAULT_DEFERRED_AUDIT_OUT_DIR)) -> dict:
    table = [
        {
            "question_id": "planner_injection_independent_value_not_authority_evaluated",
            "blocking_status": "non_blocking",
            "reason": "Planner injection remained sidecar throughout v0.4.x and was never required to answer the main learning-effectiveness question.",
        },
        {
            "question_id": "open_world_real_benchmark_not_attempted",
            "blocking_status": "non_blocking",
            "reason": "v0.4.x required targeted real-distribution back-check, not open-world product benchmark authority.",
        },
        {
            "question_id": "policy_superiority_only_tested_against_one_bounded_alternative",
            "blocking_status": "non_blocking",
            "reason": "v0.4.5 only needed to establish empirical support for the baseline policy, not exhaustive policy search.",
        },
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "deferred_question_table": table,
        "deferred_question_blocking_status": "non_blocking_only",
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(["# v0.4.6 Deferred Question Audit", "", "- deferred_question_blocking_status: `non_blocking_only`"]),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.6 deferred-question audit.")
    parser.add_argument("--out-dir", default=str(DEFAULT_DEFERRED_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v046_deferred_question_audit(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "deferred_question_blocking_status": payload.get("deferred_question_blocking_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
