from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True))
            f.write("\n")


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Joint Moat Strength History Ledger v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_moat_strength_score: `{payload.get('latest_moat_strength_score')}`",
        f"- latest_moat_strength_grade: `{payload.get('latest_moat_strength_grade')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append joint moat strength history and emit summary")
    parser.add_argument("--joint-moat-strength-summary", required=True)
    parser.add_argument("--ledger", default="artifacts/private_model_mutation_scale_batch_v1/state/joint_moat_strength_history.jsonl")
    parser.add_argument("--out", default="artifacts/dataset_joint_moat_strength_history_ledger_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    gate = _load_json(args.joint_moat_strength_summary)
    reasons: list[str] = []
    if not gate:
        reasons.append("joint_moat_strength_summary_missing")

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    row = {
        "recorded_at_utc": now,
        "gate_status": str(gate.get("status") or "UNKNOWN"),
        "moat_strength_score": _to_float(gate.get("moat_strength_score", 0.0)),
        "moat_strength_grade": str(gate.get("moat_strength_grade") or "F"),
        "hard_fail_count": int(gate.get("hard_fail_count", 0) or 0),
        "warning_count": int(gate.get("warning_count", 0) or 0),
    }
    if not reasons:
        _append_jsonl(ledger_path, [row])

    rows = _load_jsonl(ledger_path)
    total_records = len(rows)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) >= 2 else {}
    avg_score = round(sum(_to_float(r.get("moat_strength_score", 0.0)) for r in rows) / max(1, total_records), 4)
    delta_score = round(_to_float(latest.get("moat_strength_score", 0.0)) - _to_float(previous.get("moat_strength_score", 0.0)), 4)

    alerts: list[str] = []
    if str(latest.get("gate_status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("latest_joint_moat_strength_not_pass")
    if _to_float(latest.get("moat_strength_score", 0.0)) < 78.0:
        alerts.append("latest_moat_strength_score_below_78")
    if total_records >= 2 and delta_score < 0:
        alerts.append("moat_strength_score_decreasing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": now,
        "status": status,
        "ledger_path": str(ledger_path),
        "total_records": total_records,
        "latest_moat_strength_score": latest.get("moat_strength_score"),
        "latest_moat_strength_grade": latest.get("moat_strength_grade"),
        "avg_moat_strength_score": avg_score,
        "delta_moat_strength_score": delta_score,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_records": total_records,
                "latest_moat_strength_score": payload.get("latest_moat_strength_score"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
