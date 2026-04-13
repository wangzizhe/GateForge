from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_15_1_common import (
    DEFAULT_V150_CLOSEOUT_PATH,
    DEFAULT_VIABILITY_RESOLUTION_OUT_DIR,
    EXPECTED_V150_BLOCKER,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _derive_default_resolution(v150_closeout_path: str) -> dict:
    upstream = load_json(v150_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}
    governance_pack = upstream.get("governance_pack") if isinstance(upstream.get("governance_pack"), dict) else {}
    admission = (
        governance_pack.get("even_broader_change_admission")
        if isinstance(governance_pack.get("even_broader_change_admission"), dict)
        else {}
    )
    comparison_protocol = (
        governance_pack.get("pre_post_even_broader_change_comparison_protocol")
        if isinstance(governance_pack.get("pre_post_even_broader_change_comparison_protocol"), dict)
        else {}
    )
    same_source_possible = (
        comparison_protocol.get("baseline_execution_source") == "agent_modelica_live_executor_v1"
        and comparison_protocol.get("post_change_execution_source_requirement") == "agent_modelica_live_executor_v1"
        and bool(comparison_protocol.get("same_case_requirement"))
        and bool(comparison_protocol.get("runtime_measurement_required"))
    )
    return {
        "execution_arc_viability_status": "not_justified",
        "scope_relevant_uncertainty_remains": False,
        "named_viability_question": "",
        "expected_information_gain": "marginal",
        "concrete_first_pack_available": False,
        "same_source_comparison_still_possible": same_source_possible,
        "admitted_candidate_ids_if_ready": [],
        "named_reason_if_not_justified": conclusion.get("named_reason_if_not_justified") or EXPECTED_V150_BLOCKER,
    }


def build_v151_viability_resolution(
    *,
    v150_closeout_path: str = str(DEFAULT_V150_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_VIABILITY_RESOLUTION_OUT_DIR),
    execution_arc_viability_status: str | None = None,
    scope_relevant_uncertainty_remains: bool | None = None,
    named_viability_question: str | None = None,
    expected_information_gain: str | None = None,
    concrete_first_pack_available: bool | None = None,
    same_source_comparison_still_possible: bool | None = None,
    admitted_candidate_ids_if_ready: list[str] | None = None,
    named_reason_if_not_justified: str | None = None,
) -> dict:
    derived = _derive_default_resolution(v150_closeout_path)
    if execution_arc_viability_status is None:
        execution_arc_viability_status = derived["execution_arc_viability_status"]
    if scope_relevant_uncertainty_remains is None:
        scope_relevant_uncertainty_remains = derived["scope_relevant_uncertainty_remains"]
    if named_viability_question is None:
        named_viability_question = derived["named_viability_question"]
    if expected_information_gain is None:
        expected_information_gain = derived["expected_information_gain"]
    if concrete_first_pack_available is None:
        concrete_first_pack_available = derived["concrete_first_pack_available"]
    if same_source_comparison_still_possible is None:
        same_source_comparison_still_possible = derived["same_source_comparison_still_possible"]
    if admitted_candidate_ids_if_ready is None:
        admitted_candidate_ids_if_ready = list(derived["admitted_candidate_ids_if_ready"])
    if named_reason_if_not_justified is None:
        named_reason_if_not_justified = derived["named_reason_if_not_justified"]

    if execution_arc_viability_status not in {"justified", "not_justified", "invalid"}:
        execution_arc_viability_status = "invalid"

    if expected_information_gain not in {"marginal", "non_marginal"}:
        execution_arc_viability_status = "invalid"

    if execution_arc_viability_status == "justified":
        justified_ok = all(
            [
                scope_relevant_uncertainty_remains is True,
                expected_information_gain == "non_marginal",
                concrete_first_pack_available is True,
                same_source_comparison_still_possible is True,
                bool(admitted_candidate_ids_if_ready),
                bool(named_viability_question),
            ]
        )
        if not justified_ok:
            execution_arc_viability_status = "invalid"
    elif execution_arc_viability_status == "not_justified":
        scope_relevant_uncertainty_remains = bool(scope_relevant_uncertainty_remains and bool(named_viability_question))
        admitted_candidate_ids_if_ready = []
        concrete_first_pack_available = False
        if not named_reason_if_not_justified:
            named_reason_if_not_justified = EXPECTED_V150_BLOCKER

    named_first_even_broader_change_pack_ready = execution_arc_viability_status == "justified" and bool(admitted_candidate_ids_if_ready)
    named_first_even_broader_change_pack_ids = admitted_candidate_ids_if_ready if named_first_even_broader_change_pack_ready else []
    pack_readiness_status = "ready" if named_first_even_broader_change_pack_ready else ("invalid" if execution_arc_viability_status == "invalid" else "not_ready")
    if named_first_even_broader_change_pack_ready:
        pack_readiness_reason = "A concrete same-source-comparable first even-broader pack is available."
    elif execution_arc_viability_status == "invalid":
        pack_readiness_reason = "The viability reassessment is internally inconsistent."
    else:
        pack_readiness_reason = "No concrete first even-broader pack is yet justified for execution."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_viability_resolution",
        "generated_at_utc": now_utc(),
        "status": "PASS" if execution_arc_viability_status != "invalid" else "FAIL",
        "execution_arc_viability_reassessment_object": {
            "execution_arc_viability_status": execution_arc_viability_status,
            "scope_relevant_uncertainty_remains": scope_relevant_uncertainty_remains,
            "named_viability_question": named_viability_question,
            "expected_information_gain": expected_information_gain,
            "concrete_first_pack_available": concrete_first_pack_available,
            "same_source_comparison_still_possible": same_source_comparison_still_possible,
            "admitted_candidate_ids_if_ready": admitted_candidate_ids_if_ready,
            "named_reason_if_not_justified": named_reason_if_not_justified if execution_arc_viability_status != "justified" else "",
        },
        "first_even_broader_pack_readiness_object": {
            "named_first_even_broader_change_pack_ready": named_first_even_broader_change_pack_ready,
            "named_first_even_broader_change_pack_ids": named_first_even_broader_change_pack_ids,
            "pack_readiness_status": pack_readiness_status,
            "pack_readiness_reason": pack_readiness_reason,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.15.1 Viability Resolution",
                "",
                f"- execution_arc_viability_status: `{execution_arc_viability_status}`",
                f"- named_first_even_broader_change_pack_ready: `{named_first_even_broader_change_pack_ready}`",
                f"- expected_information_gain: `{expected_information_gain}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.15.1 viability-resolution artifact.")
    parser.add_argument("--v150-closeout", default=str(DEFAULT_V150_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_VIABILITY_RESOLUTION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v151_viability_resolution(
        v150_closeout_path=str(args.v150_closeout),
        out_dir=str(args.out_dir),
    )
    resolution = payload.get("execution_arc_viability_reassessment_object") or {}
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "execution_arc_viability_status": resolution.get("execution_arc_viability_status"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
