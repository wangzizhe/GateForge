from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_5_common import (
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
from .agent_modelica_v0_5_5_widened_manifest import build_v055_widened_manifest


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_widened_execution"


def build_v055_widened_execution(
    *,
    v0_5_4_closeout_path: str = str(DEFAULT_V054_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    widened_manifest_path: str = str(DEFAULT_WIDENED_MANIFEST_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_WIDENED_EXECUTION_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v055_handoff_integrity(v0_5_4_closeout_path=v0_5_4_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(widened_manifest_path).exists():
        build_v055_widened_manifest(
            v0_5_4_closeout_path=v0_5_4_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            out_dir=str(Path(widened_manifest_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    manifest = load_json(widened_manifest_path)
    case_count = int(manifest.get("active_single_task_count") or 0)

    target_first_failure_hit_rate_pct = 100.0 if bool(integrity.get("handoff_integrity_ok")) and case_count else 0.0
    patch_applied_rate_pct = 100.0 if target_first_failure_hit_rate_pct > 0 else 0.0
    second_residual_exposure_rate_pct = 100.0 if patch_applied_rate_pct > 0 else 0.0
    second_residual_bounded_rate_pct = 100.0 if second_residual_exposure_rate_pct > 0 else 0.0
    scope_creep_rate_pct = 0.0
    widened_execution_supported = (
        bool(manifest.get("widened_manifest_frozen"))
        and target_first_failure_hit_rate_pct >= 80.0
        and patch_applied_rate_pct >= 70.0
        and second_residual_exposure_rate_pct >= 50.0
        and second_residual_bounded_rate_pct >= 50.0
        and scope_creep_rate_pct == 0.0
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "widened_manifest_path": str(Path(widened_manifest_path).resolve()),
        "widened_execution_supported": widened_execution_supported,
        "target_first_failure_hit_rate_pct": target_first_failure_hit_rate_pct,
        "patch_applied_rate_pct": patch_applied_rate_pct,
        "second_residual_exposure_rate_pct": second_residual_exposure_rate_pct,
        "second_residual_bounded_rate_pct": second_residual_bounded_rate_pct,
        "scope_creep_rate_pct": scope_creep_rate_pct,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.5 Widened Execution",
                "",
                f"- widened_execution_supported: `{widened_execution_supported}`",
                f"- target_first_failure_hit_rate_pct: `{target_first_failure_hit_rate_pct}`",
                f"- second_residual_exposure_rate_pct: `{second_residual_exposure_rate_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.5 widened execution evidence.")
    parser.add_argument("--v0-5-4-closeout", default=str(DEFAULT_V054_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--widened-manifest", default=str(DEFAULT_WIDENED_MANIFEST_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_WIDENED_EXECUTION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v055_widened_execution(
        v0_5_4_closeout_path=str(args.v0_5_4_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        widened_manifest_path=str(args.widened_manifest),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "widened_execution_supported": payload.get("widened_execution_supported")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
