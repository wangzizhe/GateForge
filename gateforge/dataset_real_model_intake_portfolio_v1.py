from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


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


def _slug(v: object, *, default: str = "unknown") -> str:
    s = str(v or "").strip().lower()
    if not s:
        return default
    return s.replace("-", "_").replace(" ", "_")


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _extract_models(registry: dict) -> list[dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_domain(row: dict) -> str:
    prov = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    for key in ("source_url", "source_repo"):
        raw = str(prov.get(key) or row.get(key) or "").strip()
        if not raw:
            continue
        parsed = urlparse(raw)
        host = str(parsed.netloc or "").strip().lower()
        if host:
            return host
    return ""


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Intake Portfolio v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_real_models: `{payload.get('total_real_models')}`",
        f"- large_models: `{payload.get('large_models')}`",
        f"- license_clean_ratio_pct: `{payload.get('license_clean_ratio_pct')}`",
        f"- active_domains_count: `{payload.get('active_domains_count')}`",
        f"- portfolio_strength_score: `{payload.get('portfolio_strength_score')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build real model intake portfolio KPI summary")
    parser.add_argument("--real-model-registry", required=True)
    parser.add_argument("--allow-licenses", default="mit,apache_2.0,apache-2.0,bsd_3_clause,bsd-3-clause,bsd_2_clause,bsd-2-clause,mpl_2.0,mpl-2.0,cc0_1.0,cc0-1.0")
    parser.add_argument("--min-total-models", type=int, default=3)
    parser.add_argument("--min-large-models", type=int, default=1)
    parser.add_argument("--min-license-clean-ratio-pct", type=float, default=95.0)
    parser.add_argument("--min-active-domains", type=int, default=2)
    parser.add_argument("--out", default="artifacts/dataset_real_model_intake_portfolio_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.real_model_registry)
    models = _extract_models(registry)

    reasons: list[str] = []
    if not registry:
        reasons.append("real_model_registry_missing")

    allowed_licenses = {_slug(x, default="") for x in str(args.allow_licenses).split(",") if _slug(x, default="")}

    scale_counts = {"small": 0, "medium": 0, "large": 0, "unknown": 0}
    clean_license_count = 0
    unknown_license_count = 0
    domains: set[str] = set()

    for row in models:
        scale = _slug(row.get("suggested_scale"), default="unknown")
        if scale not in scale_counts:
            scale = "unknown"
        scale_counts[scale] += 1

        lic = _slug(row.get("license_tag"), default="unknown")
        if lic in allowed_licenses:
            clean_license_count += 1
        if lic == "unknown":
            unknown_license_count += 1

        domain = _extract_domain(row)
        if domain:
            domains.add(domain)

    total_real_models = len(models)
    large_models = int(scale_counts.get("large", 0))
    license_clean_ratio_pct = _ratio(clean_license_count, total_real_models)
    active_domains_count = len(domains)

    strength_score = 42.0
    strength_score += min(24.0, total_real_models * 4.0)
    strength_score += min(14.0, large_models * 8.0)
    strength_score += min(10.0, active_domains_count * 3.0)
    strength_score += min(10.0, license_clean_ratio_pct * 0.1)
    strength_score -= min(12.0, unknown_license_count * 5.0)
    strength_score = round(max(0.0, min(100.0, strength_score)), 2)

    alerts: list[str] = []
    if total_real_models < int(args.min_total_models):
        alerts.append("total_real_models_below_target")
    if large_models < int(args.min_large_models):
        alerts.append("large_models_below_target")
    if license_clean_ratio_pct < float(args.min_license_clean_ratio_pct):
        alerts.append("license_clean_ratio_below_target")
    if active_domains_count < int(args.min_active_domains):
        alerts.append("active_domains_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_real_models": total_real_models,
        "large_models": large_models,
        "license_clean_ratio_pct": license_clean_ratio_pct,
        "active_domains_count": active_domains_count,
        "portfolio_strength_score": strength_score,
        "scale_counts": scale_counts,
        "unique_domains": sorted(domains),
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "real_model_registry": args.real_model_registry,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_real_models": total_real_models,
                "large_models": large_models,
                "portfolio_strength_score": strength_score,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
