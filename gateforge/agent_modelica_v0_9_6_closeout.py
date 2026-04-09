from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_6_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_EXPANSION_WORTH_IT_SUMMARY_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR,
    DEFAULT_V091_CLOSEOUT_PATH,
    DEFAULT_V092_CLOSEOUT_PATH,
    DEFAULT_V093_CLOSEOUT_PATH,
    DEFAULT_V094_CLOSEOUT_PATH,
    DEFAULT_V095_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_9_6_expansion_worth_it_summary import build_v096_expansion_worth_it_summary
from .agent_modelica_v0_9_6_handoff_integrity import build_v096_handoff_integrity
from .agent_modelica_v0_9_6_remaining_uncertainty_characterization import (
    build_v096_remaining_uncertainty_characterization,
)


def build_v096_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    remaining_uncertainty_characterization_path: str = str(
        DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR / "summary.json"
    ),
    expansion_worth_it_summary_path: str = str(
        DEFAULT_EXPANSION_WORTH_IT_SUMMARY_OUT_DIR / "summary.json"
    ),
    v095_closeout_path: str = str(DEFAULT_V095_CLOSEOUT_PATH),
    v094_closeout_path: str = str(DEFAULT_V094_CLOSEOUT_PATH),
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    v092_closeout_path: str = str(DEFAULT_V092_CLOSEOUT_PATH),
    v091_closeout_path: str = str(DEFAULT_V091_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v096_handoff_integrity(
        v095_closeout_path=v095_closeout_path,
        v094_closeout_path=v094_closeout_path,
        v093_closeout_path=v093_closeout_path,
        v092_closeout_path=v092_closeout_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_9_6_HANDOFF_DECISION_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_9_6_handoff_decision_inputs_invalid",
                "v0_9_7_handoff_mode": "rebuild_v0_9_6_decision_inputs_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.9.6 Closeout\n\n- version_decision: `v0_9_6_handoff_decision_inputs_invalid`\n")
        return payload

    if not Path(remaining_uncertainty_characterization_path).exists():
        build_v096_remaining_uncertainty_characterization(
            v095_closeout_path=v095_closeout_path,
            v094_closeout_path=v094_closeout_path,
            v093_closeout_path=v093_closeout_path,
            v092_closeout_path=v092_closeout_path,
            v091_closeout_path=v091_closeout_path,
            out_dir=str(Path(remaining_uncertainty_characterization_path).parent),
        )
    if not Path(expansion_worth_it_summary_path).exists():
        build_v096_expansion_worth_it_summary(
            remaining_uncertainty_characterization_path=remaining_uncertainty_characterization_path,
            out_dir=str(Path(expansion_worth_it_summary_path).parent),
        )

    uncertainty = load_json(remaining_uncertainty_characterization_path)
    summary = load_json(expansion_worth_it_summary_path)
    v095 = load_json(v095_closeout_path)
    route = ((v095.get("conclusion") or {}).get("final_adjudication_label"))

    justified = all(
        [
            route == "expanded_workflow_readiness_partial_but_interpretable",
            uncertainty.get("remaining_uncertainty_status") == "single_expansion_addressable_uncertainty",
            bool(uncertainty.get("remaining_uncertainty_is_depth_limited")),
            bool(uncertainty.get("remaining_uncertainty_is_authentic_expansion_addressable")),
            uncertainty.get("expected_information_gain") == "non_trivial",
        ]
    )
    invalid = any(
        [
            route != "expanded_workflow_readiness_partial_but_interpretable",
            not str(uncertainty.get("remaining_uncertainty_status") or ""),
            not str(summary.get("why_one_more_authentic_expansion_is_or_is_not_justified") or ""),
        ]
    )

    if invalid:
        decision = "v0_9_6_handoff_decision_inputs_invalid"
        handoff = "rebuild_v0_9_6_decision_inputs_first"
        status = "FAIL"
        closeout_status = "V0_9_6_HANDOFF_DECISION_INPUTS_INVALID"
    elif justified:
        decision = "v0_9_6_one_more_authentic_expansion_justified"
        handoff = "run_one_last_bounded_authentic_expansion"
        status = "PASS"
        closeout_status = "V0_9_6_ONE_MORE_AUTHENTIC_EXPANSION_JUSTIFIED"
    else:
        decision = "v0_9_6_more_authentic_expansion_not_worth_it"
        handoff = "prepare_v0_9_phase_synthesis"
        status = "PASS"
        closeout_status = "V0_9_6_MORE_AUTHENTIC_EXPANSION_NOT_WORTH_IT"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": decision,
            "remaining_uncertainty_status": uncertainty.get("remaining_uncertainty_status"),
            "remaining_uncertainty_label": uncertainty.get("remaining_uncertainty_label"),
            "remaining_uncertainty_scope": uncertainty.get("remaining_uncertainty_scope"),
            "remaining_uncertainty_is_depth_limited": uncertainty.get("remaining_uncertainty_is_depth_limited"),
            "remaining_uncertainty_is_authentic_expansion_addressable": uncertainty.get("remaining_uncertainty_is_authentic_expansion_addressable"),
            "expected_information_gain": uncertainty.get("expected_information_gain"),
            "why_one_more_authentic_expansion_is_or_is_not_justified": summary.get(
                "why_one_more_authentic_expansion_is_or_is_not_justified"
            ),
            "v0_9_7_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "remaining_uncertainty_characterization": uncertainty,
        "expansion_worth_it_summary": summary,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.6 Closeout",
                "",
                f"- version_decision: `{decision}`",
                f"- remaining_uncertainty_status: `{uncertainty.get('remaining_uncertainty_status')}`",
                f"- expected_information_gain: `{uncertainty.get('expected_information_gain')}`",
                f"- v0_9_7_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.6 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--remaining-uncertainty-characterization", default=str(DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR / "summary.json"))
    parser.add_argument("--expansion-worth-it-summary", default=str(DEFAULT_EXPANSION_WORTH_IT_SUMMARY_OUT_DIR / "summary.json"))
    parser.add_argument("--v095-closeout", default=str(DEFAULT_V095_CLOSEOUT_PATH))
    parser.add_argument("--v094-closeout", default=str(DEFAULT_V094_CLOSEOUT_PATH))
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--v092-closeout", default=str(DEFAULT_V092_CLOSEOUT_PATH))
    parser.add_argument("--v091-closeout", default=str(DEFAULT_V091_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v096_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        remaining_uncertainty_characterization_path=str(args.remaining_uncertainty_characterization),
        expansion_worth_it_summary_path=str(args.expansion_worth_it_summary),
        v095_closeout_path=str(args.v095_closeout),
        v094_closeout_path=str(args.v094_closeout),
        v093_closeout_path=str(args.v093_closeout),
        v092_closeout_path=str(args.v092_closeout),
        v091_closeout_path=str(args.v091_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
