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


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Reproducible Mutation Sample Pack v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_candidates: `{payload.get('total_candidates')}`",
        f"- sampled_mutations: `{payload.get('sampled_mutations')}`",
        f"- sample_seed: `{payload.get('sample_seed')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic sample pack from reproducible mutation artifacts")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-raw-observations", default=None)
    parser.add_argument("--sample-size", type=int, default=40)
    parser.add_argument("--sample-seed", default="gateforge-sample-v1")
    parser.add_argument("--pack-out", default="artifacts/dataset_reproducible_mutation_sample_pack_v1/sample_pack.json")
    parser.add_argument("--out", default="artifacts/dataset_reproducible_mutation_sample_pack_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    raw = _load_json(args.mutation_raw_observations)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")

    execution_ok: set[str] = set()
    for row in raw.get("observations") if isinstance(raw.get("observations"), list) else []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("execution_status") or "")
        if status in {"EXECUTED", "PASS", "FAIL", "NEEDS_REVIEW"}:
            execution_ok.add(str(row.get("mutation_id") or ""))

    candidates: list[dict] = []
    for row in manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "")
        if execution_ok and mutation_id not in execution_ok:
            continue
        path = Path(str(row.get("mutated_model_path") or ""))
        if not path.exists() or not path.is_file():
            continue
        token = hashlib.sha256(f"{args.sample_seed}|{mutation_id}|{path}".encode("utf-8")).hexdigest()
        candidates.append(
            {
                "mutation_id": mutation_id,
                "target_model_id": row.get("target_model_id"),
                "target_scale": row.get("target_scale"),
                "expected_failure_type": row.get("expected_failure_type"),
                "mutated_model_path": str(path),
                "file_sha256": _sha256(path),
                "_sort_token": token,
            }
        )

    candidates.sort(key=lambda r: str(r.get("_sort_token") or ""))
    sample_size = max(1, int(args.sample_size))
    samples = [{k: v for k, v in row.items() if not k.startswith("_")} for row in candidates[:sample_size]]

    sample_pack = {
        "schema_version": "reproducible_mutation_sample_pack_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sample_seed": str(args.sample_seed),
        "sampled_mutations": samples,
    }
    _write_json(args.pack_out, sample_pack)

    alerts: list[str] = []
    if not samples:
        alerts.append("no_reproducible_mutation_samples")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "sample_seed": str(args.sample_seed),
        "total_candidates": len(candidates),
        "sampled_mutations": len(samples),
        "sample_pack_path": args.pack_out,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "mutation_raw_observations": args.mutation_raw_observations,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "sampled_mutations": len(samples), "total_candidates": len(candidates)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
