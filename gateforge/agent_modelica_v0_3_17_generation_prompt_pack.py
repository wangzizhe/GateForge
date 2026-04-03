from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_17_common import REPO_ROOT, frozen_prompt_specs, now_utc, write_json, write_text


SCHEMA_VERSION = "agent_modelica_v0_3_17_generation_prompt_pack"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_prompt_pack_current"


def build_generation_prompt_pack(*, out_dir: str = str(DEFAULT_OUT_DIR)) -> dict:
    tiers = frozen_prompt_specs()
    tier_summary = {}
    all_tasks = []
    for tier_name, section in tiers.items():
        active = [row for row in (section.get("active_tasks") or []) if isinstance(row, dict)]
        reserve = [row for row in (section.get("reserve_tasks") or []) if isinstance(row, dict)]
        tier_summary[tier_name] = {
            "active_count": len(active),
            "reserve_count": len(reserve),
            "task_ids": [row.get("task_id") for row in active],
            "reserve_task_ids": [row.get("task_id") for row in reserve],
        }
        all_tasks.extend(active)
        all_tasks.extend(reserve)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "total_active_count": sum(int(section.get("active_count") or 0) for section in tier_summary.values()),
        "total_reserve_count": sum(int(section.get("reserve_count") or 0) for section in tier_summary.values()),
        "tiers": tiers,
        "tier_summary": tier_summary,
        "tasks": all_tasks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "prompt_pack.json", payload)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.17 Generation Prompt Pack",
                "",
                f"- status: `{payload.get('status')}`",
                f"- total_active_count: `{payload.get('total_active_count')}`",
                f"- total_reserve_count: `{payload.get('total_reserve_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.17 generation prompt pack.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_generation_prompt_pack(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "total_active_count": payload.get("total_active_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
