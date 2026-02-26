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


def _extract_mutation_ids(manifest: dict) -> list[str]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "")
        if mutation_id:
            out.append(mutation_id)
    return out


def _extract_observation_map(observations: dict) -> dict[str, list[str]]:
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


def _majority_ratio(labels: list[str]) -> float:
    if not labels:
        return 0.0
    c = Counter(labels)
    top = c.most_common(1)[0][1]
    return round(top / len(labels), 4)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Repro Stability Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- stable_cases: `{payload.get('stable_cases')}`",
        f"- total_checked_cases: `{payload.get('total_checked_cases')}`",
        f"- stability_ratio_pct: `{payload.get('stability_ratio_pct')}`",
        "",
        "## Unstable Mutations",
        "",
    ]
    unstable = payload.get("unstable_mutations") if isinstance(payload.get("unstable_mutations"), list) else []
    if unstable:
        for row in unstable[:20]:
            lines.append(
                f"- `{row.get('mutation_id')}` majority_ratio=`{row.get('majority_ratio')}` runs=`{row.get('run_count')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stability gate for mutation reproducibility across repeated replay observations")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--replay-observations", required=True)
    parser.add_argument("--min-runs-per-mutation", type=int, default=3)
    parser.add_argument("--min-majority-ratio", type=float, default=0.8)
    parser.add_argument("--min-stability-ratio-pct", type=float, default=85.0)
    parser.add_argument("--out", default="artifacts/dataset_repro_stability_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    observations = _load_json(args.replay_observations)

    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not observations:
        reasons.append("replay_observations_missing")

    mutation_ids = _extract_mutation_ids(manifest)
    obs_map = _extract_observation_map(observations)

    checked = 0
    stable = 0
    unstable_rows: list[dict] = []
    min_runs = max(1, int(args.min_runs_per_mutation))
    min_majority = float(args.min_majority_ratio)

    for mutation_id in mutation_ids:
        labels = obs_map.get(mutation_id, [])
        if len(labels) < min_runs:
            unstable_rows.append(
                {
                    "mutation_id": mutation_id,
                    "run_count": len(labels),
                    "majority_ratio": 0.0,
                    "reason": "insufficient_runs",
                }
            )
            checked += 1
            continue

        ratio = _majority_ratio(labels)
        checked += 1
        if ratio >= min_majority:
            stable += 1
        else:
            unstable_rows.append(
                {
                    "mutation_id": mutation_id,
                    "run_count": len(labels),
                    "majority_ratio": ratio,
                    "reason": "label_instability",
                }
            )

    stability_ratio_pct = round((stable / checked) * 100.0, 2) if checked > 0 else 0.0

    if checked == 0:
        reasons.append("no_mutations_checked")
    if stability_ratio_pct < float(args.min_stability_ratio_pct):
        reasons.append("stability_ratio_below_threshold")

    status = "PASS"
    if "mutation_manifest_missing" in reasons or "replay_observations_missing" in reasons:
        status = "FAIL"
    elif reasons:
        status = "NEEDS_REVIEW"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_checked_cases": checked,
        "stable_cases": stable,
        "unstable_cases": len(unstable_rows),
        "stability_ratio_pct": stability_ratio_pct,
        "thresholds": {
            "min_runs_per_mutation": min_runs,
            "min_majority_ratio": min_majority,
            "min_stability_ratio_pct": float(args.min_stability_ratio_pct),
        },
        "unstable_mutations": unstable_rows,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "replay_observations": args.replay_observations,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "stability_ratio_pct": stability_ratio_pct, "total_checked_cases": checked}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
