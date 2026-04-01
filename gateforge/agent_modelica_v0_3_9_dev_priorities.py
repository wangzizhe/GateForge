from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_9_dev_priorities"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_9_dev_priorities"


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


def build_v0_3_9_dev_priorities(
    *,
    manifests_summary_path: str,
    block_b_decision_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    manifests = _load_json(manifests_summary_path)
    decision = _load_json(block_b_decision_summary_path)

    block_b_decision = str(decision.get("decision") or "")
    hypothesis = str(decision.get("replacement_hypothesis") or "")
    if block_b_decision == "replacement_hypothesis_supported" and hypothesis:
        status = "PASS"
        next_hypothesis = hypothesis
        reason = "replacement_hypothesis_supported"
    else:
        status = "PARTIAL"
        next_hypothesis = ""
        reason = str(decision.get("reason") or "")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "primary_direction": {
            "mainline_task_count": int(((manifests.get("metrics") or {}).get("mainline_task_count") or 0)),
            "contrast_task_count": int(((manifests.get("metrics") or {}).get("contrast_task_count") or 0)),
            "explicit_branch_switch_subset_count": int(((manifests.get("metrics") or {}).get("explicit_branch_switch_subset_count") or 0)),
        },
        "next_hypothesis": {
            "lever": next_hypothesis,
            "reason": reason,
            "identified": bool(next_hypothesis),
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.9 Dev Priorities",
                "",
                f"- status: `{status}`",
                f"- next_hypothesis: `{next_hypothesis}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.9 development-priority summary.")
    parser.add_argument("--manifests-summary", required=True)
    parser.add_argument("--block-b-decision-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_9_dev_priorities(
        manifests_summary_path=str(args.manifests_summary),
        block_b_decision_summary_path=str(args.block_b_decision_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_hypothesis": (payload.get("next_hypothesis") or {}).get("lever")}))


if __name__ == "__main__":
    main()
