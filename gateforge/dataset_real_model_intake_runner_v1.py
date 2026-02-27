from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ALLOWED_LICENSES = {"mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause", "mpl-2.0", "cc0-1.0"}


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("_", "-").replace(" ", "-")


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_queue_jsonl(path: str) -> tuple[list[dict], int]:
    p = Path(path)
    if not p.exists():
        return [], 0
    rows: list[dict] = []
    invalid = 0
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        else:
            invalid += 1
    return rows, invalid


def _check_model_structure(path: Path) -> tuple[bool, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    lowered = text.lower()
    if "model " not in lowered and "package " not in lowered:
        return False, "model_or_package_block_missing"
    if "end " not in lowered:
        return False, "model_end_missing"
    return True, "ok"


def _validate_candidate(candidate: dict, allowed_licenses: set[str]) -> list[str]:
    reasons: list[str] = []
    if not str(candidate.get("source_url") or "").strip():
        reasons.append("source_url_missing")
    if not str(candidate.get("domain") or "").strip():
        reasons.append("domain_missing")
    if not str(candidate.get("version_hint") or "").strip():
        reasons.append("version_hint_missing")

    license_tag = _slug(candidate.get("license"), default="")
    if not license_tag:
        reasons.append("license_missing")
    elif license_tag not in allowed_licenses:
        reasons.append("license_not_allowed")

    scale = _slug(candidate.get("expected_scale"), default="")
    if scale not in {"small", "medium", "large"}:
        reasons.append("expected_scale_invalid")

    model_path_text = str(candidate.get("model_path") or "").strip()
    if not model_path_text:
        reasons.append("model_path_missing")
        return reasons

    path = Path(model_path_text)
    if path.suffix.lower() not in {".mo", ".mos"}:
        reasons.append("model_extension_not_allowed")
    if not path.exists():
        reasons.append("model_path_not_found")
        return reasons

    ok, reason = _check_model_structure(path)
    if not ok:
        reasons.append(reason)

    return sorted(set(reasons))


def _decision_record(candidate: dict, decision: str, reasons: list[str]) -> dict:
    source_url = str(candidate.get("source_url") or "")
    model_path = str(candidate.get("model_path") or "")
    candidate_id = str(candidate.get("candidate_id") or f"intake_{_sha256_text(source_url + '|' + model_path)[:10]}")
    return {
        "candidate_id": candidate_id,
        "source_url": source_url,
        "model_path": model_path,
        "license": str(candidate.get("license") or ""),
        "domain": str(candidate.get("domain") or ""),
        "expected_scale": _slug(candidate.get("expected_scale"), default="unknown"),
        "version_hint": str(candidate.get("version_hint") or ""),
        "decision": decision,
        "reasons": reasons,
    }


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Intake Runner v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_candidates: `{payload.get('total_candidates')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- accepted_large_count: `{payload.get('accepted_large_count')}`",
        f"- reject_rate_pct: `{payload.get('reject_rate_pct')}`",
        f"- weekly_target_status: `{payload.get('weekly_target_status')}`",
        "",
        "## Target Gaps",
        "",
    ]
    gaps = payload.get("target_gaps") if isinstance(payload.get("target_gaps"), list) else []
    if gaps:
        for gap in gaps:
            lines.append(f"- `{gap}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Modelica intake queue with license/structure checks and weekly growth targets")
    parser.add_argument("--intake-queue-jsonl", required=True)
    parser.add_argument("--allow-licenses", default="mit,apache-2.0,bsd-3-clause,bsd-2-clause,mpl-2.0,cc0-1.0")
    parser.add_argument("--min-weekly-accepted", type=int, default=3)
    parser.add_argument("--min-weekly-large-accepted", type=int, default=1)
    parser.add_argument("--max-weekly-reject-rate-pct", type=float, default=45.0)
    parser.add_argument("--accepted-out", default="artifacts/dataset_real_model_intake_runner_v1/accepted.json")
    parser.add_argument("--rejected-out", default="artifacts/dataset_real_model_intake_runner_v1/rejected.json")
    parser.add_argument("--out", default="artifacts/dataset_real_model_intake_runner_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    queue_rows, invalid_jsonl_line_count = _load_queue_jsonl(args.intake_queue_jsonl)

    allowed_licenses = {
        _slug(x, default="")
        for x in str(args.allow_licenses).split(",")
        if _slug(x, default="")
    } or set(DEFAULT_ALLOWED_LICENSES)

    reasons: list[str] = []
    if not queue_rows:
        reasons.append("intake_queue_empty")

    accepted: list[dict] = []
    rejected: list[dict] = []
    reject_reason_distribution: dict[str, int] = {}

    for candidate in queue_rows:
        candidate_reasons = _validate_candidate(candidate, allowed_licenses)
        if candidate_reasons:
            record = _decision_record(candidate, "REJECT", candidate_reasons)
            rejected.append(record)
            for reason in candidate_reasons:
                reject_reason_distribution[reason] = reject_reason_distribution.get(reason, 0) + 1
        else:
            accepted.append(_decision_record(candidate, "ACCEPT", []))

    accepted_count = len(accepted)
    rejected_count = len(rejected)
    total = len(queue_rows)
    reject_rate_pct = _ratio(rejected_count, total)

    accepted_scale_counts = {
        "small": len([x for x in accepted if str(x.get("expected_scale") or "") == "small"]),
        "medium": len([x for x in accepted if str(x.get("expected_scale") or "") == "medium"]),
        "large": len([x for x in accepted if str(x.get("expected_scale") or "") == "large"]),
    }
    accepted_large_count = accepted_scale_counts["large"]

    target_gaps: list[str] = []
    if accepted_count < int(args.min_weekly_accepted):
        target_gaps.append("weekly_accepted_below_target")
    if accepted_large_count < int(args.min_weekly_large_accepted):
        target_gaps.append("weekly_large_accepted_below_target")
    if reject_rate_pct > float(args.max_weekly_reject_rate_pct):
        target_gaps.append("weekly_reject_rate_above_target")
    unknown_license_reject_count = reject_reason_distribution.get("license_missing", 0)
    if unknown_license_reject_count > 0:
        target_gaps.append("unknown_license_present")

    weekly_target_status = "PASS" if not target_gaps else "NEEDS_REVIEW"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif weekly_target_status != "PASS":
        status = "NEEDS_REVIEW"

    accepted_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "real_model_intake_runner_accepted_v1",
        "rows": accepted,
    }
    rejected_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "real_model_intake_runner_rejected_v1",
        "rows": rejected,
    }
    _write_json(args.accepted_out, accepted_payload)
    _write_json(args.rejected_out, rejected_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_candidates": total,
        "accepted_count": accepted_count,
        "accepted_large_count": accepted_large_count,
        "accepted_scale_counts": accepted_scale_counts,
        "rejected_count": rejected_count,
        "reject_rate_pct": reject_rate_pct,
        "weekly_target_status": weekly_target_status,
        "weekly_target_pass": weekly_target_status == "PASS",
        "target_gaps": target_gaps,
        "reject_reason_distribution": reject_reason_distribution,
        "invalid_jsonl_line_count": _to_int(invalid_jsonl_line_count),
        "reasons": sorted(set(reasons)),
        "sources": {
            "intake_queue_jsonl": args.intake_queue_jsonl,
        },
        "artifacts": {
            "accepted_out": args.accepted_out,
            "rejected_out": args.rejected_out,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": status,
                "accepted_count": accepted_count,
                "accepted_large_count": accepted_large_count,
                "reject_rate_pct": reject_rate_pct,
                "weekly_target_status": weekly_target_status,
            }
        )
    )

    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
