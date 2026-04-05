from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_6_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V040_CLOSEOUT_PATH,
    DEFAULT_V041_CLOSEOUT_PATH,
    DEFAULT_V042_CLOSEOUT_PATH,
    DEFAULT_V043_CLOSEOUT_PATH,
    DEFAULT_V044_CLOSEOUT_PATH,
    DEFAULT_V045_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_phase_ledger"


def build_v046_phase_ledger(
    *,
    v040_closeout_path: str = str(DEFAULT_V040_CLOSEOUT_PATH),
    v041_closeout_path: str = str(DEFAULT_V041_CLOSEOUT_PATH),
    v042_closeout_path: str = str(DEFAULT_V042_CLOSEOUT_PATH),
    v043_closeout_path: str = str(DEFAULT_V043_CLOSEOUT_PATH),
    v044_closeout_path: str = str(DEFAULT_V044_CLOSEOUT_PATH),
    v045_closeout_path: str = str(DEFAULT_V045_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    entries = []
    for version, path in [
        ("v0.4.0", v040_closeout_path),
        ("v0.4.1", v041_closeout_path),
        ("v0.4.2", v042_closeout_path),
        ("v0.4.3", v043_closeout_path),
        ("v0.4.4", v044_closeout_path),
        ("v0.4.5", v045_closeout_path),
    ]:
        payload = load_json(path)
        conclusion = payload.get("conclusion") if isinstance(payload.get("conclusion"), dict) else {}
        entries.append(
            {
                "version": version,
                "closeout_path": str(Path(path).resolve()),
                "version_decision": conclusion.get("version_decision"),
                "primary_status": conclusion,
            }
        )

    phase_ledger_complete = len(entries) == 6 and all(bool(entry.get("version_decision")) for entry in entries)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_ledger_complete else "FAIL",
        "phase_ledger_complete": phase_ledger_complete,
        "version_anchor_table": entries,
        "authority_transition_table": [
            {"from_version": "v0.4.0", "to_version": "v0.4.1", "transition": "conditioning_substrate_partial -> stage2_conditioning_signal_ready"},
            {"from_version": "v0.4.1", "to_version": "v0.4.2", "transition": "signal_ready -> synthetic_gain_supported_real_backcheck_partial"},
            {"from_version": "v0.4.2", "to_version": "v0.4.3", "transition": "partial_real_backcheck -> supported_real_backcheck"},
            {"from_version": "v0.4.3", "to_version": "v0.4.4", "transition": "supported_real_backcheck -> real_authority_promoted"},
            {"from_version": "v0.4.4", "to_version": "v0.4.5", "transition": "real_authority_promoted -> dispatch_policy_empirically_supported"},
        ],
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.6 Phase Ledger",
                "",
                f"- phase_ledger_complete: `{payload.get('phase_ledger_complete')}`",
                f"- version_count: `{len(entries)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.6 phase ledger.")
    parser.add_argument("--v040-closeout", default=str(DEFAULT_V040_CLOSEOUT_PATH))
    parser.add_argument("--v041-closeout", default=str(DEFAULT_V041_CLOSEOUT_PATH))
    parser.add_argument("--v042-closeout", default=str(DEFAULT_V042_CLOSEOUT_PATH))
    parser.add_argument("--v043-closeout", default=str(DEFAULT_V043_CLOSEOUT_PATH))
    parser.add_argument("--v044-closeout", default=str(DEFAULT_V044_CLOSEOUT_PATH))
    parser.add_argument("--v045-closeout", default=str(DEFAULT_V045_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v046_phase_ledger(
        v040_closeout_path=str(args.v040_closeout),
        v041_closeout_path=str(args.v041_closeout),
        v042_closeout_path=str(args.v042_closeout),
        v043_closeout_path=str(args.v043_closeout),
        v044_closeout_path=str(args.v044_closeout),
        v045_closeout_path=str(args.v045_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_complete": payload.get("phase_ledger_complete")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
