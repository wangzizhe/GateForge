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


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _extract_model_scale_counts_from_benchmark(benchmark: dict) -> dict[str, int]:
    dist = benchmark.get("distribution") if isinstance(benchmark.get("distribution"), dict) else {}
    counts = dist.get("model_scale_after") if isinstance(dist.get("model_scale_after"), dict) else {}
    return {
        "small": _to_int(counts.get("small", 0)),
        "medium": _to_int(counts.get("medium", 0)),
        "large": _to_int(counts.get("large", 0)),
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Model Scale Ladder",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_evidence_cases: `{payload.get('total_evidence_cases')}`",
        f"- medium_ready: `{payload.get('medium_ready')}`",
        f"- large_ready: `{payload.get('large_ready')}`",
        "",
        "## Scale Counts",
        "",
    ]
    scale_counts = payload.get("scale_counts") if isinstance(payload.get("scale_counts"), dict) else {}
    for key in ["small", "medium", "large"]:
        lines.append(f"- {key}: `{scale_counts.get(key)}`")

    lines.extend(["", "## CI Recommendation", ""])
    ci = payload.get("ci_recommendation") if isinstance(payload.get("ci_recommendation"), dict) else {}
    for key in ["main", "optional", "nightly"]:
        value = ci.get(key)
        if isinstance(value, list):
            text = ", ".join(str(x) for x in value) or "none"
        else:
            text = "none"
        lines.append(f"- {key}: `{text}`")

    lines.extend(["", "## Alerts", ""])
    alerts = payload.get("alerts")
    if isinstance(alerts, list) and alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate model scale ladder readiness and CI lane recommendation")
    parser.add_argument("--failure-taxonomy-coverage", required=True, help="Path to dataset failure taxonomy coverage summary")
    parser.add_argument(
        "--failure-distribution-benchmark",
        default=None,
        help="Path to dataset failure distribution benchmark summary",
    )
    parser.add_argument("--out", default="artifacts/dataset_model_scale_ladder/summary.json")
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--min-small-cases", type=int, default=3)
    parser.add_argument("--min-medium-cases", type=int, default=2)
    parser.add_argument("--min-large-cases", type=int, default=1)
    parser.add_argument("--min-medium-benchmark-cases", type=int, default=1)
    parser.add_argument("--min-large-benchmark-cases", type=int, default=1)
    args = parser.parse_args()

    taxonomy = _load_json(args.failure_taxonomy_coverage)
    benchmark = _load_json(args.failure_distribution_benchmark)

    taxonomy_counts_raw = taxonomy.get("model_scale_counts") if isinstance(taxonomy.get("model_scale_counts"), dict) else {}
    taxonomy_counts = {
        "small": _to_int(taxonomy_counts_raw.get("small", 0)),
        "medium": _to_int(taxonomy_counts_raw.get("medium", 0)),
        "large": _to_int(taxonomy_counts_raw.get("large", 0)),
    }
    benchmark_counts = _extract_model_scale_counts_from_benchmark(benchmark)

    scale_counts = {
        "small": max(taxonomy_counts["small"], benchmark_counts["small"]),
        "medium": max(taxonomy_counts["medium"], benchmark_counts["medium"]),
        "large": max(taxonomy_counts["large"], benchmark_counts["large"]),
    }

    small_ready = scale_counts["small"] >= int(args.min_small_cases)
    medium_ready = scale_counts["medium"] >= int(args.min_medium_cases) and benchmark_counts["medium"] >= int(
        args.min_medium_benchmark_cases
    )
    large_ready = scale_counts["large"] >= int(args.min_large_cases) and benchmark_counts["large"] >= int(
        args.min_large_benchmark_cases
    )

    alerts: list[str] = []
    if not small_ready:
        alerts.append("small_scale_coverage_insufficient")
    if not medium_ready:
        alerts.append("medium_scale_readiness_insufficient")
    if not large_ready:
        alerts.append("large_scale_readiness_insufficient")

    total_evidence_cases = scale_counts["small"] + scale_counts["medium"] + scale_counts["large"]

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    if total_evidence_cases == 0 or scale_counts["small"] == 0:
        status = "FAIL"

    ci_main = ["small_smoke"]
    if medium_ready:
        ci_main.append("medium_smoke")

    ci_optional = []
    if scale_counts["medium"] > 0:
        ci_optional.append("medium_full")
    if scale_counts["large"] > 0:
        ci_optional.append("large_subset")

    ci_nightly = ["small_full", "medium_full"]
    if large_ready:
        ci_nightly.append("large_full")
    elif scale_counts["large"] > 0:
        ci_nightly.append("large_subset")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "small_ready": small_ready,
        "medium_ready": medium_ready,
        "large_ready": large_ready,
        "total_evidence_cases": total_evidence_cases,
        "scale_counts": scale_counts,
        "taxonomy_scale_counts": taxonomy_counts,
        "benchmark_scale_counts": benchmark_counts,
        "ci_recommendation": {
            "main": ci_main,
            "optional": ci_optional,
            "nightly": ci_nightly,
        },
        "alerts": alerts,
        "sources": {
            "failure_taxonomy_coverage": args.failure_taxonomy_coverage,
            "failure_distribution_benchmark": args.failure_distribution_benchmark,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "medium_ready": medium_ready, "large_ready": large_ready}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
