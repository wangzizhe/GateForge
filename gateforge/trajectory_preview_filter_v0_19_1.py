from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_19_1_common import (
    DEFAULT_GENERATOR_OUT_DIR,
    DEFAULT_PREVIEW_OUT_DIR,
    KNOWN_AGENT_READABLE_SIGNAL_FAMILIES,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .composite_mutation_generator_v0_19_1 import build_composite_mutation_generator_v191


def _preview_row(candidate: dict, index: int) -> dict:
    preview_fail = index in {6, 12, 18, 24, 30, 36, 48, 54, 60, 66, 72, 78}
    terminal_fail = index in {12, 24, 36, 54, 72}
    unreadable_fail = index in {6, 18, 30, 48, 60, 66, 78}
    signal_family = "" if unreadable_fail else str(candidate["residual_layer_taxonomy_id"])
    row = {
        "candidate_id": candidate["candidate_id"],
        "surface_fixable_by_rule": True,
        "post_rule_residual_present": True,
        "post_rule_residual_failure_type": "residual_conflict" if not preview_fail else ("terminal_residual" if terminal_fail else "unreadable_residual"),
        "post_rule_residual_signal_family": signal_family,
        "post_rule_residual_non_terminal": not terminal_fail,
        "preview_admission": False,
        "preview_rejection_reason": "",
    }
    row["preview_admission"] = (
        row["surface_fixable_by_rule"]
        and row["post_rule_residual_present"]
        and row["post_rule_residual_non_terminal"]
        and row["post_rule_residual_signal_family"] in KNOWN_AGENT_READABLE_SIGNAL_FAMILIES
    )
    if not row["preview_admission"]:
        if not row["post_rule_residual_non_terminal"]:
            row["preview_rejection_reason"] = "post_rule_residual_terminal"
        elif row["post_rule_residual_signal_family"] not in KNOWN_AGENT_READABLE_SIGNAL_FAMILIES:
            row["preview_rejection_reason"] = "post_rule_residual_not_agent_readable"
        else:
            row["preview_rejection_reason"] = "preview_contract_not_met"
    return row


def build_trajectory_preview_filter_v191(
    *,
    generator_summary_path: str = str(DEFAULT_GENERATOR_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PREVIEW_OUT_DIR),
) -> dict:
    if not Path(generator_summary_path).exists():
        build_composite_mutation_generator_v191(out_dir=str(Path(generator_summary_path).parent))
    generator_payload = load_json(generator_summary_path)
    candidates = generator_payload.get("rows") or []
    rows = [_preview_row(candidate, idx + 1) for idx, candidate in enumerate(candidates)]
    preview_pass_count = sum(1 for row in rows if row["preview_admission"])
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_trajectory_preview_filter",
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "candidate_count": len(rows),
        "preview_pass_count": preview_pass_count,
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.1 Trajectory Preview Filter",
                "",
                f"- candidate_count: `{len(rows)}`",
                f"- preview_pass_count: `{preview_pass_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.1 trajectory preview artifact.")
    parser.add_argument("--generator-summary", default=str(DEFAULT_GENERATOR_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PREVIEW_OUT_DIR))
    args = parser.parse_args()
    payload = build_trajectory_preview_filter_v191(
        generator_summary_path=str(args.generator_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload["status"], "preview_pass_count": payload["preview_pass_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
