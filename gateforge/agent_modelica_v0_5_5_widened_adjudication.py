from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_5_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V054_CLOSEOUT_PATH,
    DEFAULT_WIDENED_EXECUTION_OUT_DIR,
    DEFAULT_WIDENED_MANIFEST_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_5_handoff_integrity import build_v055_handoff_integrity
from .agent_modelica_v0_5_5_widened_execution import build_v055_widened_execution
from .agent_modelica_v0_5_5_widened_manifest import build_v055_widened_manifest


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_widened_adjudication"


def build_v055_widened_adjudication(
    *,
    v0_5_4_closeout_path: str = str(DEFAULT_V054_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    widened_manifest_path: str = str(DEFAULT_WIDENED_MANIFEST_OUT_DIR / "summary.json"),
    widened_execution_path: str = str(DEFAULT_WIDENED_EXECUTION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ADJUDICATION_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v055_handoff_integrity(v0_5_4_closeout_path=v0_5_4_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(widened_manifest_path).exists():
        build_v055_widened_manifest(
            v0_5_4_closeout_path=v0_5_4_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            out_dir=str(Path(widened_manifest_path).parent),
        )
    if not Path(widened_execution_path).exists():
        build_v055_widened_execution(
            v0_5_4_closeout_path=v0_5_4_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            widened_manifest_path=str(widened_manifest_path),
            out_dir=str(Path(widened_execution_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    manifest = load_json(widened_manifest_path)
    execution = load_json(widened_execution_path)

    handoff_integrity_ok = bool(integrity.get("handoff_integrity_ok"))
    widened_manifest_frozen = bool(manifest.get("widened_manifest_frozen"))
    widened_execution_supported = bool(execution.get("widened_execution_supported"))
    scope_creep_rate_pct = float(execution.get("scope_creep_rate_pct") or 0.0)
    widened_ready = handoff_integrity_ok and widened_manifest_frozen and widened_execution_supported and scope_creep_rate_pct == 0.0

    support_gap_table = []
    if not handoff_integrity_ok:
        support_gap_table.append("handoff_integrity_not_ok")
    if not widened_manifest_frozen:
        support_gap_table.append("widened_manifest_not_frozen")
    if not widened_execution_supported:
        support_gap_table.append("widened_execution_not_supported")
    if scope_creep_rate_pct != 0.0:
        support_gap_table.append("scope_creep_detected")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "handoff_integrity_path": str(Path(handoff_integrity_path).resolve()),
        "widened_manifest_path": str(Path(widened_manifest_path).resolve()),
        "widened_execution_path": str(Path(widened_execution_path).resolve()),
        "widened_ready": widened_ready,
        "support_gap_table": support_gap_table,
        "widened_interpretation": {
            "primary_stability_factor": (
                "The targeted expansion keeps both first-fix and bounded second-residual behavior after denominator widening."
                if widened_ready
                else "At least one widened stability layer no longer holds cleanly."
            ),
            "boundedness_preserved": scope_creep_rate_pct == 0.0,
        },
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.5 Widened Adjudication",
                "",
                f"- widened_ready: `{widened_ready}`",
                f"- support_gap_table: `{', '.join(support_gap_table) if support_gap_table else 'none'}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.5 widened adjudication.")
    parser.add_argument("--v0-5-4-closeout", default=str(DEFAULT_V054_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--widened-manifest", default=str(DEFAULT_WIDENED_MANIFEST_OUT_DIR / "summary.json"))
    parser.add_argument("--widened-execution", default=str(DEFAULT_WIDENED_EXECUTION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v055_widened_adjudication(
        v0_5_4_closeout_path=str(args.v0_5_4_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        widened_manifest_path=str(args.widened_manifest),
        widened_execution_path=str(args.widened_execution),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "widened_ready": payload.get("widened_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
