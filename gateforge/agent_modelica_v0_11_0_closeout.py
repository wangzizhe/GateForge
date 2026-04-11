from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_0_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V103_CLOSEOUT_PATH,
    DEFAULT_V104_CLOSEOUT_PATH,
    DEFAULT_V106_CLOSEOUT_PATH,
    DEFAULT_V108_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_11_0_governance_pack import build_v110_governance_pack
from .agent_modelica_v0_11_0_handoff_integrity import build_v110_handoff_integrity


def build_v110_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    governance_pack_path: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"),
    v103_closeout_path: str = str(DEFAULT_V103_CLOSEOUT_PATH),
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    v106_closeout_path: str = str(DEFAULT_V106_CLOSEOUT_PATH),
    v108_closeout_path: str = str(DEFAULT_V108_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    governance_path_obj = Path(governance_pack_path)

    if not handoff_path_obj.exists():
        build_v110_handoff_integrity(
            v103_closeout_path=v103_closeout_path,
            v104_closeout_path=v104_closeout_path,
            v106_closeout_path=v106_closeout_path,
            v108_closeout_path=v108_closeout_path,
            out_dir=str(handoff_path_obj.parent),
        )
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_11_0_HANDOFF_PHASE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_11_0_handoff_phase_inputs_invalid",
                "product_gap_governance_status": "invalid",
                "baseline_anchor_pass": False,
                "v0_11_1_handoff_mode": "rebuild_v0_11_0_governance_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.11.0 Closeout\n\n- version_decision: `v0_11_0_handoff_phase_inputs_invalid`\n")
        return payload

    if not governance_path_obj.exists():
        build_v110_governance_pack(
            v103_closeout_path=v103_closeout_path,
            v104_closeout_path=v104_closeout_path,
            v106_closeout_path=v106_closeout_path,
            v108_closeout_path=v108_closeout_path,
            out_dir=str(governance_path_obj.parent),
        )
    governance = load_json(governance_pack_path)

    context_contract = governance.get("context_contract", {})
    anti = governance.get("anti_reward_hacking_checklist", {})
    sidecar = governance.get("product_gap_sidecar", {})
    scope = governance.get("protocol_robustness_scope", {})
    patches = governance.get("patch_candidates", {})
    baseline_anchor = governance.get("baseline_anchor", {})

    statuses = {
        "context_contract_status": context_contract.get("context_contract_status", "partial"),
        "anti_reward_hacking_checklist_status": anti.get("checklist_status", "partial"),
        "product_gap_sidecar_status": sidecar.get("product_gap_sidecar_status", "partial"),
        "protocol_robustness_scope_status": scope.get("scope_status", "partial"),
        "patch_candidate_pack_status": patches.get("patch_candidate_pack_status", "partial"),
    }
    baseline_anchor_pass = bool(baseline_anchor.get("baseline_anchor_pass"))

    if baseline_anchor_pass and all(value == "ready" for value in statuses.values()):
        governance_status = "ready"
        version_decision = "v0_11_0_product_gap_governance_ready"
        handoff_mode = "execute_first_product_gap_patch_pack"
        status = "PASS"
        why = "The minimum product-gap governance objects are frozen, the carried real-origin baseline remains explicit, and the first bounded patch pack can now execute under governed semantics."
    elif baseline_anchor_pass and any(value == "ready" for value in statuses.values()):
        governance_status = "partial"
        version_decision = "v0_11_0_product_gap_governance_partial"
        handoff_mode = "finish_product_gap_governance_minimums_first"
        status = "PASS"
        why = "The carried baseline anchor is intact and some governance objects are structurally useful, but at least one minimum-form product-gap object remains incomplete and must be frozen before execution-phase interpretation can proceed."
    else:
        governance_status = "invalid"
        version_decision = "v0_11_0_handoff_phase_inputs_invalid"
        handoff_mode = "rebuild_v0_11_0_governance_inputs_first"
        status = "FAIL"
        why = "The carried baseline anchor or the phase handoff is invalid, so product-gap governance cannot be trusted yet."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "product_gap_governance_status": governance_status,
            "context_contract_status": statuses["context_contract_status"],
            "anti_reward_hacking_checklist_status": statuses["anti_reward_hacking_checklist_status"],
            "product_gap_sidecar_status": statuses["product_gap_sidecar_status"],
            "protocol_robustness_scope_status": statuses["protocol_robustness_scope_status"],
            "patch_candidate_pack_status": statuses["patch_candidate_pack_status"],
            "baseline_anchor_pass": baseline_anchor_pass,
            "why_this_is_or_is_not_ready": why,
            "v0_11_1_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "governance_pack": governance,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.0 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- product_gap_governance_status: `{governance_status}`",
                f"- baseline_anchor_pass: `{baseline_anchor_pass}`",
                f"- v0_11_1_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.0 product-gap governance closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--governance-pack", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v103-closeout", default=str(DEFAULT_V103_CLOSEOUT_PATH))
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--v106-closeout", default=str(DEFAULT_V106_CLOSEOUT_PATH))
    parser.add_argument("--v108-closeout", default=str(DEFAULT_V108_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v110_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        governance_pack_path=str(args.governance_pack),
        v103_closeout_path=str(args.v103_closeout),
        v104_closeout_path=str(args.v104_closeout),
        v106_closeout_path=str(args.v106_closeout),
        v108_closeout_path=str(args.v108_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
