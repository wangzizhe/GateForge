from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_benchmark_variance_summary_v1"
SPEC_SCHEMA_VERSION = "agent_modelica_benchmark_variance_spec_v1"


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _series_stats(values: list[float]) -> dict:
    series = [float(v) for v in values]
    if not series:
        return {
            "count": 0,
            "mean": 0.0,
            "stddev": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    stddev = statistics.stdev(series) if len(series) >= 2 else 0.0
    return {
        "count": len(series),
        "mean": round(statistics.mean(series), 4),
        "stddev": round(float(stddev), 4),
        "min": round(min(series), 4),
        "max": round(max(series), 4),
    }


def _provider_noise_counts(comparison_summary: dict) -> dict[str, int]:
    rows = comparison_summary.get("bare_llm_results")
    if not isinstance(rows, list):
        return {}
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        error = str(row.get("error") or "").strip().lower()
        if not error:
            continue
        if "503" in error or "high demand" in error:
            key = "provider_503"
        elif "rate_limit" in error or "rate limited" in error:
            key = "rate_limited"
        elif "timeout" in error:
            key = "timeout"
        elif "omc_validation_failed" in error:
            key = "omc_validation_failed"
        else:
            key = "other"
        counts[key] = int(counts.get(key, 0)) + 1
    return dict(sorted(counts.items()))


def summarize_group(group: dict) -> dict:
    runs = group.get("runs") if isinstance(group.get("runs"), list) else []
    bare_rates: list[float] = []
    gf_rates: list[float] = []
    provider_noise_totals: dict[str, list[float]] = {}
    rows: list[dict] = []

    for idx, run in enumerate(runs, 1):
        if not isinstance(run, dict):
            continue
        comparison_path = str(run.get("comparison_summary") or "").strip()
        gateforge_path = str(run.get("gateforge_results") or "").strip()
        comparison = _load_json(comparison_path)
        gateforge = _load_json(gateforge_path)
        bare_metrics = comparison.get("bare_llm_metrics") if isinstance(comparison.get("bare_llm_metrics"), dict) else {}
        gf_metrics = comparison.get("gateforge_metrics") if isinstance(comparison.get("gateforge_metrics"), dict) else {}
        if not gf_metrics and isinstance(gateforge.get("metrics"), dict):
            gf_metrics = gateforge.get("metrics") or {}

        bare_rate = _to_float(bare_metrics.get("repair_rate"), 0.0)
        gf_rate = _to_float(gf_metrics.get("repair_rate"), 0.0)
        bare_rates.append(bare_rate)
        gf_rates.append(gf_rate)
        provider_noise = _provider_noise_counts(comparison)
        for key, value in provider_noise.items():
            provider_noise_totals.setdefault(str(key), []).append(float(value))
        rows.append(
            {
                "run_index": idx,
                "bare_llm_repair_rate": bare_rate,
                "gateforge_repair_rate": gf_rate,
                "provider_noise_counts": provider_noise,
                "sources": {
                    "comparison_summary": comparison_path,
                    "gateforge_results": gateforge_path,
                },
            }
        )

    provider_noise_summary = {
        key: _series_stats(values) for key, values in sorted(provider_noise_totals.items())
    }
    return {
        "group_id": str(group.get("group_id") or "").strip(),
        "library": str(group.get("library") or "").strip(),
        "config_label": str(group.get("config_label") or "").strip(),
        "role": str(group.get("role") or "").strip(),
        "run_count": len(rows),
        "bare_llm_repair_rate": _series_stats(bare_rates),
        "gateforge_repair_rate": _series_stats(gf_rates),
        "delta_pp_mean": round((_series_stats(gf_rates)["mean"] - _series_stats(bare_rates)["mean"]) * 100.0, 2),
        "provider_noise": provider_noise_summary,
        "runs": rows,
    }


def build_summary(spec: dict) -> dict:
    groups = spec.get("groups") if isinstance(spec.get("groups"), list) else []
    summaries = [summarize_group(group) for group in groups if isinstance(group, dict)]
    status = "PASS" if summaries else "FAIL"
    reasons: list[str] = []
    if not summaries:
        reasons.append("no_groups")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reasons": reasons,
        "groups": summaries,
        "sources": {
            "spec_path": str(spec.get("_source_path") or ""),
        },
    }


def render_markdown(summary: dict) -> str:
    lines = [
        f"# {SCHEMA_VERSION}",
        "",
        f"- status: `{summary.get('status')}`",
        "",
        "| group | library | config | runs | gf_mean | gf_stddev | bare_mean | bare_stddev | delta_pp_mean |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary.get("groups") or []:
        if not isinstance(row, dict):
            continue
        gf = row.get("gateforge_repair_rate") if isinstance(row.get("gateforge_repair_rate"), dict) else {}
        bare = row.get("bare_llm_repair_rate") if isinstance(row.get("bare_llm_repair_rate"), dict) else {}
        lines.append(
            f"| {row.get('group_id')} | {row.get('library')} | {row.get('config_label')} | {row.get('run_count')} | "
            f"{gf.get('mean', 0.0):.1%} | {gf.get('stddev', 0.0):.2%} | "
            f"{bare.get('mean', 0.0):.1%} | {bare.get('stddev', 0.0):.2%} | "
            f"{row.get('delta_pp_mean', 0.0):.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def run_summary(*, spec_path: str, out: str) -> dict:
    spec = _load_json(spec_path)
    spec["_source_path"] = spec_path
    if not spec:
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "reasons": ["spec_missing_or_invalid"],
        }
        _write_json(out, summary)
        Path(_default_md_path(out)).write_text(render_markdown(summary), encoding="utf-8")
        return summary
    summary = build_summary(spec)
    _write_json(out, summary)
    Path(_default_md_path(out)).write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps({"status": summary.get("status"), "group_count": len(summary.get("groups") or [])}))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize repeated-run benchmark variance for provider instability analysis")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", default="artifacts/benchmark_variance_summary_v1/summary.json")
    args = parser.parse_args()
    run_summary(spec_path=args.spec, out=args.out)


if __name__ == "__main__":
    main()
