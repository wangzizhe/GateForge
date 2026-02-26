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


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _extract_cases(db: dict) -> list[dict]:
    rows = db.get("cases") if isinstance(db.get("cases"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _pick(cases: list[dict], scale: str, limit: int) -> list[dict]:
    filtered = [c for c in cases if str(c.get("model_scale") or "") == scale]
    filtered.sort(key=lambda x: str(x.get("case_id") or ""))
    return filtered[: max(0, limit)]


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Baseline Pack v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- baseline_id: `{payload.get('baseline_id')}`",
        f"- total_selected_cases: `{payload.get('total_selected_cases')}`",
        f"- small_selected: `{payload.get('scale_counts', {}).get('small', 0)}`",
        f"- medium_selected: `{payload.get('scale_counts', {}).get('medium', 0)}`",
        f"- large_selected: `{payload.get('scale_counts', {}).get('large', 0)}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fixed reproducible failure baseline pack from failure corpus DB v1")
    parser.add_argument("--failure-corpus-db", required=True)
    parser.add_argument("--small-quota", type=int, default=5)
    parser.add_argument("--medium-quota", type=int, default=4)
    parser.add_argument("--large-quota", type=int, default=3)
    parser.add_argument("--baseline-id", default="failure_baseline_v1")
    parser.add_argument("--pack-out", default="artifacts/dataset_failure_baseline_pack_v1/pack.json")
    parser.add_argument("--out", default="artifacts/dataset_failure_baseline_pack_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    db = _load_json(args.failure_corpus_db)
    cases = _extract_cases(db)

    reasons: list[str] = []
    if not db:
        reasons.append("failure_corpus_db_missing")
    if str(db.get("schema_version") or "") != "failure_corpus_db_v1":
        reasons.append("unexpected_schema_version")

    selected_small = _pick(cases, "small", int(args.small_quota))
    selected_medium = _pick(cases, "medium", int(args.medium_quota))
    selected_large = _pick(cases, "large", int(args.large_quota))

    selected = selected_small + selected_medium + selected_large
    selected_case_ids = [str(x.get("case_id") or "") for x in selected]

    scale_counts = {
        "small": len(selected_small),
        "medium": len(selected_medium),
        "large": len(selected_large),
    }

    if scale_counts["medium"] < min(2, int(args.medium_quota)):
        reasons.append("medium_quota_underfilled")
    if scale_counts["large"] < min(2, int(args.large_quota)):
        reasons.append("large_quota_underfilled")

    status = "PASS"
    if reasons:
        status = "NEEDS_REVIEW"
    if "failure_corpus_db_missing" in reasons:
        status = "FAIL"

    pack_payload = {
        "baseline_id": args.baseline_id,
        "schema_version": "failure_baseline_pack_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_case_ids": selected_case_ids,
        "selected_cases": selected,
        "scale_counts": scale_counts,
        "total_selected_cases": len(selected),
    }
    _write_json(args.pack_out, pack_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "baseline_id": args.baseline_id,
        "pack_path": args.pack_out,
        "total_selected_cases": len(selected),
        "scale_counts": scale_counts,
        "reasons": sorted(set(reasons)),
        "sources": {"failure_corpus_db": args.failure_corpus_db},
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "total_selected_cases": len(selected), "baseline_id": args.baseline_id}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
