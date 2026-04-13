from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_14_2_common import (
    ALLOWED_CANDIDATE_BROADER_CHANGE_SHAPES,
    CARRIED_DOMINANT_GAP_FAMILY,
    DEFAULT_NAMED_BLOCKER,
    DEFAULT_REMAINING_BROADER_CHANGE_SCOPE_ASSESSMENT_OUT_DIR,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V140_GOVERNANCE_PACK_PATH,
    DEFAULT_V141_CLOSEOUT_PATH,
    EXPECTED_V115_FORMAL_LABEL,
    EXPECTED_V140_ADMITTED_BROADER_CHANGE_IDS,
    SCHEMA_PREFIX,
    SCOPE_STATUS_NO_STRONGER,
    SCOPE_STATUS_STRONGER_IN_SCOPE,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _read_v115_gap_fields(v115_closeout_path: str) -> tuple[str, str]:
    v115 = load_json(v115_closeout_path)
    conclusion = v115.get("conclusion") if isinstance(v115.get("conclusion"), dict) else {}
    formal_label = str(conclusion.get("formal_adjudication_label") or "")
    dominant_gap = str(conclusion.get("dominant_gap_family_readout") or "")
    if not dominant_gap:
        dominant_gap = CARRIED_DOMINANT_GAP_FAMILY
    return formal_label, dominant_gap


def _read_v140_admitted_ids(v140_governance_pack_path: str) -> frozenset[str]:
    v140 = load_json(v140_governance_pack_path)
    admission = (
        v140.get("broader_change_admission")
        if isinstance(v140.get("broader_change_admission"), dict)
        else {}
    )
    admitted_rows = list(admission.get("admitted_rows") or [])
    return frozenset(str(row.get("candidate_id") or "") for row in admitted_rows if isinstance(row, dict))


def build_v142_remaining_broader_change_scope_assessment(
    *,
    v141_closeout_path: str = str(DEFAULT_V141_CLOSEOUT_PATH),
    v140_governance_pack_path: str = str(DEFAULT_V140_GOVERNANCE_PACK_PATH),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_REMAINING_BROADER_CHANGE_SCOPE_ASSESSMENT_OUT_DIR),
    scope_relevant_uncertainty_remains: bool | None = None,
    uncertainty_is_stronger_change_addressable: bool | None = None,
    expected_information_gain: str | None = None,
    candidate_next_broader_change_shape: str | None = None,
    named_blocker_if_not_in_scope: str | None = None,
) -> dict:
    v141 = load_json(v141_closeout_path)
    v141_conclusion = v141.get("conclusion") if isinstance(v141.get("conclusion"), dict) else {}
    first_pack_result_readout = str(v141_conclusion.get("broader_change_effect_class") or "")

    formal_label, remaining_gap_family_readout = _read_v115_gap_fields(v115_closeout_path)
    admitted_ids = _read_v140_admitted_ids(v140_governance_pack_path)

    if scope_relevant_uncertainty_remains is None:
        scope_relevant_uncertainty_remains = False
    if uncertainty_is_stronger_change_addressable is None:
        uncertainty_is_stronger_change_addressable = False
    if candidate_next_broader_change_shape is None:
        candidate_next_broader_change_shape = "none"
    if named_blocker_if_not_in_scope is None:
        named_blocker_if_not_in_scope = DEFAULT_NAMED_BLOCKER

    if candidate_next_broader_change_shape not in ALLOWED_CANDIDATE_BROADER_CHANGE_SHAPES:
        candidate_next_broader_change_shape = "none"

    if not scope_relevant_uncertainty_remains:
        expected_information_gain = "marginal"
    elif expected_information_gain is None:
        expected_information_gain = "marginal"

    if expected_information_gain not in {"marginal", "non_marginal"}:
        expected_information_gain = "marginal"

    if not uncertainty_is_stronger_change_addressable:
        candidate_next_broader_change_shape = "none"

    if (
        scope_relevant_uncertainty_remains
        and uncertainty_is_stronger_change_addressable
        and expected_information_gain == "non_marginal"
        and candidate_next_broader_change_shape != "none"
    ):
        remaining_scope_status = SCOPE_STATUS_STRONGER_IN_SCOPE
    else:
        remaining_scope_status = SCOPE_STATUS_NO_STRONGER

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_remaining_broader_change_scope_assessment",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "remaining_broader_change_scope_object": {
            "remaining_scope_status": remaining_scope_status,
            "remaining_gap_family_readout": remaining_gap_family_readout,
            "first_pack_result_readout": first_pack_result_readout,
            "scope_relevant_uncertainty_remains": scope_relevant_uncertainty_remains,
            "uncertainty_is_stronger_change_addressable": uncertainty_is_stronger_change_addressable,
            "expected_information_gain": expected_information_gain,
            "candidate_next_broader_change_shape": candidate_next_broader_change_shape,
            "named_blocker_if_not_in_scope": (
                "" if remaining_scope_status == SCOPE_STATUS_STRONGER_IN_SCOPE else named_blocker_if_not_in_scope
            ),
            "carried_formal_adjudication_label": formal_label,
            "carried_formal_adjudication_label_match_expected": formal_label == EXPECTED_V115_FORMAL_LABEL,
            "admitted_broader_change_ids_reference": sorted(admitted_ids),
            "admitted_broader_change_ids_match_expected": admitted_ids == EXPECTED_V140_ADMITTED_BROADER_CHANGE_IDS,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.14.2 Remaining Broader Change Scope Assessment",
                "",
                f"- remaining_scope_status: `{remaining_scope_status}`",
                f"- first_pack_result_readout: `{first_pack_result_readout}`",
                f"- remaining_gap_family_readout: `{remaining_gap_family_readout}`",
                f"- expected_information_gain: `{expected_information_gain}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.14.2 remaining broader-change scope assessment.")
    parser.add_argument("--v141-closeout", default=str(DEFAULT_V141_CLOSEOUT_PATH))
    parser.add_argument("--v140-governance-pack", default=str(DEFAULT_V140_GOVERNANCE_PACK_PATH))
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REMAINING_BROADER_CHANGE_SCOPE_ASSESSMENT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v142_remaining_broader_change_scope_assessment(
        v141_closeout_path=str(args.v141_closeout),
        v140_governance_pack_path=str(args.v140_governance_pack),
        v115_closeout_path=str(args.v115_closeout),
        out_dir=str(args.out_dir),
    )
    scope_obj = payload.get("remaining_broader_change_scope_object") or {}
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "remaining_scope_status": scope_obj.get("remaining_scope_status"),
                "expected_information_gain": scope_obj.get("expected_information_gain"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
