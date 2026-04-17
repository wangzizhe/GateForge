from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUMMARY = REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1_minimax_20260417_rerun" / "summary.json"
DEFAULT_RAW_DIR = REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1_minimax_20260417_rerun" / "raw"
DEFAULT_OUT = REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1_minimax_20260417_rerun" / "failure_profile_v0_19_23.json"


def classify_error_message(error_message: str) -> str:
    text = str(error_message or "").strip().lower()
    if not text:
        return "no_error_message"
    if "529" in text or "overloaded_error" in text:
        return "provider_overloaded_529"
    if "timeout" in text:
        return "provider_timeout"
    if "rate_limited" in text or "429" in text:
        return "provider_rate_limited"
    if "missing_patched_model_text" in text:
        return "provider_response_shape_miss"
    return "other_failure"


def build_failure_profile(summary_path: Path, raw_dir: Path) -> dict:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summaries = list(summary.get("summaries") or [])

    failed = [row for row in summaries if str(row.get("executor_status") or "").upper() != "PASS"]
    failure_class_counts: Counter[str] = Counter()
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    failed_case_rows: list[dict] = []

    for row in failed:
        candidate_id = str(row.get("candidate_id") or "")
        raw_path = raw_dir / f"{candidate_id}.json"
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
        error_message = str(raw_payload.get("error_message") or "")
        failure_class = classify_error_message(error_message)
        family = str(row.get("benchmark_family") or "unknown")

        failure_class_counts[failure_class] += 1
        by_family[family][failure_class] += 1

        failed_case_rows.append(
            {
                "candidate_id": candidate_id,
                "benchmark_family": family,
                "n_turns": int(row.get("n_turns") or 0),
                "observed_error_sequence": list(row.get("observed_error_sequence") or []),
                "failure_class": failure_class,
                "error_message": error_message,
            }
        )

    infra_failure_total = sum(
        failure_class_counts.get(key, 0)
        for key in ("provider_timeout", "provider_overloaded_529", "provider_rate_limited")
    )
    capability_failure_total = sum(
        failure_class_counts.get(key, 0)
        for key in ("other_failure", "provider_response_shape_miss")
    )

    targeted_families = {
        family: {
            "total_failed": sum(counter.values()),
            "failure_classes": dict(counter),
        }
        for family, counter in sorted(by_family.items())
        if family in {"underdetermined_missing_ground", "compound_four_layer"}
    }

    return {
        "schema_version": "gateforge_minimax_failure_profile_v0_19_23",
        "summary_source": str(summary_path),
        "raw_dir": str(raw_dir),
        "aggregate_pass_rate": float(summary.get("aggregate", {}).get("pass_rate") or 0.0),
        "failed_case_count": len(failed_case_rows),
        "failure_class_counts": dict(failure_class_counts),
        "infra_failure_total": infra_failure_total,
        "capability_failure_total": capability_failure_total,
        "infra_failure_share_of_failed": round(infra_failure_total / len(failed_case_rows), 3) if failed_case_rows else 0.0,
        "targeted_family_failure_profile": targeted_families,
        "failed_cases": failed_case_rows,
        "headline_conclusion": (
            "Current MiniMax benchmark failures are dominated by provider timeout / overload events rather than confirmed repair-capability misses."
            if infra_failure_total and infra_failure_total == len(failed_case_rows)
            else "MiniMax failure profile mixes provider-side failures with possible capability misses."
        ),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    report = build_failure_profile(Path(args.summary), Path(args.raw_dir))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("MiniMax failure profile")
    print(f"  failed_case_count: {report['failed_case_count']}")
    print(f"  failure_class_counts: {report['failure_class_counts']}")
    print(f"  infra_failure_share_of_failed: {report['infra_failure_share_of_failed']}")
    print(f"  headline_conclusion: {report['headline_conclusion']}")
    print(f"  wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
