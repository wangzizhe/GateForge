from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_cross_domain_track_prepare_v1"
DEFAULT_SOURCE_MANIFEST = "data/modelica_cross_domain_seed_sources_v1.json"
DEFAULT_TRACK_MANIFEST = "data/agent_modelica_cross_domain_track_manifest_v1.json"


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


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str | Path) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str | Path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent Modelica Cross-Domain Track Prepare v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- track_id: `{payload.get('track_id')}`",
        f"- library: `{payload.get('library')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        "",
        "## Steps",
        "",
    ]
    for step in payload.get("steps") or []:
        if not isinstance(step, dict):
            continue
        lines.append(f"- `{step.get('name')}`: `{step.get('status')}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def resolve_track_entry(track_manifest: dict, track_id: str) -> dict:
    tracks = track_manifest.get("tracks") if isinstance(track_manifest.get("tracks"), list) else []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        if str(track.get("track_id") or "").strip() == str(track_id or "").strip():
            return track
    return {}


def build_filtered_source_manifest(source_manifest: dict, source_id: str) -> dict:
    sources = source_manifest.get("sources") if isinstance(source_manifest.get("sources"), list) else []
    filtered = [
        src
        for src in sources
        if isinstance(src, dict) and str(src.get("source_id") or "").strip() == str(source_id or "").strip()
    ]
    return {
        "schema_version": str(source_manifest.get("schema_version") or "modelica_open_source_seed_sources_v1"),
        "sources": filtered,
    }


def build_prepare_commands(
    *,
    out_dir: str,
    filtered_source_manifest_path: str,
    track_entry: dict,
    target_scales: str,
    failure_types: str,
    mutations_per_failure_type: int,
    max_models: int,
    per_scale_total: int,
    per_scale_failure_targets: str,
    frozen_root: str,
    valid_only: bool,
) -> list[dict]:
    harvest_dir = Path(out_dir) / "harvest"
    intake_dir = Path(out_dir) / "intake"
    selection_dir = Path(out_dir) / "selection"
    mutation_dir = Path(out_dir) / "mutation"
    hardpack_dir = Path(out_dir) / "hardpack"

    include_patterns = [str(x) for x in (track_entry.get("include_patterns") or []) if str(x).strip()]
    library_load_models = [str(x) for x in (track_entry.get("library_load_models") or []) if str(x).strip()]
    pack_label = str(track_entry.get("pack_label") or track_entry.get("library") or track_entry.get("track_id") or "")
    track_id = str(track_entry.get("track_id") or "").strip()
    scale_list = [x.strip().lower() for x in str(target_scales).split(",") if x.strip()]
    selection_max_models = min(int(max_models), len(scale_list)) if scale_list else int(max_models)
    if selection_max_models <= 0:
        selection_max_models = len(scale_list) or 1

    commands: list[dict] = [
        {
            "name": "harvest",
            "cmd": [
                sys.executable,
                "-m",
                "gateforge.dataset_modelica_open_source_harvest_v1",
                "--source-manifest",
                filtered_source_manifest_path,
                "--source-cache-root",
                "assets_private/modelica_sources",
                "--export-root",
                str(harvest_dir / "exported"),
                "--max-models-per-source",
                str(max_models),
                "--catalog-out",
                str(harvest_dir / "candidate_catalog.json"),
                "--out",
                str(harvest_dir / "summary.json"),
            ],
        },
        {
            "name": "intake",
            "cmd": [
                sys.executable,
                "-m",
                "gateforge.dataset_open_source_model_intake_v1",
                "--candidate-catalog",
                str(harvest_dir / "candidate_catalog.json"),
                "--source-name",
                str(track_entry.get("library") or track_id),
                "--registry-out",
                str(intake_dir / "accepted_registry_rows.json"),
                "--out",
                str(intake_dir / "summary.json"),
            ],
        },
        {
            "name": "build_selection_plan",
            "cmd": [
                sys.executable,
                "-m",
                "gateforge.dataset_mutation_model_selection_plan_v1",
                "--executable-registry",
                str(intake_dir / "accepted_registry_rows.json"),
                "--target-scales",
                str(target_scales),
                "--max-models",
                str(selection_max_models),
                "--min-covered-scales",
                str(len(scale_list) or 1),
                "--min-covered-families",
                "1",
                "--min-source-buckets",
                "1",
                "--plan-out",
                str(selection_dir / "selection_plan.json"),
                "--out",
                str(selection_dir / "summary.json"),
            ],
        },
        {
            "name": "materialize_mutations",
            "cmd": [
                sys.executable,
                "-m",
                "gateforge.dataset_mutation_model_materializer_v1",
                "--model-registry",
                str(intake_dir / "accepted_registry_rows.json"),
                "--selection-plan",
                str(selection_dir / "selection_plan.json"),
                "--target-scales",
                str(target_scales),
                "--failure-types",
                str(failure_types),
                "--mutations-per-failure-type",
                str(int(mutations_per_failure_type)),
                "--max-models",
                str(int(max_models)),
                "--mutant-root",
                str(mutation_dir / "mutants"),
                "--manifest-out",
                str(mutation_dir / "mutation_manifest.json"),
                "--out",
                str(mutation_dir / "summary.json"),
            ],
        },
        {
            "name": "lock_hardpack",
            "cmd": [
                sys.executable,
                "-m",
                "gateforge.agent_modelica_hardpack_lock_v1",
                "--mutation-manifest",
                str(mutation_dir / "mutation_manifest.json"),
                "--per-scale-total",
                str(int(per_scale_total)),
                "--per-scale-failure-targets",
                str(per_scale_failure_targets),
                "--track-id",
                track_id,
                "--pack-label",
                pack_label,
                "--out",
                str(hardpack_dir / "hardpack.json"),
            ],
            "include_patterns": include_patterns,
            "library_load_models": library_load_models,
        },
        {
            "name": "freeze_fixture",
            "cmd": [
                sys.executable,
                "-m",
                "gateforge.agent_modelica_benchmark_fixture_freeze_v1",
                "--hardpack",
                str(hardpack_dir / "hardpack.json"),
                "--out-root",
                str(frozen_root),
            ]
            + (["--valid-only"] if bool(valid_only) else []),
        },
    ]
    return commands


def _run_step(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return int(proc.returncode), str(proc.stdout or ""), str(proc.stderr or "")


def run_prepare_track(
    *,
    track_id: str,
    source_manifest_path: str = DEFAULT_SOURCE_MANIFEST,
    track_manifest_path: str = DEFAULT_TRACK_MANIFEST,
    out_dir: str = "",
    frozen_root: str = "",
    target_scales: str = "small,medium,large",
    failure_types: str = "model_check_error,simulate_error,semantic_regression",
    mutations_per_failure_type: int = 2,
    max_models: int = 6,
    per_scale_total: int = 6,
    per_scale_failure_targets: str = "2,2,2",
    valid_only: bool = True,
    dry_run: bool = False,
) -> dict:
    source_manifest = _load_json(source_manifest_path)
    track_manifest = _load_json(track_manifest_path)
    track_entry = resolve_track_entry(track_manifest, track_id)

    if not source_manifest or not track_entry:
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "track_id": str(track_id or ""),
            "reasons": [
                r
                for r, cond in (
                    ("source_manifest_missing_or_invalid", not source_manifest),
                    ("track_entry_missing", not track_entry),
                )
                if cond
            ],
            "steps": [],
        }
        return summary

    track_source_id = str(track_entry.get("source_manifest_source_id") or "").strip()
    filtered_manifest = build_filtered_source_manifest(source_manifest, track_source_id)
    out_root = Path(out_dir or f"artifacts/agent_modelica_cross_domain_track_prepare_v1/{track_id}")
    filtered_manifest_path = out_root / "filtered_source_manifest.json"
    _write_json(filtered_manifest_path, filtered_manifest)

    effective_frozen_root = frozen_root or f"assets_private/agent_modelica_cross_domain_{track_id}_fixture_v1"
    commands = build_prepare_commands(
        out_dir=str(out_root),
        filtered_source_manifest_path=str(filtered_manifest_path),
        track_entry=track_entry,
        target_scales=target_scales,
        failure_types=failure_types,
        mutations_per_failure_type=mutations_per_failure_type,
        max_models=max_models,
        per_scale_total=per_scale_total,
        per_scale_failure_targets=per_scale_failure_targets,
        frozen_root=str(effective_frozen_root),
        valid_only=valid_only,
    )

    steps: list[dict] = []
    status = "PASS"
    for step in commands:
        cmd = list(step.get("cmd") or [])
        if step.get("name") == "lock_hardpack":
            for pattern in step.get("include_patterns") or []:
                cmd += ["--include-pattern", str(pattern)]
            for model_name in step.get("library_load_models") or []:
                cmd += ["--library-load-model", str(model_name)]
        entry = {
            "name": str(step.get("name") or ""),
            "cmd": cmd,
            "status": "PLANNED" if dry_run else "PENDING",
        }
        if dry_run:
            steps.append(entry)
            continue
        rc, stdout, stderr = _run_step(cmd)
        entry["status"] = "PASS" if rc == 0 else "FAIL"
        entry["exit_code"] = rc
        entry["stdout_tail"] = stdout[-500:]
        entry["stderr_tail"] = stderr[-500:]
        steps.append(entry)
        if rc != 0:
            status = "FAIL"
            break

    if dry_run:
        status = "PASS"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "track_id": str(track_entry.get("track_id") or track_id),
        "library": str(track_entry.get("library") or ""),
        "dry_run": bool(dry_run),
        "source_manifest_path": str(source_manifest_path),
        "track_manifest_path": str(track_manifest_path),
        "filtered_source_manifest_path": str(filtered_manifest_path),
        "frozen_root": str(effective_frozen_root),
        "steps": steps,
        "artifacts": {
            "harvest_summary": str(out_root / "harvest" / "summary.json"),
            "intake_summary": str(out_root / "intake" / "summary.json"),
            "selection_summary": str(out_root / "selection" / "summary.json"),
            "mutation_summary": str(out_root / "mutation" / "summary.json"),
            "hardpack_path": str(out_root / "hardpack" / "hardpack.json"),
            "frozen_hardpack_path": str(Path(effective_frozen_root) / "hardpack_frozen.json"),
        },
    }
    _write_json(out_root / "summary.json", summary)
    _write_markdown(out_root / "summary.md", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a local cross-domain library track for benchmark validation")
    parser.add_argument("--track-id", required=True)
    parser.add_argument("--source-manifest", default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--track-manifest", default=DEFAULT_TRACK_MANIFEST)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--frozen-root", default="")
    parser.add_argument("--target-scales", default="small,medium,large")
    parser.add_argument("--failure-types", default="model_check_error,simulate_error,semantic_regression")
    parser.add_argument("--mutations-per-failure-type", type=int, default=2)
    parser.add_argument("--max-models", type=int, default=6)
    parser.add_argument("--per-scale-total", type=int, default=6)
    parser.add_argument("--per-scale-failure-targets", default="2,2,2")
    parser.add_argument("--valid-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = run_prepare_track(
        track_id=args.track_id,
        source_manifest_path=args.source_manifest,
        track_manifest_path=args.track_manifest,
        out_dir=args.out_dir,
        frozen_root=args.frozen_root,
        target_scales=args.target_scales,
        failure_types=args.failure_types,
        mutations_per_failure_type=args.mutations_per_failure_type,
        max_models=args.max_models,
        per_scale_total=args.per_scale_total,
        per_scale_failure_targets=args.per_scale_failure_targets,
        valid_only=bool(args.valid_only),
        dry_run=bool(args.dry_run),
    )
    print(json.dumps({"status": summary.get("status"), "track_id": summary.get("track_id"), "dry_run": summary.get("dry_run")}))
    if str(summary.get("status") or "") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
