from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_5_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V084_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v085_handoff_integrity(
    *,
    v084_closeout_path: str = str(DEFAULT_V084_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v084_closeout_path)
    conclusion = closeout.get("conclusion") or {}

    checks = {
        "version_decision_ok": conclusion.get("version_decision")
        == "v0_8_4_workflow_readiness_partial_but_interpretable",
        "handoff_mode_ok": conclusion.get("v0_8_5_handoff_mode")
        == "decide_if_one_more_same_logic_refinement_is_worth_it",
        "adjudication_route_ok": conclusion.get("adjudication_route")
        == "workflow_readiness_partial_but_interpretable",
        "adjudication_route_count_ok": int(conclusion.get("adjudication_route_count") or 0) == 1,
        "legacy_sidecar_ok": bool(conclusion.get("legacy_bucket_sidecar_still_interpretable")),
        "execution_source_ok": (
            ((closeout.get("handoff_integrity") or {}).get("upstream_execution_source"))
            == "gateforge_run_contract_live_path"
        ),
    }
    passed = all(checks.values())
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed else "FAIL",
        "handoff_integrity_status": "PASS" if passed else "FAIL",
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_8_5_handoff_mode"),
        "upstream_adjudication_route": conclusion.get("adjudication_route"),
        "upstream_execution_source": ((closeout.get("handoff_integrity") or {}).get("upstream_execution_source")),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.5 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_adjudication_route: `{payload['upstream_adjudication_route']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.5 handoff integrity artifact.")
    parser.add_argument("--v084-closeout", default=str(DEFAULT_V084_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v085_handoff_integrity(
        v084_closeout_path=str(args.v084_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
