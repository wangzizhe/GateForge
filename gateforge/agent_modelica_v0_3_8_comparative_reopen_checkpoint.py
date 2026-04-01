from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_8_comparative_reopen_checkpoint"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_8_comparative_reopen_checkpoint"


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


def build_v0_3_8_comparative_reopen_checkpoint(
    *,
    refreshed_summary_path: str,
    dev_priorities_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    refreshed = _load_json(refreshed_summary_path)
    dev = _load_json(dev_priorities_summary_path)
    metrics = refreshed.get("metrics") if isinstance(refreshed.get("metrics"), dict) else {}
    dev_status = str(dev.get("status") or "")
    should_reopen = False
    reason = "maintenance_only_default"
    if (
        float(metrics.get("branch_switch_evidenced_success_pct") or 0.0) >= 40.0
        and int(metrics.get("success_after_branch_switch_count") or 0) >= 3
        and dev_status == "PASS"
    ):
        should_reopen = False
        reason = "checkpoint_green_but_reopen_deferred_by_version_scope"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "decision": "DEFER",
        "should_reopen": should_reopen,
        "reason": reason,
        "comparative_mode": "maintenance_only",
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", "\n".join(["# v0.3.8 Comparative Reopen Checkpoint", "", f"- decision: `{payload['decision']}`", f"- reason: `{payload['reason']}`", ""]))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the fixed v0.3.8 comparative reopen checkpoint artifact.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--dev-priorities-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_8_comparative_reopen_checkpoint(
        refreshed_summary_path=str(args.refreshed_summary),
        dev_priorities_summary_path=str(args.dev_priorities_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))


if __name__ == "__main__":
    main()
