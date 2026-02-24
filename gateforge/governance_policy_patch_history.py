from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        rows.append(json.loads(s))
    return rows


def _append_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True))
            f.write("\n")


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    status_counts = summary.get("status_counts", {})
    lines = [
        "# GateForge Policy Patch History",
        "",
        f"- total_records: `{summary.get('total_records')}`",
        f"- latest_status: `{summary.get('latest_status')}`",
        f"- pass_count: `{status_counts.get('PASS', 0)}`",
        f"- needs_review_count: `{status_counts.get('NEEDS_REVIEW', 0)}`",
        f"- fail_count: `{status_counts.get('FAIL', 0)}`",
        f"- applied_count: `{summary.get('applied_count', 0)}`",
            f"- reject_count: `{summary.get('reject_count', 0)}`",
        f"- pairwise_threshold_enabled_count: `{summary.get('pairwise_threshold_enabled_count', 0)}`",
        f"- latest_pairwise_threshold: `{summary.get('latest_pairwise_threshold')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append policy patch apply summaries to history ledger and aggregate KPIs")
    parser.add_argument(
        "--record",
        action="append",
        default=[],
        help="Path to governance_policy_patch_apply summary JSON (repeatable)",
    )
    parser.add_argument(
        "--ledger",
        default="artifacts/governance_policy_patch_history/history.jsonl",
        help="History ledger JSONL path",
    )
    parser.add_argument(
        "--out",
        default="artifacts/governance_policy_patch_history/summary.json",
        help="Summary JSON path",
    )
    parser.add_argument("--report", default=None, help="Summary markdown path")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)

    append_rows: list[dict] = []
    for record_path in args.record:
        payload = _load_json(record_path)
        proposal_path = payload.get("proposal_path")
        proposal_payload = {}
        if isinstance(proposal_path, str) and proposal_path:
            proposal_file = Path(proposal_path)
            if proposal_file.exists():
                proposal_payload = _load_json(str(proposal_file))
        policy_after = proposal_payload.get("policy_after") if isinstance(proposal_payload.get("policy_after"), dict) else {}
        pairwise_threshold = policy_after.get("require_min_pairwise_net_margin")
        row = {
            "recorded_at_utc": now,
            "source_record_path": record_path,
            "proposal_id": payload.get("proposal_id"),
            "final_status": payload.get("final_status"),
            "apply_action": payload.get("apply_action"),
            "approval_decision": payload.get("approval_decision"),
            "approval_decisions": payload.get("approval_decisions"),
            "applied": bool(payload.get("applied")),
            "reasons_count": len(payload.get("reasons", []) or []),
            "target_policy_path": payload.get("target_policy_path"),
            "proposal_path": proposal_path,
            "pairwise_threshold": pairwise_threshold,
        }
        append_rows.append(row)

    if append_rows:
        _append_rows(ledger_path, append_rows)

    rows = _load_ledger(ledger_path)
    status_counter = Counter()
    applied_count = 0
    reject_count = 0
    pairwise_threshold_enabled_count = 0
    latest_pairwise_threshold: int | None = None
    for row in rows:
        status = str(row.get("final_status") or "")
        if status:
            status_counter[status] += 1
        if bool(row.get("applied")):
            applied_count += 1
        decisions = row.get("approval_decisions")
        decision_values: list[str] = []
        if isinstance(decisions, list):
            decision_values.extend([str(x or "").lower() for x in decisions])
        else:
            decision_values.append(str(row.get("approval_decision") or "").lower())
        if any(x == "reject" for x in decision_values):
            reject_count += 1
        pairwise_threshold = row.get("pairwise_threshold")
        if isinstance(pairwise_threshold, int) and pairwise_threshold > 0:
            pairwise_threshold_enabled_count += 1
            latest_pairwise_threshold = pairwise_threshold

    latest_status = rows[-1].get("final_status") if rows else None
    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": len(rows),
        "latest_status": latest_status,
        "status_counts": dict(status_counter),
        "applied_count": applied_count,
        "reject_count": reject_count,
        "pairwise_threshold_enabled_count": pairwise_threshold_enabled_count,
        "latest_pairwise_threshold": latest_pairwise_threshold,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": summary["total_records"], "latest_status": summary["latest_status"]}))


if __name__ == "__main__":
    main()
