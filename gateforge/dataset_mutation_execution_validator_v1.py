from __future__ import annotations

import argparse
import json
from collections import Counter
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


def _extract_mutations(manifest: dict) -> list[dict]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_obs_map(observations: dict) -> dict[str, list[str]]:
    rows = observations.get("observations") if isinstance(observations.get("observations"), list) else []
    out: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "")
        if not mutation_id:
            continue
        labels = row.get("observed_failure_types")
        if isinstance(labels, list):
            out[mutation_id] = [str(x) for x in labels if isinstance(x, str)]
            continue
        single = str(row.get("observed_failure_type") or "")
        if single:
            out[mutation_id] = [single]
    return out


def _majority(labels: list[str]) -> tuple[str, float]:
    if not labels:
        return "", 0.0
    c = Counter(labels)
    label, count = c.most_common(1)[0]
    return str(label), round(count / len(labels), 4)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Execution Validator v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- validated_count: `{payload.get('validated_count')}`",
        f"- mismatch_count: `{payload.get('mismatch_count')}`",
        f"- uncertain_count: `{payload.get('uncertain_count')}`",
        f"- expected_match_ratio_pct: `{payload.get('expected_match_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate mutation execution outcomes against expected failure types")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--replay-observations", required=True)
    parser.add_argument("--min-evidence-runs", type=int, default=3)
    parser.add_argument("--min-majority-ratio", type=float, default=0.66)
    parser.add_argument("--min-match-ratio-pct", type=float, default=70.0)
    parser.add_argument("--validated-manifest-out", default="artifacts/dataset_mutation_execution_validator_v1/validated_manifest.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_execution_validator_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    observations = _load_json(args.replay_observations)

    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not observations:
        reasons.append("replay_observations_missing")

    mutations = _extract_mutations(manifest)
    obs_map = _extract_obs_map(observations)

    min_runs = max(1, int(args.min_evidence_runs))
    min_majority = float(args.min_majority_ratio)

    validated: list[dict] = []
    details: list[dict] = []

    mismatch_count = 0
    uncertain_count = 0

    for row in mutations:
        mutation_id = str(row.get("mutation_id") or "")
        expected = str(row.get("expected_failure_type") or "")
        labels = obs_map.get(mutation_id, [])

        if len(labels) < min_runs:
            uncertain_count += 1
            details.append(
                {
                    "mutation_id": mutation_id,
                    "decision": "UNCERTAIN",
                    "expected_failure_type": expected,
                    "observed_majority_failure_type": "",
                    "observed_majority_ratio": 0.0,
                    "run_count": len(labels),
                    "reason": "insufficient_runs",
                }
            )
            continue

        observed, ratio = _majority(labels)
        if ratio < min_majority:
            uncertain_count += 1
            details.append(
                {
                    "mutation_id": mutation_id,
                    "decision": "UNCERTAIN",
                    "expected_failure_type": expected,
                    "observed_majority_failure_type": observed,
                    "observed_majority_ratio": ratio,
                    "run_count": len(labels),
                    "reason": "majority_ratio_low",
                }
            )
            continue

        if expected and observed == expected:
            decision = "VALIDATED"
            validated_row = dict(row)
            validated_row["observed_majority_failure_type"] = observed
            validated_row["observed_majority_ratio"] = ratio
            validated_row["run_count"] = len(labels)
            validated.append(validated_row)
        else:
            decision = "MISMATCH"
            mismatch_count += 1

        details.append(
            {
                "mutation_id": mutation_id,
                "decision": decision,
                "expected_failure_type": expected,
                "observed_majority_failure_type": observed,
                "observed_majority_ratio": ratio,
                "run_count": len(labels),
            }
        )

    matched = len(validated)
    compared = len(mutations) - uncertain_count
    match_ratio_pct = round((matched / compared) * 100.0, 2) if compared > 0 else 0.0

    if not mutations:
        reasons.append("no_mutations_in_manifest")
    if compared == 0 and mutations:
        reasons.append("no_mutations_with_sufficient_evidence")
    if match_ratio_pct < float(args.min_match_ratio_pct):
        reasons.append("expected_match_ratio_below_threshold")

    status = "PASS"
    if "mutation_manifest_missing" in reasons or "replay_observations_missing" in reasons:
        status = "FAIL"
    elif reasons:
        status = "NEEDS_REVIEW"

    validated_manifest = {
        "schema_version": "validated_mutation_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mutations": validated,
    }
    _write_json(args.validated_manifest_out, validated_manifest)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_mutations": len(mutations),
        "validated_count": len(validated),
        "mismatch_count": mismatch_count,
        "uncertain_count": uncertain_count,
        "expected_match_ratio_pct": match_ratio_pct,
        "validated_manifest_path": args.validated_manifest_out,
        "details": details,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "replay_observations": args.replay_observations,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "validated_count": len(validated), "expected_match_ratio_pct": match_ratio_pct}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
