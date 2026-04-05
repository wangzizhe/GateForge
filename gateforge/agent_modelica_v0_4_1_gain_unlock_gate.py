from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_0_closeout import build_v040_closeout
from .agent_modelica_v0_4_1_common import (
    DEFAULT_GAIN_UNLOCK_OUT_DIR,
    DEFAULT_REAUDIT_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_1_conditioning_reaudit import build_v041_conditioning_reaudit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_gain_unlock_gate"


def build_v041_gain_unlock_gate(
    *,
    conditioning_reaudit_path: str = str(DEFAULT_REAUDIT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_GAIN_UNLOCK_OUT_DIR),
) -> dict:
    if not Path(conditioning_reaudit_path).exists():
        build_v041_conditioning_reaudit(out_dir=str(Path(conditioning_reaudit_path).parent))

    reaudit = load_json(conditioning_reaudit_path)
    replay_rate = float(reaudit.get("replay_exact_match_rate_pct") or 0.0)
    planner_rate = float(reaudit.get("planner_hint_rate_pct") or 0.0)
    synthetic_gain_measurement_unlocked = bool(reaudit.get("conditioning_reactivation_ready"))
    if replay_rate > 0.0 and planner_rate > 0.0:
        preferred_conditioning_mode_for_v0_4_2 = "replay_primary_with_planner_sidecar"
        single_mechanism_constraint = False
    elif replay_rate > 0.0:
        preferred_conditioning_mode_for_v0_4_2 = "replay_only"
        single_mechanism_constraint = True
    elif planner_rate > 0.0:
        preferred_conditioning_mode_for_v0_4_2 = "planner_only"
        single_mechanism_constraint = True
    else:
        preferred_conditioning_mode_for_v0_4_2 = "none"
        single_mechanism_constraint = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "conditioning_reaudit_path": str(Path(conditioning_reaudit_path).resolve()),
        "synthetic_gain_measurement_unlocked": synthetic_gain_measurement_unlocked,
        "preferred_conditioning_mode_for_v0_4_2": preferred_conditioning_mode_for_v0_4_2,
        "single_mechanism_constraint": single_mechanism_constraint,
        "primary_bottleneck": "none" if synthetic_gain_measurement_unlocked else "stage2_conditioning_signal_still_insufficient",
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.1 Gain Unlock Gate",
                "",
                f"- synthetic_gain_measurement_unlocked: `{payload.get('synthetic_gain_measurement_unlocked')}`",
                f"- preferred_conditioning_mode_for_v0_4_2: `{payload.get('preferred_conditioning_mode_for_v0_4_2')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.1 synthetic gain unlock gate.")
    parser.add_argument("--conditioning-reaudit", default=str(DEFAULT_REAUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_GAIN_UNLOCK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v041_gain_unlock_gate(
        conditioning_reaudit_path=str(args.conditioning_reaudit),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "synthetic_gain_measurement_unlocked": payload.get("synthetic_gain_measurement_unlocked")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
