from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V110_CLOSEOUT_PATH,
    EXPECTED_V110_HANDOFF_MODE,
    EXPECTED_V110_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v111_handoff_integrity(
    *,
    v110_closeout_path: str = str(DEFAULT_V110_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    v110 = load_json(v110_closeout_path).get("conclusion", {})
    checks = {
        "version_decision_ok": v110.get("version_decision") == EXPECTED_V110_VERSION_DECISION,
        "governance_status_ok": v110.get("product_gap_governance_status") == "ready",
        "context_contract_status_ok": v110.get("context_contract_status") == "ready",
        "anti_reward_hacking_checklist_status_ok": v110.get("anti_reward_hacking_checklist_status") == "ready",
        "product_gap_sidecar_status_ok": v110.get("product_gap_sidecar_status") == "ready",
        "protocol_robustness_scope_status_ok": v110.get("protocol_robustness_scope_status") == "ready",
        "patch_candidate_pack_status_ok": v110.get("patch_candidate_pack_status") == "ready",
        "baseline_anchor_pass_ok": bool(v110.get("baseline_anchor_pass")),
        "handoff_mode_ok": v110.get("v0_11_1_handoff_mode") == EXPECTED_V110_HANDOFF_MODE,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": v110.get("version_decision"),
        "upstream_handoff_mode": v110.get("v0_11_1_handoff_mode"),
        "upstream_governance_ready": v110.get("product_gap_governance_status"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.1 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.1 handoff integrity artifact.")
    parser.add_argument("--v110-closeout", default=str(DEFAULT_V110_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v111_handoff_integrity(
        v110_closeout_path=str(args.v110_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
