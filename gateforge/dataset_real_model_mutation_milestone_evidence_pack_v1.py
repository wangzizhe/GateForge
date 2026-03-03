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


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 2)


def _sha256_of_file(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _artifact_digest(paths: list[str]) -> str:
    h = hashlib.sha256()
    for p in sorted(set(x for x in paths if x)):
        h.update(p.encode("utf-8"))
        h.update(b"|")
        h.update(_sha256_of_file(p).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model + Mutation Milestone Evidence Pack v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- milestone_id: `{payload.get('milestone_id')}`",
        f"- evidence_score: `{payload.get('evidence_score')}`",
        f"- publishable: `{payload.get('publishable')}`",
        f"- accepted_models: `{payload.get('accepted_models')}`",
        f"- accepted_large_models: `{payload.get('accepted_large_models')}`",
        f"- generated_mutations: `{payload.get('generated_mutations')}`",
        f"- reproducible_mutations: `{payload.get('reproducible_mutations')}`",
        "",
        "## Repro Commands",
        "",
    ]
    commands = payload.get("repro_commands") if isinstance(payload.get("repro_commands"), list) else []
    if commands:
        for c in commands:
            lines.append(f"- `{c}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build milestone evidence pack from open-source intake + mutation scale sprint")
    parser.add_argument("--open-source-bootstrap-summary", required=True)
    parser.add_argument("--scale-batch-summary", required=True)
    parser.add_argument("--scale-gate-summary", required=True)
    parser.add_argument("--source-manifest", default=None)
    parser.add_argument("--min-accepted-models", type=int, default=300)
    parser.add_argument("--min-accepted-large-models", type=int, default=80)
    parser.add_argument("--min-generated-mutations", type=int, default=2000)
    parser.add_argument("--min-reproducibility-ratio-pct", type=float, default=98.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_mutation_milestone_evidence_pack_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    bootstrap = _load_json(args.open_source_bootstrap_summary)
    scale_batch = _load_json(args.scale_batch_summary)
    scale_gate = _load_json(args.scale_gate_summary)
    manifest = _load_json(args.source_manifest)

    reasons: list[str] = []
    if not bootstrap:
        reasons.append("open_source_bootstrap_summary_missing")
    if not scale_batch:
        reasons.append("scale_batch_summary_missing")
    if not scale_gate:
        reasons.append("scale_gate_summary_missing")

    accepted_models = _to_int(scale_batch.get("accepted_models", 0))
    accepted_large_models = _to_int(scale_batch.get("accepted_large_models", 0))
    generated_mutations = _to_int(scale_batch.get("generated_mutations", 0))
    reproducible_mutations = _to_int(scale_batch.get("reproducible_mutations", 0))
    selected_mutation_models = _to_int(scale_batch.get("selected_mutation_models", 0))
    mutations_per_failure_type = _to_int(scale_batch.get("mutations_per_failure_type", 0))
    failure_types_count = _to_int(scale_batch.get("failure_types_count", 0))
    harvest_total_candidates = _to_int(bootstrap.get("harvest_total_candidates", 0))
    bootstrap_accepted_models = _to_int(bootstrap.get("accepted_models", 0))

    scale_gate_status = str(scale_gate.get("status") or scale_batch.get("scale_gate_status") or "UNKNOWN")
    bundle_status = str(scale_batch.get("bundle_status") or "UNKNOWN")

    reproducibility_ratio_pct = _round(
        100.0 * reproducible_mutations / max(1, generated_mutations)
    )
    mutations_per_accepted_model = _round(generated_mutations / max(1, accepted_models))

    alerts: list[str] = []
    if accepted_models < int(args.min_accepted_models):
        alerts.append("accepted_models_below_target")
    if accepted_large_models < int(args.min_accepted_large_models):
        alerts.append("accepted_large_models_below_target")
    if generated_mutations < int(args.min_generated_mutations):
        alerts.append("generated_mutations_below_target")
    if reproducibility_ratio_pct < float(args.min_reproducibility_ratio_pct):
        alerts.append("reproducibility_ratio_below_target")
    if scale_gate_status != "PASS":
        alerts.append("scale_gate_not_pass")
    if bundle_status != "PASS":
        alerts.append("scale_batch_bundle_not_pass")

    evidence_score = _round(
        _clamp(
            min(35.0, accepted_models / max(1.0, float(args.min_accepted_models)) * 35.0)
            + min(20.0, accepted_large_models / max(1.0, float(args.min_accepted_large_models)) * 20.0)
            + min(25.0, generated_mutations / max(1.0, float(args.min_generated_mutations)) * 25.0)
            + min(15.0, reproducibility_ratio_pct / max(1.0, float(args.min_reproducibility_ratio_pct)) * 15.0)
            + (5.0 if scale_gate_status == "PASS" else 0.0)
        )
    )

    publishable = not reasons and not alerts and evidence_score >= 80.0
    status = "PASS" if publishable else "NEEDS_REVIEW"
    if reasons:
        status = "FAIL"

    source_paths = [
        args.open_source_bootstrap_summary,
        args.scale_batch_summary,
        args.scale_gate_summary,
        args.source_manifest or "",
    ]
    digest = _artifact_digest(source_paths)
    milestone_id = f"real_model_mutation_milestone_{digest[:12]}"

    manifest_sources = manifest.get("sources") if isinstance(manifest.get("sources"), list) else []
    source_library_count = len([x for x in manifest_sources if isinstance(x, dict)])

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "publishable": publishable,
        "milestone_id": milestone_id,
        "evidence_score": evidence_score,
        "scale_gate_status": scale_gate_status,
        "bundle_status": bundle_status,
        "harvest_total_candidates": harvest_total_candidates,
        "bootstrap_accepted_models": bootstrap_accepted_models,
        "accepted_models": accepted_models,
        "accepted_large_models": accepted_large_models,
        "generated_mutations": generated_mutations,
        "reproducible_mutations": reproducible_mutations,
        "reproducibility_ratio_pct": reproducibility_ratio_pct,
        "mutations_per_accepted_model": mutations_per_accepted_model,
        "selected_mutation_models": selected_mutation_models,
        "failure_types_count": failure_types_count,
        "mutations_per_failure_type": mutations_per_failure_type,
        "source_library_count": source_library_count,
        "artifact_digest_sha256": digest,
        "milestone_claims": [
            {
                "claim_id": "real_model.accepted_count",
                "value": accepted_models,
                "text": f"accepted real models = {accepted_models}",
            },
            {
                "claim_id": "real_model.accepted_large_count",
                "value": accepted_large_models,
                "text": f"accepted large models = {accepted_large_models}",
            },
            {
                "claim_id": "mutation.generated_count",
                "value": generated_mutations,
                "text": f"generated reproducible mutations = {generated_mutations}",
            },
            {
                "claim_id": "mutation.reproducibility_ratio_pct",
                "value": reproducibility_ratio_pct,
                "text": f"reproducibility ratio = {reproducibility_ratio_pct}%",
            },
        ],
        "repro_commands": [
            "bash scripts/run_modelica_open_source_bootstrap_v1.sh",
            'GATEFORGE_PRIVATE_MODEL_ROOTS="assets_private/modelica/open_source" bash scripts/run_private_model_mutation_scale_sprint_v1.sh',
            'GATEFORGE_PRIVATE_MODEL_ROOTS="assets_private/modelica/open_source" bash scripts/run_private_model_mutation_depth4_sprint_v1.sh',
        ],
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "open_source_bootstrap_summary": args.open_source_bootstrap_summary,
            "scale_batch_summary": args.scale_batch_summary,
            "scale_gate_summary": args.scale_gate_summary,
            "source_manifest": args.source_manifest,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "publishable": publishable,
                "evidence_score": evidence_score,
                "accepted_models": accepted_models,
                "generated_mutations": generated_mutations,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
