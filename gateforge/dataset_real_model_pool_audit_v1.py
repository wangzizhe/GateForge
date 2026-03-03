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


def _write_json(path: str, payload: object) -> None:
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


def _count_lines(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except OSError:
        return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Pool Audit v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_models: `{payload.get('total_models')}`",
        f"- existing_model_files: `{payload.get('existing_model_files')}`",
        f"- missing_model_files: `{payload.get('missing_model_files')}`",
        f"- nontrivial_model_ratio: `{payload.get('nontrivial_model_ratio')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit real model pool for file existence and structural non-triviality")
    parser.add_argument("--executable-registry", required=True)
    parser.add_argument("--intake-runner-accepted", default=None)
    parser.add_argument("--min-model-lines", type=int, default=30)
    parser.add_argument("--min-nontrivial-ratio", type=float, default=0.7)
    parser.add_argument("--out", default="artifacts/dataset_real_model_pool_audit_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.executable_registry)
    accepted = _load_json(args.intake_runner_accepted)
    reasons: list[str] = []
    if not registry:
        reasons.append("executable_registry_missing")

    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    model_rows = [r for r in rows if isinstance(r, dict) and str(r.get("asset_type") or "") == "model_source"]
    accepted_rows = accepted.get("rows") if isinstance(accepted.get("rows"), list) else []

    total_models = len(model_rows)
    existing_files = 0
    missing_files = 0
    nontrivial_models = 0
    large_models = 0
    total_lines = 0
    missing_examples: list[str] = []
    for row in model_rows:
        source_path = str(row.get("source_path") or "")
        p = Path(source_path)
        if p.exists() and p.is_file():
            existing_files += 1
            line_count = _count_lines(p)
            total_lines += line_count
            if line_count >= int(args.min_model_lines):
                nontrivial_models += 1
        else:
            missing_files += 1
            if len(missing_examples) < 10:
                missing_examples.append(source_path)
        if str(row.get("suggested_scale") or "").lower() == "large":
            large_models += 1

    avg_model_lines = round(total_lines / max(1, existing_files), 4)
    existing_file_ratio = round(existing_files / max(1, total_models), 4)
    nontrivial_ratio = round(nontrivial_models / max(1, existing_files), 4)
    accepted_count = len([r for r in accepted_rows if isinstance(r, dict)])

    alerts: list[str] = []
    if missing_files > 0:
        alerts.append("model_files_missing")
    if nontrivial_ratio < float(args.min_nontrivial_ratio):
        alerts.append("nontrivial_model_ratio_low")
    if accepted_count > 0 and total_models < accepted_count:
        alerts.append("registry_model_count_less_than_accepted_count")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_models": total_models,
        "accepted_count": accepted_count,
        "large_models": large_models,
        "existing_model_files": existing_files,
        "missing_model_files": missing_files,
        "existing_file_ratio": existing_file_ratio,
        "nontrivial_models": nontrivial_models,
        "nontrivial_model_ratio": nontrivial_ratio,
        "avg_model_lines": avg_model_lines,
        "missing_file_examples": missing_examples,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "executable_registry": args.executable_registry,
            "intake_runner_accepted": args.intake_runner_accepted,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_models": total_models, "existing_model_files": existing_files}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
