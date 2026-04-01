from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_6_comparative_reopen_checkpoint"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_6_comparative_reopen_checkpoint"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def build_comparative_reopen_checkpoint(
    *,
    refreshed_summary_path: str,
    dev_priorities_summary_path: str,
    verifier_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    refreshed = _load_json(refreshed_summary_path)
    dev = _load_json(dev_priorities_summary_path)
    verifier = _load_json(verifier_summary_path)

    lane = refreshed.get("lane_summary") if isinstance(refreshed.get("lane_summary"), dict) else {}
    block_a_green = _norm(lane.get("lane_status")) == "FREEZE_READY"
    block_b_green = _norm(dev.get("status")) == "PASS" and bool((dev.get("next_bottleneck") or {}).get("lever") or (dev.get("deterministic_coverage_explanation") or {}).get("present"))
    block_c_green = _norm(verifier.get("status")) == "PASS"

    reopen = block_a_green and block_b_green and block_c_green
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "REOPEN" if reopen else "DEFER",
        "reopen_comparative_work": reopen,
        "inputs": {
            "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
            "dev_priorities_summary_path": str(Path(dev_priorities_summary_path).resolve()) if Path(dev_priorities_summary_path).exists() else str(dev_priorities_summary_path),
            "verifier_summary_path": str(Path(verifier_summary_path).resolve()) if Path(verifier_summary_path).exists() else str(verifier_summary_path),
        },
        "checkpoint_gates": {
            "block_a_green": block_a_green,
            "block_b_green": block_b_green,
            "block_c_green": block_c_green,
        },
        "reason": (
            "All Block A/B/C gates are green; comparative work may reopen inside v0.3.6."
            if reopen
            else "Comparative work remains maintenance-only because the v0.3.6 harder lane / priorities / verifier gates are not all green."
        ),
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.6 Comparative Reopen Checkpoint",
                "",
                f"- status: `{payload['status']}`",
                f"- reopen_comparative_work: `{payload['reopen_comparative_work']}`",
                f"- block_a_green: `{payload['checkpoint_gates']['block_a_green']}`",
                f"- block_b_green: `{payload['checkpoint_gates']['block_b_green']}`",
                f"- block_c_green: `{payload['checkpoint_gates']['block_c_green']}`",
                f"- reason: `{payload['reason']}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the fixed v0.3.6 comparative reopen checkpoint artifact.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--dev-priorities-summary", required=True)
    parser.add_argument("--verifier-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_comparative_reopen_checkpoint(
        refreshed_summary_path=str(args.refreshed_summary),
        dev_priorities_summary_path=str(args.dev_priorities_summary),
        verifier_summary_path=str(args.verifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "reopen_comparative_work": payload.get("reopen_comparative_work")}))


if __name__ == "__main__":
    main()
