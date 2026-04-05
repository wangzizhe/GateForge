from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_1_common import (
    DEFAULT_GAIN_UNLOCK_OUT_DIR,
    DEFAULT_V0_4_2_HANDOFF_OUT_DIR,
    DEFAULT_V040_HANDOFF_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_1_gain_unlock_gate import build_v041_gain_unlock_gate


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_v0_4_2_handoff"


def build_v041_v0_4_2_handoff(
    *,
    gain_unlock_path: str = str(DEFAULT_GAIN_UNLOCK_OUT_DIR / "summary.json"),
    v040_handoff_path: str = str(DEFAULT_V040_HANDOFF_PATH),
    out_dir: str = str(DEFAULT_V0_4_2_HANDOFF_OUT_DIR),
) -> dict:
    if not Path(gain_unlock_path).exists():
        build_v041_gain_unlock_gate(out_dir=str(Path(gain_unlock_path).parent))

    unlock = load_json(gain_unlock_path)
    legacy = load_json(v040_handoff_path)
    unlocked = bool(unlock.get("synthetic_gain_measurement_unlocked"))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "gain_unlock_path": str(Path(gain_unlock_path).resolve()),
        "v040_handoff_path": str(Path(v040_handoff_path).resolve()),
        "v0_4_2_primary_eval_question": (
            "Does refreshed stage-2 conditioning signal unlock measurable synthetic gain, and does that movement survive the required targeted real back-check?"
            if unlocked
            else "What remaining conditioning-signal bottleneck still blocks synthetic gain measurement on the three-family benchmark?"
        ),
        "v0_4_2_required_real_back_check": True,
        "v0_4_2_policy_eval_scope": legacy.get("v0_4_multi_family_policy_requirement") or {},
        "next_phase_recommendation": (
            "run_synthetic_gain_measurement_with_required_real_back_check"
            if unlocked
            else "continue_stage2_conditioning_signal_refresh"
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.1 v0.4.2 Handoff",
                "",
                f"- next_phase_recommendation: `{payload.get('next_phase_recommendation')}`",
                f"- v0_4_2_required_real_back_check: `{payload.get('v0_4_2_required_real_back_check')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.1 -> v0.4.2 handoff.")
    parser.add_argument("--gain-unlock", default=str(DEFAULT_GAIN_UNLOCK_OUT_DIR / "summary.json"))
    parser.add_argument("--v040-handoff", default=str(DEFAULT_V040_HANDOFF_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_V0_4_2_HANDOFF_OUT_DIR))
    args = parser.parse_args()
    payload = build_v041_v0_4_2_handoff(
        gain_unlock_path=str(args.gain_unlock),
        v040_handoff_path=str(args.v040_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_phase_recommendation": payload.get("next_phase_recommendation")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
