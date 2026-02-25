from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    checks = payload.get("gate_checks", {})
    lines = [
        "# GateForge Dataset Freeze",
        "",
        f"- freeze_id: `{payload.get('freeze_id')}`",
        f"- generated_at_utc: `{payload.get('generated_at_utc')}`",
        f"- status: `{payload.get('status')}`",
        f"- total_cases: `{payload.get('total_cases')}`",
        f"- failure_case_rate: `{payload.get('failure_case_rate')}`",
        "",
        "## Gate Checks",
        "",
        f"- min_cases_check: `{checks.get('min_cases_check')}`",
        f"- min_failure_case_rate_check: `{checks.get('min_failure_case_rate_check')}`",
        "",
        "## Inputs",
        "",
        f"- dataset_jsonl: `{payload.get('inputs', {}).get('dataset_jsonl')}`",
        f"- distribution_json: `{payload.get('inputs', {}).get('distribution_json')}`",
        f"- quality_json: `{payload.get('inputs', {}).get('quality_json')}`",
        "",
        "## Checksums",
        "",
    ]
    checksums = payload.get("checksums", {})
    if isinstance(checksums, dict) and checksums:
        for k in sorted(checksums.keys()):
            lines.append(f"- {k}: `{checksums[k]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _count_jsonl_rows(path: str) -> int:
    total = 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            total += 1
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze dataset artifacts into a versioned manifest")
    parser.add_argument("--dataset-jsonl", required=True, help="dataset_cases.jsonl path")
    parser.add_argument("--distribution-json", required=True, help="distribution.json path")
    parser.add_argument("--quality-json", required=True, help="quality_report.json path")
    parser.add_argument("--freeze-id", default="freeze_v1", help="Freeze identifier")
    parser.add_argument("--out-dir", default="artifacts/dataset_freeze/freeze_v1", help="Freeze output directory")
    parser.add_argument(
        "--quality-gate",
        default=None,
        help="Optional dataset quality gate JSON path; freeze fails unless status=PASS",
    )
    parser.add_argument("--min-cases", type=int, default=100, help="Minimum required case count")
    parser.add_argument("--min-failure-case-rate", type=float, default=0.2, help="Minimum failure_case_rate")
    args = parser.parse_args()

    quality = _load_json(args.quality_json)
    total_cases = _count_jsonl_rows(args.dataset_jsonl)
    failure_case_rate = float(quality.get("failure_case_rate", 0.0) or 0.0)
    quality_gate = _load_json(args.quality_gate) if args.quality_gate else {}

    min_cases_ok = total_cases >= int(args.min_cases)
    min_failure_rate_ok = failure_case_rate >= float(args.min_failure_case_rate)
    quality_gate_ok = True
    if args.quality_gate:
        quality_gate_ok = str(quality_gate.get("status") or "FAIL") == "PASS"
    status = "PASS" if min_cases_ok and min_failure_rate_ok and quality_gate_ok else "FAIL"

    payload = {
        "freeze_id": args.freeze_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_cases": total_cases,
        "failure_case_rate": failure_case_rate,
        "gate_checks": {
            "min_cases_check": "PASS" if min_cases_ok else "FAIL",
            "min_failure_case_rate_check": "PASS" if min_failure_rate_ok else "FAIL",
            "quality_gate_check": "PASS" if quality_gate_ok else "FAIL",
        },
        "inputs": {
            "dataset_jsonl": args.dataset_jsonl,
            "distribution_json": args.distribution_json,
            "quality_json": args.quality_json,
            "quality_gate_json": args.quality_gate,
        },
        "checksums": {
            "dataset_jsonl_sha256": _sha256(args.dataset_jsonl),
            "distribution_json_sha256": _sha256(args.distribution_json),
            "quality_json_sha256": _sha256(args.quality_json),
        },
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(str(out_dir / "manifest.json"), payload)
    _write_json(str(out_dir / "summary.json"), payload)
    _write_markdown(str(out_dir / "summary.md"), payload)
    print(json.dumps({"freeze_id": args.freeze_id, "status": status, "total_cases": total_cases}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
