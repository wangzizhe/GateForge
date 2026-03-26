from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_cross_domain_validation_v1"
SPEC_SCHEMA_VERSION = "agent_modelica_cross_domain_validation_spec_v1"
DEFAULT_CONFIG_ORDER = (
    "baseline",
    "replay_only",
    "planner_only",
    "replay_plus_planner",
)


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


def _sorted_int_map(values: dict[str, int]) -> dict[str, int]:
    return dict(sorted({str(k): int(v) for k, v in values.items()}.items()))


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except Exception:
        return default


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
        if "503" in error or "high demand" in error or "gemini_http_error: 503" in error:
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
    return _sorted_int_map(counts)


def _aggregate_case_diagnostics(gf_results: dict) -> dict:
    rows = gf_results.get("results")
    if not isinstance(rows, list):
        rows = []

    replay_used_count = 0
    replay_coverage: dict[str, int] = {}
    replay_priority_reason: dict[str, int] = {}
    planner_used_count = 0
    planner_prompt_tokens: list[float] = []
    planner_injection_reasons: dict[str, int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        replay = row.get("experience_replay")
        if isinstance(replay, dict):
            if bool(replay.get("used")):
                replay_used_count += 1
            coverage = str(replay.get("signal_coverage_status") or "").strip()
            if coverage:
                replay_coverage[coverage] = int(replay_coverage.get(coverage, 0)) + 1
            reason = str(replay.get("priority_reason") or "").strip()
            if reason:
                replay_priority_reason[reason] = int(replay_priority_reason.get(reason, 0)) + 1

        planner = row.get("planner_experience_injection")
        if isinstance(planner, dict):
            if bool(planner.get("used")):
                planner_used_count += 1
            token_estimate = planner.get("prompt_token_estimate")
            if isinstance(token_estimate, (int, float)):
                planner_prompt_tokens.append(float(token_estimate))
            injection_reason = str(planner.get("injection_reason") or "").strip()
            if injection_reason:
                planner_injection_reasons[injection_reason] = int(
                    planner_injection_reasons.get(injection_reason, 0)
                ) + 1

    total_cases = len(rows)
    avg_tokens = round(sum(planner_prompt_tokens) / len(planner_prompt_tokens), 2) if planner_prompt_tokens else 0.0
    return {
        "result_count": total_cases,
        "replay_used_count": replay_used_count,
        "replay_used_rate_pct": round((replay_used_count / total_cases) * 100.0, 2) if total_cases else 0.0,
        "replay_signal_coverage_counts": _sorted_int_map(replay_coverage),
        "replay_priority_reason_counts": _sorted_int_map(replay_priority_reason),
        "planner_used_count": planner_used_count,
        "planner_used_rate_pct": round((planner_used_count / total_cases) * 100.0, 2) if total_cases else 0.0,
        "planner_prompt_token_estimate_avg": avg_tokens,
        "planner_injection_reason_counts": _sorted_int_map(planner_injection_reasons),
    }


def summarize_track_config(
    *,
    track_id: str,
    library: str,
    config_label: str,
    comparison_summary: dict,
    gateforge_results: dict,
) -> dict:
    bare_metrics = comparison_summary.get("bare_llm_metrics") if isinstance(comparison_summary.get("bare_llm_metrics"), dict) else {}
    gf_metrics = comparison_summary.get("gateforge_metrics") if isinstance(comparison_summary.get("gateforge_metrics"), dict) else {}
    if not gf_metrics and isinstance(gateforge_results.get("metrics"), dict):
        gf_metrics = gateforge_results.get("metrics") or {}

    bare_rate = _to_float(bare_metrics.get("repair_rate"), 0.0)
    gf_rate = _to_float(gf_metrics.get("repair_rate"), 0.0)
    total_cases = max(
        _to_int(gf_metrics.get("total"), 0),
        _to_int(bare_metrics.get("total"), 0),
    )
    verdict = str(comparison_summary.get("verdict") or "UNKNOWN")
    status = str(comparison_summary.get("status") or "UNKNOWN")
    diagnostics = _aggregate_case_diagnostics(gateforge_results)
    return {
        "track_id": str(track_id or "").strip(),
        "library": str(library or "").strip(),
        "config_label": str(config_label or "").strip(),
        "status": status,
        "verdict": verdict,
        "total_cases": total_cases,
        "gateforge_repair_rate": gf_rate,
        "bare_llm_repair_rate": bare_rate,
        "delta_pp": round((gf_rate - bare_rate) * 100.0, 2),
        "provider_noise_counts": _provider_noise_counts(comparison_summary),
        "gateforge_diagnostics": diagnostics,
        "sources": {
            "comparison_summary": str(comparison_summary.get("_source_path") or ""),
            "gateforge_results": str(gateforge_results.get("_source_path") or ""),
        },
    }


def _config_sort_key(label: str) -> tuple[int, str]:
    norm = str(label or "").strip()
    try:
        return (DEFAULT_CONFIG_ORDER.index(norm), norm)
    except ValueError:
        return (len(DEFAULT_CONFIG_ORDER), norm)


def build_validation_summary(spec: dict) -> dict:
    tracks = spec.get("tracks") if isinstance(spec.get("tracks"), list) else []
    track_summaries: list[dict] = []

    for track in tracks:
        if not isinstance(track, dict):
            continue
        track_id = str(track.get("track_id") or "").strip() or "unknown_track"
        library = str(track.get("library") or track_id).strip()
        configs = track.get("configs") if isinstance(track.get("configs"), dict) else {}
        for config_label, config in sorted(configs.items(), key=lambda item: _config_sort_key(item[0])):
            if not isinstance(config, dict):
                continue
            comparison_path = str(config.get("comparison_summary") or "").strip()
            gateforge_path = str(config.get("gateforge_results") or "").strip()
            comparison_summary = _load_json(comparison_path)
            gateforge_results = _load_json(gateforge_path)
            comparison_summary["_source_path"] = comparison_path
            gateforge_results["_source_path"] = gateforge_path
            track_summaries.append(
                summarize_track_config(
                    track_id=track_id,
                    library=library,
                    config_label=str(config_label),
                    comparison_summary=comparison_summary,
                    gateforge_results=gateforge_results,
                )
            )

    baseline_by_track = {
        str(row.get("track_id")): row
        for row in track_summaries
        if str(row.get("config_label") or "") == "baseline"
    }

    aggregate_by_config: dict[str, dict] = {}
    for row in track_summaries:
        label = str(row.get("config_label") or "unknown")
        bucket = aggregate_by_config.setdefault(
            label,
            {
                "config_label": label,
                "track_count": 0,
                "total_cases": 0,
                "gateforge_success_weighted": 0.0,
                "bare_success_weighted": 0.0,
                "advantage_track_count": 0,
                "provider_noise_counts": {},
                "replay_signal_coverage_counts": {},
                "planner_injection_reason_counts": {},
                "no_regression_vs_baseline": True,
                "track_rows": [],
            },
        )
        total_cases = _to_int(row.get("total_cases"), 0)
        bucket["track_count"] += 1
        bucket["total_cases"] += total_cases
        bucket["gateforge_success_weighted"] += _to_float(row.get("gateforge_repair_rate"), 0.0) * total_cases
        bucket["bare_success_weighted"] += _to_float(row.get("bare_llm_repair_rate"), 0.0) * total_cases
        if str(row.get("verdict") or "") == "GATEFORGE_ADVANTAGE":
            bucket["advantage_track_count"] += 1
        for key, value in (row.get("provider_noise_counts") or {}).items():
            bucket["provider_noise_counts"][str(key)] = int(bucket["provider_noise_counts"].get(str(key), 0)) + _to_int(value)
        diag = row.get("gateforge_diagnostics") if isinstance(row.get("gateforge_diagnostics"), dict) else {}
        for key, value in (diag.get("replay_signal_coverage_counts") or {}).items():
            bucket["replay_signal_coverage_counts"][str(key)] = int(bucket["replay_signal_coverage_counts"].get(str(key), 0)) + _to_int(value)
        for key, value in (diag.get("planner_injection_reason_counts") or {}).items():
            bucket["planner_injection_reason_counts"][str(key)] = int(bucket["planner_injection_reason_counts"].get(str(key), 0)) + _to_int(value)

        baseline = baseline_by_track.get(str(row.get("track_id") or ""))
        if baseline and label != "baseline":
            if _to_float(row.get("gateforge_repair_rate"), 0.0) < _to_float(baseline.get("gateforge_repair_rate"), 0.0):
                bucket["no_regression_vs_baseline"] = False
        bucket["track_rows"].append(row)

    ordered_aggregate: list[dict] = []
    for label, bucket in sorted(aggregate_by_config.items(), key=lambda item: _config_sort_key(item[0])):
        total_cases = max(1, int(bucket["total_cases"]))
        gf_rate = round(bucket["gateforge_success_weighted"] / total_cases, 4)
        bare_rate = round(bucket["bare_success_weighted"] / total_cases, 4)
        ordered_aggregate.append(
            {
                "config_label": label,
                "track_count": int(bucket["track_count"]),
                "total_cases": int(bucket["total_cases"]),
                "gateforge_repair_rate": gf_rate,
                "bare_llm_repair_rate": bare_rate,
                "delta_pp": round((gf_rate - bare_rate) * 100.0, 2),
                "advantage_track_count": int(bucket["advantage_track_count"]),
                "all_tracks_advantage": int(bucket["advantage_track_count"]) == int(bucket["track_count"]),
                "no_regression_vs_baseline": bool(bucket["no_regression_vs_baseline"]),
                "provider_noise_counts": _sorted_int_map(bucket["provider_noise_counts"]),
                "replay_signal_coverage_counts": _sorted_int_map(bucket["replay_signal_coverage_counts"]),
                "planner_injection_reason_counts": _sorted_int_map(bucket["planner_injection_reason_counts"]),
            }
        )

    status = "PASS"
    reasons: list[str] = []
    if not track_summaries:
        status = "FAIL"
        reasons.append("no_track_summaries")
    elif not any(str(row.get("config_label") or "") == "baseline" for row in track_summaries):
        status = "NEEDS_REVIEW"
        reasons.append("baseline_missing")
    elif any(not bool(row.get("no_regression_vs_baseline")) for row in ordered_aggregate if str(row.get("config_label") or "") != "baseline"):
        status = "NEEDS_REVIEW"
        reasons.append("config_regression_detected")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reasons": reasons,
        "track_summaries": track_summaries,
        "aggregate_by_config": ordered_aggregate,
        "sources": {
            "spec_path": str(spec.get("_source_path") or ""),
        },
    }


