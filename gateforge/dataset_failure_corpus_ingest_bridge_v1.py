from __future__ import annotations

import argparse
import hashlib
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


def _slug(v: object, *, default: str = "unknown") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_manifest_rows(manifest: dict) -> list[dict]:
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


def _majority(labels: list[str]) -> str:
    if not labels:
        return "unknown"
    freq: dict[str, int] = {}
    for x in labels:
        freq[x] = freq.get(x, 0) + 1
    winner = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return str(winner)


def _extract_unstable_ids(stability_summary: dict) -> set[str]:
    rows = stability_summary.get("unstable_mutations") if isinstance(stability_summary.get("unstable_mutations"), list) else []
    return {str(x.get("mutation_id") or "") for x in rows if isinstance(x, dict) and x.get("mutation_id")}


def _extract_existing_cases(db: dict) -> list[dict]:
    rows = db.get("cases") if isinstance(db.get("cases"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Corpus Ingest Bridge v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- ingested_cases: `{payload.get('ingested_cases')}`",
        f"- skipped_unstable_cases: `{payload.get('skipped_unstable_cases')}`",
        f"- total_cases_after: `{payload.get('total_cases_after')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest stable mutation outcomes into failure corpus DB v1")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--repro-stability-summary", required=True)
    parser.add_argument("--replay-observations", required=True)
    parser.add_argument("--existing-failure-corpus-db", default=None)
    parser.add_argument("--db-out", default="artifacts/dataset_failure_corpus_db_v1/db.json")
    parser.add_argument("--out", default="artifacts/dataset_failure_corpus_ingest_bridge_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    stability = _load_json(args.repro_stability_summary)
    observations = _load_json(args.replay_observations)
    existing_db = _load_json(args.existing_failure_corpus_db)

    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not stability:
        reasons.append("repro_stability_summary_missing")
    if not observations:
        reasons.append("replay_observations_missing")

    manifest_rows = _extract_manifest_rows(manifest)
    obs_map = _extract_obs_map(observations)
    unstable_ids = _extract_unstable_ids(stability)
    existing_cases = _extract_existing_cases(existing_db)

    existing_by_case_id = {str(x.get("case_id") or ""): x for x in existing_cases if x.get("case_id")}
    ingested = 0
    skipped_unstable = 0

    for row in manifest_rows:
        mutation_id = str(row.get("mutation_id") or "")
        if not mutation_id:
            continue
        if mutation_id in unstable_ids:
            skipped_unstable += 1
            continue

        labels = obs_map.get(mutation_id, [])
        majority = _majority(labels)
        target_scale = _slug(row.get("target_scale"), default="small")
        failure_type = _slug(majority)
        failure_stage = "simulation"
        severity = "high" if target_scale == "large" else "medium"
        model_name = str(row.get("target_model_id") or "unknown_model")

        fingerprint_basis = json.dumps(
            {
                "mutation_id": mutation_id,
                "target_model_id": model_name,
                "target_scale": target_scale,
                "failure_type": failure_type,
            },
            sort_keys=True,
        )
        fingerprint = _sha256_text(fingerprint_basis)
        case_id = f"mutcase_{fingerprint[:12]}"

        if case_id in existing_by_case_id:
            continue

        new_case = {
            "case_id": case_id,
            "fingerprint": fingerprint,
            "model_scale": target_scale,
            "failure_type": failure_type,
            "failure_stage": failure_stage,
            "severity": severity,
            "model_name": model_name,
            "source_catalog_path": args.mutation_manifest,
            "registered_at_utc": datetime.now(timezone.utc).isoformat(),
            "reproducibility": {
                "simulator_version": "openmodelica-1.25.5",
                "seed": int(row.get("seed") or 0),
                "scenario_hash": mutation_id,
                "repro_command": str(row.get("repro_command") or ""),
            },
            "lineage": {
                "source": "mutation_factory_v1",
                "mutation_id": mutation_id,
            },
        }
        existing_by_case_id[case_id] = new_case
        ingested += 1

    final_cases = sorted(existing_by_case_id.values(), key=lambda x: str(x.get("case_id") or ""))

    db_payload = {
        "schema_version": "failure_corpus_db_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases": final_cases,
    }
    _write_json(args.db_out, db_payload)

    status = "PASS"
    if "mutation_manifest_missing" in reasons or "repro_stability_summary_missing" in reasons or "replay_observations_missing" in reasons:
        status = "FAIL"
    elif ingested == 0:
        reasons.append("no_new_cases_ingested")
        status = "NEEDS_REVIEW"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "db_out": args.db_out,
        "ingested_cases": ingested,
        "skipped_unstable_cases": skipped_unstable,
        "total_cases_after": len(final_cases),
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "repro_stability_summary": args.repro_stability_summary,
            "replay_observations": args.replay_observations,
            "existing_failure_corpus_db": args.existing_failure_corpus_db,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "ingested_cases": ingested, "total_cases_after": len(final_cases)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
