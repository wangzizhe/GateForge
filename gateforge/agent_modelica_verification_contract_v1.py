from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_verification_contract_v1"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_verification_contract(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_verification_contract(
    *,
    verifier_profile_id: str,
    verified_flow: str,
    inputs: dict,
    checks: list[dict],
) -> dict:
    passed = all(bool(item.get("passed")) for item in checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "verifier_profile_id": str(verifier_profile_id),
        "verified_flow": str(verified_flow),
        "status": "PASS" if passed else "FAIL",
        "inputs": dict(inputs),
        "checks": list(checks),
    }
