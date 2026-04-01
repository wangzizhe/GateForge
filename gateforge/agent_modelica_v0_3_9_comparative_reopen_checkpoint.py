from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_9_comparative_reopen_checkpoint"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_9_comparative_reopen_checkpoint"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_v0_3_9_comparative_reopen_checkpoint(
    *,
    block_b_decision_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    decision = _load_json(block_b_decision_summary_path)
    block_b = str(decision.get("decision") or "")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "decision": "DEFER",
        "reason": "maintenance_only_comparative_route",
        "block_b_decision": block_b,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", "\n".join(["# v0.3.9 Comparative Reopen Checkpoint", "", "- decision: `DEFER`", ""]))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.9 comparative reopen checkpoint artifact.")
    parser.add_argument("--block-b-decision-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_9_comparative_reopen_checkpoint(
        block_b_decision_summary_path=str(args.block_b_decision_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))


if __name__ == "__main__":
    main()
