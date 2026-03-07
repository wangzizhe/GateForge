#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L2_DELIVERY_OUT_DIR:-artifacts/agent_modelica_l2_delivery_pack_v0}"
CONTRACT_SNAPSHOT="${GATEFORGE_AGENT_L2_CONTRACT_SNAPSHOT:-assets_private/agent_modelica_l2_contract_snapshot_v0/contract_snapshot.json}"
DUAL_GATE_SUMMARY="${GATEFORGE_AGENT_L2_DUAL_GATE_SUMMARY:-artifacts/agent_modelica_l2_dual_gate_v0/summary.json}"
FREEZE_MANIFEST="${GATEFORGE_AGENT_L2_FREEZE_MANIFEST:-assets_private/agent_modelica_l2_freeze_pack_v0/freeze_manifest.json}"
STABILITY_SUMMARY="${GATEFORGE_AGENT_L2_STABILITY_SUMMARY:-artifacts/agent_modelica_l2_stability_regression_v0/summary.json}"

mkdir -p "$OUT_DIR"

export GATEFORGE_AGENT_L2_DELIVERY_OUT_DIR="$OUT_DIR"
export GATEFORGE_AGENT_L2_CONTRACT_SNAPSHOT="$CONTRACT_SNAPSHOT"
export GATEFORGE_AGENT_L2_DUAL_GATE_SUMMARY="$DUAL_GATE_SUMMARY"
export GATEFORGE_AGENT_L2_FREEZE_MANIFEST="$FREEZE_MANIFEST"
export GATEFORGE_AGENT_L2_STABILITY_SUMMARY="$STABILITY_SUMMARY"
python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(os.environ["GATEFORGE_AGENT_L2_DELIVERY_OUT_DIR"])

def load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

contract = load(os.environ["GATEFORGE_AGENT_L2_CONTRACT_SNAPSHOT"])
dual = load(os.environ["GATEFORGE_AGENT_L2_DUAL_GATE_SUMMARY"])
freeze = load(os.environ["GATEFORGE_AGENT_L2_FREEZE_MANIFEST"])
stability = load(os.environ["GATEFORGE_AGENT_L2_STABILITY_SUMMARY"])

reasons = []
if str(contract.get("status") or "FAIL") != "PASS":
    reasons.append("contract_snapshot_not_pass")
if str(dual.get("status") or "FAIL") != "PASS":
    reasons.append("dual_gate_not_pass")
if str(freeze.get("status") or "FAIL") != "PASS":
    reasons.append("freeze_manifest_not_pass")
if str(stability.get("status") or "FAIL") != "PASS":
    reasons.append("stability_regression_not_pass")
status = "PASS" if not reasons else "FAIL"

payload = {
    "schema_version": "agent_modelica_l2_delivery_pack_v0",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "reasons": reasons,
    "highlights": {
        "dual_gate_compile_pass_rate_pct": dual.get("compile_pass_rate_pct"),
        "dual_gate_infra_failure_count": dual.get("infra_failure_count"),
        "stability_run1_success_at_k_pct": (stability.get("run1") or {}).get("success_at_k_pct"),
        "stability_run2_success_at_k_pct": (stability.get("run2") or {}).get("success_at_k_pct"),
        "stability_run1_infra_failure_count": (stability.get("run1") or {}).get("infra_failure_count"),
        "stability_run2_infra_failure_count": (stability.get("run2") or {}).get("infra_failure_count"),
    },
    "sources": {
        "contract_snapshot": os.environ["GATEFORGE_AGENT_L2_CONTRACT_SNAPSHOT"],
        "dual_gate_summary": os.environ["GATEFORGE_AGENT_L2_DUAL_GATE_SUMMARY"],
        "freeze_manifest": os.environ["GATEFORGE_AGENT_L2_FREEZE_MANIFEST"],
        "stability_summary": os.environ["GATEFORGE_AGENT_L2_STABILITY_SUMMARY"],
    },
}

(out_dir / "delivery_pack.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
(out_dir / "delivery_pack.md").write_text(
    "\n".join(
        [
            "# Agent Modelica L2 Delivery Pack v0",
            "",
            f"- status: `{status}`",
            f"- reasons: `{reasons}`",
            f"- dual_gate_compile_pass_rate_pct: `{payload['highlights']['dual_gate_compile_pass_rate_pct']}`",
            f"- stability_run1_success_at_k_pct: `{payload['highlights']['stability_run1_success_at_k_pct']}`",
            f"- stability_run2_success_at_k_pct: `{payload['highlights']['stability_run2_success_at_k_pct']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"status": status, "reasons": reasons}))
if status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/delivery_pack.json"
