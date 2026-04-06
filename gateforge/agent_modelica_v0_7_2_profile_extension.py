from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .agent_modelica_v0_7_2_common import (
    DEFAULT_PROFILE_EXTENSION_OUT_DIR,
    DEFAULT_V070_SUBSTRATE_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


_EXTRA_ROWS: list[dict[str, Any]] = [
    {"task_id": "v072_case_23", "family_id": "component_api_alignment", "complexity_tier": "medium", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
    {"task_id": "v072_case_24", "family_id": "local_interface_alignment", "complexity_tier": "medium", "legacy_bucket_hint": "covered_but_fragile", "dispatch_risk": "clean"},
    {"task_id": "v072_case_25", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "dispatch_or_policy_limited", "dispatch_risk": "ambiguous"},
    {"task_id": "v072_case_26", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "bounded_uncovered_subtype_candidate", "dispatch_risk": "clean"},
    {"task_id": "v072_case_27", "family_id": "component_api_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "topology_or_open_world_spillover", "dispatch_risk": "clean"},
    {"task_id": "v072_case_28", "family_id": "local_interface_alignment", "complexity_tier": "simple", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
]


def build_v072_profile_extension(
    *,
    substrate_path: str = str(DEFAULT_V070_SUBSTRATE_PATH),
    out_dir: str = str(DEFAULT_PROFILE_EXTENSION_OUT_DIR),
) -> dict:
    substrate = load_json(substrate_path)
    base_rows = list(substrate.get("task_rows") or [])
    rows = base_rows + _EXTRA_ROWS
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_profile_extension",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "slice_extension_mode": "widened",
        "case_count_after_extension": len(rows),
        "distribution_logic_preserved": True,
        "task_rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.2 Profile Extension",
                "",
                "- slice_extension_mode: `widened`",
                f"- case_count_after_extension: `{len(rows)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.2 profile extension slice.")
    parser.add_argument("--substrate-path", default=str(DEFAULT_V070_SUBSTRATE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_EXTENSION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v072_profile_extension(
        substrate_path=str(args.substrate_path),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
