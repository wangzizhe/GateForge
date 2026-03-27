from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_LICENSES = {"mit", "bsd-3-clause", "bsd-2-clause", "apache-2.0", "mpl-2.0", "cc0-1.0"}


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


def _looks_like_partial_model(candidate: dict) -> bool:
    candidate_paths = [
        str(candidate.get("local_path") or "").strip(),
        str(candidate.get("source_library_model_path") or "").strip(),
    ]
    for raw_path in candidate_paths:
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:12]:
                stripped = line.strip().lower()
                if not stripped or stripped.startswith("//"):
                    continue
                if stripped.startswith("partial model "):
                    return True
        except Exception:
            continue
    return False


def _decision(candidate: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []

    license_tag = str(candidate.get("license") or candidate.get("license_tag") or "").strip().lower()
    if license_tag not in ALLOWED_LICENSES:
        reasons.append("license_not_allowed")

    scale_hint = _slug(candidate.get("scale_hint"), default="")
    if scale_hint not in {"small", "medium", "large"}:
        reasons.append("scale_hint_missing_or_invalid")

    repro_command = str(candidate.get("repro_command") or "").strip()
    if not repro_command:
        reasons.append("repro_command_missing")

    source = str(candidate.get("source_url") or candidate.get("source") or "").strip()
    if not source:
        reasons.append("source_missing")

    if _looks_like_partial_model(candidate):
        reasons.append("partial_model_not_runnable")

    if reasons:
        return "REJECT", reasons
    return "ACCEPT", reasons


def _to_registry_row(candidate: dict, source_name: str, om_version: str) -> dict:
    model_id = str(candidate.get("model_id") or "").strip()
    if not model_id:
        base = str(candidate.get("name") or candidate.get("source_url") or "model")
        model_id = f"intake_{_slug(base)}_{_sha256_text(base)[:8]}"

    source_path = str(candidate.get("local_path") or candidate.get("source_url") or "")
    checksum = str(candidate.get("checksum_sha256") or _sha256_text(source_path))

    return {
        "model_id": model_id,
        "asset_type": "model_source",
        "source_path": source_path,
        "source_name": source_name,
        "source_repo": str(candidate.get("source_repo") or ""),
        "source_rel_path": str(candidate.get("source_rel_path") or ""),
        "license_tag": str(candidate.get("license") or candidate.get("license_tag") or "UNKNOWN"),
        "checksum_sha256": checksum,
        "suggested_scale": _slug(candidate.get("scale_hint"), default="small"),
        "source_library_path": str(candidate.get("source_library_path") or ""),
        "source_package_name": str(candidate.get("source_package_name") or ""),
        "source_library_model_path": str(candidate.get("source_library_model_path") or ""),
        "source_qualified_model_name": str(candidate.get("source_qualified_model_name") or ""),
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
            "intake_notes": str(candidate.get("notes") or ""),
        },
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Open-Source Model Intake v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_candidates: `{payload.get('total_candidates')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- rejected_count: `{payload.get('rejected_count')}`",
        "",
        "## Rejection Reasons",
        "",
    ]
    reasons = payload.get("rejection_reason_counts") if isinstance(payload.get("rejection_reason_counts"), dict) else {}
    if reasons:
        for k, v in sorted(reasons.items()):
            lines.append(f"- `{k}`: `{v}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Intake open-source Modelica candidates into a governed allowlist")
    parser.add_argument("--candidate-catalog", required=True)
    parser.add_argument("--source-name", default="open_source_intake_v1")
    parser.add_argument("--om-version", default="openmodelica-1.25.5")
    parser.add_argument("--registry-out", default="artifacts/dataset_open_source_model_intake_v1/accepted_registry_rows.json")
    parser.add_argument("--out", default="artifacts/dataset_open_source_model_intake_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    raw = _load_json(args.candidate_catalog)
    candidates = _extract_candidates(raw)

    reasons: list[str] = []
    if not candidates:
        reasons.append("candidate_catalog_empty")

    accepted_rows: list[dict] = []
    decisions: list[dict] = []
    rejection_reason_counts: dict[str, int] = {}

    for candidate in candidates:
        decision, d_reasons = _decision(candidate)
        row = {
            "model_id": str(candidate.get("model_id") or ""),
            "name": str(candidate.get("name") or ""),
            "decision": decision,
            "reasons": d_reasons,
        }
        decisions.append(row)

        if decision == "ACCEPT":
            accepted_rows.append(_to_registry_row(candidate, str(args.source_name), str(args.om_version)))
        else:
            for r in d_reasons:
                rejection_reason_counts[r] = rejection_reason_counts.get(r, 0) + 1

    status = "PASS"
    if "candidate_catalog_empty" in reasons:
        status = "FAIL"
    elif not accepted_rows:
        status = "NEEDS_REVIEW"
        reasons.append("no_accepted_models")

    _write_json(args.registry_out, {"schema_version": "open_source_intake_registry_rows_v1", "models": accepted_rows})

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_candidates": len(candidates),
        "accepted_count": len(accepted_rows),
        "rejected_count": len(candidates) - len(accepted_rows),
        "rejection_reason_counts": rejection_reason_counts,
        "accepted_registry_rows_path": args.registry_out,
        "decisions": decisions,
        "reasons": sorted(set(reasons)),
        "sources": {"candidate_catalog": args.candidate_catalog},
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "accepted_count": len(accepted_rows), "total_candidates": len(candidates)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
