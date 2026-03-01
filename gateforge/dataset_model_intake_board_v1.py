from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict | list:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _slug(v: object, *, default: str = "") -> str:
    s = str(v or "").strip().lower()
    if not s:
        return default
    return s.replace("-", "_").replace(" ", "_")


def _extract_candidates(raw: dict | list) -> list[dict]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        rows = raw.get("candidates")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Model Intake Board v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- board_score: `{payload.get('board_score')}`",
        f"- total_candidates: `{payload.get('total_candidates')}`",
        f"- ready_count: `{payload.get('ready_count')}`",
        f"- blocked_count: `{payload.get('blocked_count')}`",
        f"- ingested_count: `{payload.get('ingested_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build model intake board with NEW/SCREENED/BLOCKED/READY/INGESTED status")
    parser.add_argument("--candidate-catalog", required=True)
    parser.add_argument("--intake-summary", required=True)
    parser.add_argument("--intake-ledger", default=None)
    parser.add_argument("--allow-licenses", default="mit,apache-2.0,bsd-3-clause,bsd-2-clause,mpl-2.0,cc0-1.0")
    parser.add_argument("--min-medium-complexity-score", type=int, default=80)
    parser.add_argument("--min-large-complexity-score", type=int, default=140)
    parser.add_argument("--out", default="artifacts/dataset_model_intake_board_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    raw = _load_json(args.candidate_catalog)
    intake = _load_json(args.intake_summary)
    ledger = _load_json(args.intake_ledger)
    candidates = _extract_candidates(raw)

    reasons: list[str] = []
    if not candidates:
        reasons.append("candidate_catalog_empty")
    if not intake:
        reasons.append("intake_summary_missing")

    allowed = {_slug(x) for x in str(args.allow_licenses).split(",") if _slug(x)}
    ledger_rows = (ledger.get("records") if isinstance(ledger, dict) else []) if ledger else []
    ledger_by_model: dict[str, dict] = {}
    if isinstance(ledger_rows, list):
        for row in ledger_rows:
            if isinstance(row, dict):
                mid = str(row.get("model_id") or "").strip()
                if mid:
                    ledger_by_model[mid] = row

    board_rows: list[dict] = []
    counts = {"NEW": 0, "SCREENED": 0, "BLOCKED": 0, "READY": 0, "INGESTED": 0}

    for c in candidates:
        model_id = str(c.get("model_id") or c.get("name") or "").strip() or "unknown"
        license_tag = _slug(c.get("license") or c.get("license_tag"))
        source_present = bool(str(c.get("source_url") or c.get("local_path") or "").strip())
        repro_present = bool(str(c.get("repro_command") or "").strip())
        complexity = _to_int(c.get("complexity_score", 0))
        scale = _slug(c.get("scale_hint"), default="small")

        gate_reasons: list[str] = []
        if not source_present:
            gate_reasons.append("source_missing")
        if not license_tag or license_tag not in allowed:
            gate_reasons.append("license_not_allowed")
        if not repro_present:
            gate_reasons.append("repro_command_missing")
        if scale == "medium" and complexity < int(args.min_medium_complexity_score):
            gate_reasons.append("medium_complexity_below_threshold")
        if scale == "large" and complexity < int(args.min_large_complexity_score):
            gate_reasons.append("large_complexity_below_threshold")

        status = "READY" if not gate_reasons else "BLOCKED"
        ledger_decision = str((ledger_by_model.get(model_id) or {}).get("decision") or "")
        if ledger_decision == "ACCEPT":
            status = "INGESTED"
        elif status == "READY" and ledger_decision == "REJECT":
            status = "SCREENED"
        elif status == "BLOCKED" and any(r in {"source_missing", "license_not_allowed"} for r in gate_reasons):
            status = "BLOCKED"
        elif status == "BLOCKED":
            status = "SCREENED"

        counts[status] = counts.get(status, 0) + 1
        board_rows.append(
            {
                "model_id": model_id,
                "status": status,
                "suggested_scale": scale,
                "license_tag": license_tag or "unknown",
                "complexity_score": complexity,
                "gate_reasons": sorted(set(gate_reasons)),
                "source_present": source_present,
                "repro_present": repro_present,
            }
        )

    total = len(candidates)
    ready_count = counts.get("READY", 0)
    blocked_count = counts.get("BLOCKED", 0)
    ingested_count = counts.get("INGESTED", 0)

    board_score = 45.0
    if total > 0:
        board_score += (ready_count / total) * 25.0
        board_score += (ingested_count / total) * 25.0
        board_score -= (blocked_count / total) * 20.0
    board_score = round(max(0.0, min(100.0, board_score)), 2)

    alerts: list[str] = []
    if blocked_count > 0:
        alerts.append("blocked_candidates_present")
    if ready_count == 0 and total > 0:
        alerts.append("no_ready_candidates")
    if _to_int(intake.get("accepted_count", 0)) == 0:
        alerts.append("no_ingested_models_yet")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "board_score": board_score,
        "total_candidates": total,
        "new_count": counts.get("NEW", 0),
        "screened_count": counts.get("SCREENED", 0),
        "blocked_count": blocked_count,
        "ready_count": ready_count,
        "ingested_count": ingested_count,
        "intake_status": intake.get("status"),
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "top_blockers": sorted(
            {
                r
                for row in board_rows
                for r in (row.get("gate_reasons") or [])
                if isinstance(r, str)
            }
        )[:10],
        "board_rows": board_rows,
        "sources": {
            "candidate_catalog": args.candidate_catalog,
            "intake_summary": args.intake_summary,
            "intake_ledger": args.intake_ledger,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "board_score": board_score, "ready_count": ready_count, "blocked_count": blocked_count}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
