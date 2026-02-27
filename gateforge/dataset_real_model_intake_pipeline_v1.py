from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ALLOWED_LICENSES = {"mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause", "mpl-2.0", "cc0-1.0"}


def _load_json(path: str | None) -> dict | list:
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
    return t.replace("-", "_").replace(" ", "_")


def _extract_candidates(raw: dict | list) -> list[dict]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        rows = raw.get("candidates")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _probe_repro_command(command: str, mode: str, timeout_seconds: int) -> dict:
    command = str(command or "").strip()
    if not command:
        return {"probe_status": "FAIL", "probe_reason": "repro_command_missing", "return_code": None}

    looks_like_valid_entry = any(token in command for token in ("omc", "python", "bash", "sh", "./"))
    if mode == "syntax":
        return {
            "probe_status": "PASS" if looks_like_valid_entry else "FAIL",
            "probe_reason": "syntax_ok" if looks_like_valid_entry else "syntax_unrecognized_command",
            "return_code": None,
        }

    try:
        proc = subprocess.run(
            ["bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
        return {
            "probe_status": "PASS" if int(proc.returncode) == 0 else "FAIL",
            "probe_reason": "execution_ok" if int(proc.returncode) == 0 else "execution_nonzero_exit",
            "return_code": int(proc.returncode),
        }
    except subprocess.TimeoutExpired:
        return {"probe_status": "FAIL", "probe_reason": "execution_timeout", "return_code": None}
    except Exception as exc:  # pragma: no cover - defensive
        return {"probe_status": "FAIL", "probe_reason": f"execution_exception:{type(exc).__name__}", "return_code": None}


def _to_registry_row(candidate: dict, source_name: str, om_version: str) -> dict:
    model_id = str(candidate.get("model_id") or "").strip()
    if not model_id:
        base = str(candidate.get("name") or candidate.get("source_url") or candidate.get("local_path") or "model")
        model_id = f"realintake_{_slug(base)}_{_sha256_text(base)[:8]}"

    source_path = str(candidate.get("local_path") or candidate.get("source_url") or "")
    checksum = str(candidate.get("checksum_sha256") or _sha256_text(source_path))

    return {
        "model_id": model_id,
        "asset_type": "model_source",
        "source_path": source_path,
        "source_name": source_name,
        "license_tag": str(candidate.get("license") or candidate.get("license_tag") or "UNKNOWN"),
        "checksum_sha256": checksum,
        "suggested_scale": _slug(candidate.get("scale_hint"), default="small"),
        "complexity": {
            "line_count": int(candidate.get("line_count") or 0),
            "equation_count": int(candidate.get("equation_count") or 0),
            "model_block_count": int(candidate.get("model_block_count") or 0),
            "algorithm_count": int(candidate.get("algorithm_count") or 0),
            "complexity_score": int(candidate.get("complexity_score") or 0),
        },
        "reproducibility": {
            "om_version": om_version,
            "repro_command": str(candidate.get("repro_command") or ""),
        },
        "provenance": {
            "source_url": str(candidate.get("source_url") or ""),
            "source_repo": str(candidate.get("source_repo") or ""),
            "source_commit": str(candidate.get("source_commit") or ""),
            "intake_notes": str(candidate.get("notes") or ""),
        },
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Intake Pipeline v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_candidates: `{payload.get('total_candidates')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- rejected_count: `{payload.get('rejected_count')}`",
        f"- probe_fail_count: `{payload.get('probe_fail_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Intake real Modelica sources into governed registry rows with provenance and reproducibility probes")
    parser.add_argument("--candidate-catalog", required=True)
    parser.add_argument("--source-name", default="real_model_intake_pipeline_v1")
    parser.add_argument("--om-version", default="openmodelica-1.25.5")
    parser.add_argument("--probe-mode", choices=["syntax", "execute"], default="syntax")
    parser.add_argument("--probe-timeout-seconds", type=int, default=6)
    parser.add_argument("--allow-licenses", default="mit,apache-2.0,bsd-3-clause,bsd-2-clause,mpl-2.0,cc0-1.0")
    parser.add_argument("--min-medium-complexity-score", type=int, default=80)
    parser.add_argument("--min-large-complexity-score", type=int, default=140)
    parser.add_argument("--registry-rows-out", default="artifacts/dataset_real_model_intake_pipeline_v1/accepted_registry_rows.json")
    parser.add_argument("--ledger-out", default="artifacts/dataset_real_model_intake_pipeline_v1/intake_ledger.json")
    parser.add_argument("--out", default="artifacts/dataset_real_model_intake_pipeline_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    raw = _load_json(args.candidate_catalog)
    candidates = _extract_candidates(raw)
    allowed_licenses = {
        _slug(x, default="")
        for x in (str(args.allow_licenses).split(",") if args.allow_licenses else sorted(DEFAULT_ALLOWED_LICENSES))
        if _slug(x, default="")
    } or set(DEFAULT_ALLOWED_LICENSES)

    reasons: list[str] = []
    if not candidates:
        reasons.append("candidate_catalog_empty")

    accepted_rows: list[dict] = []
    ledger_rows: list[dict] = []
    rejection_reason_counts: dict[str, int] = {}
    probe_fail_count = 0

    for candidate in candidates:
        candidate_reasons: list[str] = []
        scale_hint = _slug(candidate.get("scale_hint"), default="")
        license_tag = _slug(candidate.get("license") or candidate.get("license_tag"), default="")
        repro_command = str(candidate.get("repro_command") or "").strip()
        local_path = str(candidate.get("local_path") or "").strip()
        complexity_score = int(candidate.get("complexity_score") or 0)

        if scale_hint not in {"small", "medium", "large"}:
            candidate_reasons.append("scale_hint_missing_or_invalid")
        if license_tag not in allowed_licenses:
            candidate_reasons.append("license_not_allowed")
        if not str(candidate.get("source_url") or "").strip() and not local_path:
            candidate_reasons.append("source_missing")
        if local_path and not Path(local_path).exists():
            candidate_reasons.append("local_path_not_found")
        if not repro_command:
            candidate_reasons.append("repro_command_missing")

        if scale_hint == "medium" and complexity_score < int(args.min_medium_complexity_score):
            candidate_reasons.append("medium_complexity_below_threshold")
        if scale_hint == "large" and complexity_score < int(args.min_large_complexity_score):
            candidate_reasons.append("large_complexity_below_threshold")

        probe = _probe_repro_command(repro_command, mode=str(args.probe_mode), timeout_seconds=int(args.probe_timeout_seconds))
        if probe.get("probe_status") != "PASS":
            candidate_reasons.append(str(probe.get("probe_reason") or "probe_failed"))
            probe_fail_count += 1

        decision = "ACCEPT" if not candidate_reasons else "REJECT"
        if decision == "ACCEPT":
            accepted_rows.append(_to_registry_row(candidate, str(args.source_name), str(args.om_version)))
        else:
            for reason in candidate_reasons:
                rejection_reason_counts[reason] = rejection_reason_counts.get(reason, 0) + 1

        ledger_rows.append(
            {
                "model_id": str(candidate.get("model_id") or ""),
                "name": str(candidate.get("name") or ""),
                "decision": decision,
                "reasons": sorted(set(candidate_reasons)),
                "probe": probe,
            }
        )

    status = "PASS"
    if "candidate_catalog_empty" in reasons:
        status = "FAIL"
    elif not accepted_rows:
        status = "NEEDS_REVIEW"
        reasons.append("no_accepted_real_models")
    elif probe_fail_count > 0:
        status = "NEEDS_REVIEW"

    scale_counts = {
        "small": len([x for x in accepted_rows if str(x.get("suggested_scale") or "") == "small"]),
        "medium": len([x for x in accepted_rows if str(x.get("suggested_scale") or "") == "medium"]),
        "large": len([x for x in accepted_rows if str(x.get("suggested_scale") or "") == "large"]),
    }

    _write_json(
        args.registry_rows_out,
        {"schema_version": "real_model_intake_registry_rows_v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "models": accepted_rows},
    )
    _write_json(
        args.ledger_out,
        {"schema_version": "real_model_intake_ledger_v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "records": ledger_rows},
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_candidates": len(candidates),
        "accepted_count": len(accepted_rows),
        "rejected_count": len(candidates) - len(accepted_rows),
        "probe_fail_count": probe_fail_count,
        "accepted_scale_counts": scale_counts,
        "rejection_reason_counts": rejection_reason_counts,
        "registry_rows_out": args.registry_rows_out,
        "ledger_out": args.ledger_out,
        "reasons": sorted(set(reasons)),
        "sources": {"candidate_catalog": args.candidate_catalog},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "accepted_count": len(accepted_rows), "probe_fail_count": probe_fail_count}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
