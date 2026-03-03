from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _slug(v: object, *, default: str = "unknown") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return "".join(ch if ch.isalnum() else "_" for ch in t).strip("_") or default


def _extract_records(payload: dict) -> list[dict]:
    rows = payload.get("mutation_records") if isinstance(payload.get("mutation_records"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_manifest_map(payload: dict) -> dict[str, dict]:
    rows = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        if mutation_id:
            out[mutation_id] = row
    return out


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _counter_to_rows(counter: Counter[tuple[str, str]]) -> list[dict]:
    rows: list[dict] = []
    for (expected, observed), count in sorted(counter.items(), key=lambda x: (x[0][0], x[0][1])):
        rows.append({"expected": expected, "observed": observed, "count": int(count)})
    return rows


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    overall = payload.get("overall") if isinstance(payload.get("overall"), dict) else {}
    by_scale = payload.get("by_scale") if isinstance(payload.get("by_scale"), dict) else {}
    medium = by_scale.get("medium") if isinstance(by_scale.get("medium"), dict) else {}
    large = by_scale.get("large") if isinstance(by_scale.get("large"), dict) else {}
    lines = [
        "# GateForge Mutation Validation Matrix v2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- validated_mutants: `{overall.get('validated_count')}`",
        f"- overall_stage_match_rate_pct: `{overall.get('stage_match_rate_pct')}`",
        f"- overall_type_match_rate_pct: `{overall.get('type_match_rate_pct')}`",
        f"- medium_type_match_rate_pct: `{medium.get('type_match_rate_pct')}`",
        f"- large_type_match_rate_pct: `{large.get('type_match_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stratified mutation validation confusion matrix")
    parser.add_argument("--validation-records", required=True)
    parser.add_argument("--mutation-manifest", default=None)
    parser.add_argument("--min-medium-stage-match-rate-pct", type=float, default=55.0)
    parser.add_argument("--min-medium-type-match-rate-pct", type=float, default=35.0)
    parser.add_argument("--min-large-stage-match-rate-pct", type=float, default=55.0)
    parser.add_argument("--min-large-type-match-rate-pct", type=float, default=35.0)
    parser.add_argument("--matrix-out", default="artifacts/dataset_mutation_validation_matrix_v2/matrix.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_validation_matrix_v2/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    records_payload = _load_json(args.validation_records)
    manifest_payload = _load_json(args.mutation_manifest)
    records = _extract_records(records_payload)
    manifest_map = _extract_manifest_map(manifest_payload) if manifest_payload else {}

    reasons: list[str] = []
    if not records_payload:
        reasons.append("validation_records_missing")
    if not records:
        reasons.append("validation_records_empty")

    type_confusion: dict[str, Counter[tuple[str, str]]] = {
        "overall": Counter(),
        "medium": Counter(),
        "large": Counter(),
        "other": Counter(),
    }
    stage_confusion: dict[str, Counter[tuple[str, str]]] = {
        "overall": Counter(),
        "medium": Counter(),
        "large": Counter(),
        "other": Counter(),
    }

    stats: dict[str, dict[str, int]] = {
        "overall": {"validated": 0, "stage_match": 0, "type_match": 0},
        "medium": {"validated": 0, "stage_match": 0, "type_match": 0},
        "large": {"validated": 0, "stage_match": 0, "type_match": 0},
        "other": {"validated": 0, "stage_match": 0, "type_match": 0},
    }

    for row in records:
        mutation_id = str(row.get("mutation_id") or "").strip()
        manifest_row = manifest_map.get(mutation_id, {})
        scale = _slug(manifest_row.get("target_scale") or row.get("target_scale"), default="other")
        if scale not in {"medium", "large"}:
            scale = "other"

        expected_type = _slug(row.get("expected_failure_type"), default="unknown")
        observed_type = _slug(row.get("observed_failure_type"), default="unknown")
        expected_stage = _slug(row.get("expected_stage"), default="unknown")
        observed_stage = _slug(row.get("observed_stage"), default="unknown")
        stage_match = bool(row.get("stage_match"))
        type_match = bool(row.get("type_match"))

        type_confusion["overall"][(expected_type, observed_type)] += 1
        type_confusion[scale][(expected_type, observed_type)] += 1
        stage_confusion["overall"][(expected_stage, observed_stage)] += 1
        stage_confusion[scale][(expected_stage, observed_stage)] += 1

        for key in ("overall", scale):
            stats[key]["validated"] += 1
            stats[key]["stage_match"] += 1 if stage_match else 0
            stats[key]["type_match"] += 1 if type_match else 0

    def _metric_row(k: str) -> dict:
        row = stats.get(k, {})
        validated = int(row.get("validated", 0))
        return {
            "validated_count": validated,
            "stage_match_count": int(row.get("stage_match", 0)),
            "type_match_count": int(row.get("type_match", 0)),
            "stage_match_rate_pct": _ratio(int(row.get("stage_match", 0)), validated),
            "type_match_rate_pct": _ratio(int(row.get("type_match", 0)), validated),
        }

    overall_metrics = _metric_row("overall")
    medium_metrics = _metric_row("medium")
    large_metrics = _metric_row("large")
    other_metrics = _metric_row("other")

    alerts: list[str] = []
    if int(medium_metrics.get("validated_count", 0)) == 0:
        alerts.append("medium_validated_empty")
    if int(large_metrics.get("validated_count", 0)) == 0:
        alerts.append("large_validated_empty")
    if float(medium_metrics.get("stage_match_rate_pct", 0.0)) < float(args.min_medium_stage_match_rate_pct):
        alerts.append("medium_stage_match_rate_below_target")
    if float(medium_metrics.get("type_match_rate_pct", 0.0)) < float(args.min_medium_type_match_rate_pct):
        alerts.append("medium_type_match_rate_below_target")
    if float(large_metrics.get("stage_match_rate_pct", 0.0)) < float(args.min_large_stage_match_rate_pct):
        alerts.append("large_stage_match_rate_below_target")
    if float(large_metrics.get("type_match_rate_pct", 0.0)) < float(args.min_large_type_match_rate_pct):
        alerts.append("large_type_match_rate_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    matrix_payload = {
        "schema_version": "mutation_validation_matrix_v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "type_confusion": {k: _counter_to_rows(v) for k, v in type_confusion.items()},
        "stage_confusion": {k: _counter_to_rows(v) for k, v in stage_confusion.items()},
    }
    _write_json(args.matrix_out, matrix_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "overall": overall_metrics,
        "by_scale": {
            "medium": medium_metrics,
            "large": large_metrics,
            "other": other_metrics,
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "matrix_path": args.matrix_out,
        "sources": {
            "validation_records": args.validation_records,
            "mutation_manifest": args.mutation_manifest,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": status,
                "validated_mutants": overall_metrics.get("validated_count"),
                "overall_type_match_rate_pct": overall_metrics.get("type_match_rate_pct"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
