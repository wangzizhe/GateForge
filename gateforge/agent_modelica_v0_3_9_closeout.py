from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_9_closeout"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_9_closeout"


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


def build_v0_3_9_closeout(
    *,
    manifests_summary_path: str,
    block_b_decision_summary_path: str,
    dev_priorities_summary_path: str,
    verifier_summary_path: str,
    comparative_checkpoint_summary_path: str,
    previous_closeout_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    manifests = _load_json(manifests_summary_path)
    decision = _load_json(block_b_decision_summary_path)
    dev = _load_json(dev_priorities_summary_path)
    verifier = _load_json(verifier_summary_path)
    checkpoint = _load_json(comparative_checkpoint_summary_path)
    previous = _load_json(previous_closeout_summary_path)

    verifier_status = str(verifier.get("status") or "")
    block_b = str(decision.get("decision") or "")
    replacement_hypothesis = str(decision.get("replacement_hypothesis") or "")
    mainline_count = int(((manifests.get("metrics") or {}).get("mainline_task_count") or 0))

    if verifier_status != "PASS":
        status = "FAIL"
        classification = "v0_3_9_closeout_blocked_by_verifier"
    elif block_b == "replacement_hypothesis_supported" and mainline_count >= 8:
        status = "PASS"
        classification = "alternative_absorption_mechanism_replaces_branch_switch"
    elif block_b == "promotion_path_supported":
        status = "PASS"
        classification = "branch_switch_promotion_path_supported_but_unfinished"
    else:
        status = "FAIL"
        classification = "branch_switch_promotion_v0_3_9_blocked"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "classification": classification,
        "inputs": {
            "manifests_summary_path": str(Path(manifests_summary_path).resolve()) if Path(manifests_summary_path).exists() else str(manifests_summary_path),
            "block_b_decision_summary_path": str(Path(block_b_decision_summary_path).resolve()) if Path(block_b_decision_summary_path).exists() else str(block_b_decision_summary_path),
            "dev_priorities_summary_path": str(Path(dev_priorities_summary_path).resolve()) if Path(dev_priorities_summary_path).exists() else str(dev_priorities_summary_path),
            "verifier_summary_path": str(Path(verifier_summary_path).resolve()) if Path(verifier_summary_path).exists() else str(verifier_summary_path),
            "comparative_checkpoint_summary_path": str(Path(comparative_checkpoint_summary_path).resolve()) if Path(comparative_checkpoint_summary_path).exists() else str(comparative_checkpoint_summary_path),
            "previous_closeout_summary_path": str(Path(previous_closeout_summary_path).resolve()) if Path(previous_closeout_summary_path).exists() else str(previous_closeout_summary_path),
        },
        "metrics": {
            "previous_classification": str(previous.get("classification") or ""),
            "mainline_task_count": mainline_count,
            "contrast_task_count": int(((manifests.get("metrics") or {}).get("contrast_task_count") or 0)),
            "block_b_decision": block_b,
            "replacement_hypothesis": replacement_hypothesis,
            "verifier_status": verifier_status,
            "checkpoint_decision": str(checkpoint.get("decision") or ""),
            "dev_status": str(dev.get("status") or ""),
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", "\n".join(["# v0.3.9 Closeout", "", f"- classification: `{classification}`", ""]))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.9 release closeout summary.")
    parser.add_argument("--manifests-summary", required=True)
    parser.add_argument("--block-b-decision-summary", required=True)
    parser.add_argument("--dev-priorities-summary", required=True)
    parser.add_argument("--verifier-summary", required=True)
    parser.add_argument("--comparative-checkpoint-summary", required=True)
    parser.add_argument("--previous-closeout-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_9_closeout(
        manifests_summary_path=str(args.manifests_summary),
        block_b_decision_summary_path=str(args.block_b_decision_summary),
        dev_priorities_summary_path=str(args.dev_priorities_summary),
        verifier_summary_path=str(args.verifier_summary),
        comparative_checkpoint_summary_path=str(args.comparative_checkpoint_summary),
        previous_closeout_summary_path=str(args.previous_closeout_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