def render_markdown(summary: dict) -> str:
    lines = [
        f"# {SCHEMA_VERSION}",
        "",
        f"- status: `{summary.get('status')}`",
    ]
    reasons = summary.get("reasons") if isinstance(summary.get("reasons"), list) else []
    if reasons:
        lines.append(f"- reasons: `{', '.join(str(x) for x in reasons)}`")
    lines.extend(
        [
            "",
            "## Aggregate by Config",
            "",
            "| config | tracks | total_cases | gf_rate | bare_rate | delta_pp | advantage_tracks | no_regression_vs_baseline |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in summary.get("aggregate_by_config") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {config_label} | {track_count} | {total_cases} | {gateforge_repair_rate:.1%} | "
            "{bare_llm_repair_rate:.1%} | {delta_pp:.2f} | {advantage_track_count} | {no_regression_vs_baseline} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Per-Track Rows",
            "",
            "| track | library | config | status | verdict | gf_rate | bare_rate | delta_pp |",
            "|---|---|---|---|---|---:|---:|---:|",
        ]
    )
    for row in summary.get("track_summaries") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {track_id} | {library} | {config_label} | {status} | {verdict} | {gateforge_repair_rate:.1%} | "
            "{bare_llm_repair_rate:.1%} | {delta_pp:.2f} |".format(**row)
        )
    lines.append("")
    return "\n".join(lines)


def run_validation(*, spec_path: str, out: str) -> dict:
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

    summary = build_validation_summary(spec)
    _write_json(out, summary)
    Path(_default_md_path(out)).write_text(render_markdown(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "track_rows": len(summary.get("track_summaries") or []),
                "configs": [str(x.get("config_label") or "") for x in (summary.get("aggregate_by_config") or []) if isinstance(x, dict)],
            }
        )
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate cross-domain validation results across tracks and configs")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", default="artifacts/cross_domain_validation_v1/summary.json")
    args = parser.parse_args()

    run_validation(spec_path=args.spec, out=args.out)


if __name__ == "__main__":
    main()
