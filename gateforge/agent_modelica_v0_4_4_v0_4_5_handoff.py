from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_4_common import (
    DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR,
    DEFAULT_V0_4_5_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_4_promotion_adjudication import build_v044_promotion_adjudication


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_v0_4_5_handoff"


def build_v044_v0_4_5_handoff(
    *,
    promotion_adjudication_path: str = str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_V0_4_5_HANDOFF_OUT_DIR),
) -> dict:
    if not Path(promotion_adjudication_path).exists():
        build_v044_promotion_adjudication(out_dir=str(Path(promotion_adjudication_path).parent))
    promotion = load_json(promotion_adjudication_path)

    if bool(promotion.get("real_authority_upgrade_supported")):
        handoff_mode = "prepare_v0_4_phase_synthesis"
        question = "Can v0.4.x now be closed as a successful learning-effectiveness phase with real-authority support?"
    elif bool(promotion.get("promotion_floor_satisfied")):
        basis = str(promotion.get("promotion_basis") or "")
        handoff_mode = (
            "increase_overlap_density"
            if basis == "higher_complexity_coverage"
            else "expand_complexity_real_slice"
        )
        question = "Which single real-authority dimension still needs to be strengthened before promotion is justified?"
    else:
        handoff_mode = "strengthen_dispatch_policy_authority"
        question = "Which authority-level dispatch change is required before real promotion can be reconsidered?"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "promotion_adjudication_path": str(Path(promotion_adjudication_path).resolve()),
        "v0_4_5_handoff_mode": handoff_mode,
        "v0_4_5_primary_eval_question": question,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.4 -> v0.4.5 Handoff",
                "",
                f"- v0_4_5_handoff_mode: `{payload.get('v0_4_5_handoff_mode')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.4 -> v0.4.5 handoff.")
    parser.add_argument("--promotion-adjudication", default=str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_V0_4_5_HANDOFF_OUT_DIR))
    args = parser.parse_args()
    payload = build_v044_v0_4_5_handoff(
        promotion_adjudication_path=str(args.promotion_adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "v0_4_5_handoff_mode": payload.get("v0_4_5_handoff_mode")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
