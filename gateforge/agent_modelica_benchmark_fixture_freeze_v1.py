from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUT_ROOT = "assets_private/agent_modelica_track_a_fixture_v1"
DEFAULT_VALID_ONLY_OUT_ROOT = "assets_private/agent_modelica_track_a_valid32_fixture_v1"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


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
        "# GateForge Track A Fixture Freeze v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- copied_sources: `{payload.get('copied_sources')}`",
        f"- copied_mutants: `{payload.get('copied_mutants')}`",
        f"- total_cases: `{payload.get('total_cases')}`",
        f"- missing_files: `{payload.get('missing_files')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _slug(value: object) -> str:
    text = str(value or "").strip().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_") or "unknown"


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _source_copy_name(source_path: Path) -> str:
    digest = hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()[:10]
    return f"{source_path.stem}_{digest}{source_path.suffix or '.mo'}"


def _mutation_copy_name(case: dict, mutated_path: Path) -> str:
    mutation_id = str(case.get("mutation_id") or "").strip()
    if mutation_id:
        return f"{mutation_id}{mutated_path.suffix or '.mo'}"
    return mutated_path.name


def freeze_hardpack_fixture(
    *,
    hardpack_path: str,
    out_root: str = DEFAULT_OUT_ROOT,
    out_hardpack_name: str = "hardpack_frozen.json",
    valid_only: bool = False,
) -> dict:
    hardpack = _load_json(hardpack_path)
    cases = hardpack.get("cases") if isinstance(hardpack.get("cases"), list) else []
    cases = [c for c in cases if isinstance(c, dict)]

    root = Path(out_root)
    source_dir = root / "source_models"
    mutants_dir = root / "mutants"
    frozen_hardpack_path = root / out_hardpack_name
    manifest_path = root / "freeze_manifest.json"
    summary_path = root / "frozen_summary.json"

    copied_sources = 0
    copied_mutants = 0
    missing_files: list[dict] = []
    source_map: dict[str, str] = {}
    frozen_cases: list[dict] = []

    for idx, case in enumerate(cases, 1):
        source_raw = str(case.get("source_model_path") or "").strip()
        mutated_raw = str(case.get("mutated_model_path") or "").strip()
        source_path = Path(source_raw) if source_raw else Path("")
        mutated_path = Path(mutated_raw) if mutated_raw else Path("")

        if not mutated_raw or not mutated_path.exists():
            missing_files.append(
                {
                    "case_index": idx,
                    "mutation_id": str(case.get("mutation_id") or f"case_{idx}"),
                    "kind": "mutated_model_path",
                    "path": mutated_raw,
                }
            )
            if valid_only:
                continue
            continue
        if source_raw and not source_path.exists():
            missing_files.append(
                {
                    "case_index": idx,
                    "mutation_id": str(case.get("mutation_id") or f"case_{idx}"),
                    "kind": "source_model_path",
                    "path": source_raw,
                }
            )
            if valid_only:
                continue
            continue

        frozen_case = dict(case)

        if source_raw:
            if source_raw not in source_map:
                source_dst = source_dir / _source_copy_name(source_path)
                _copy_file(source_path, source_dst)
                copied_sources += 1
                source_map[source_raw] = str(source_dst)
            frozen_case["source_model_path"] = source_map[source_raw]

        failure_type = _slug(case.get("expected_failure_type") or case.get("failure_type"))
        mutation_dst = mutants_dir / failure_type / _mutation_copy_name(case, mutated_path)
        _copy_file(mutated_path, mutation_dst)
        copied_mutants += 1
        frozen_case["mutated_model_path"] = str(mutation_dst)
        frozen_cases.append(frozen_case)

    status = "PASS" if (valid_only or not missing_files) else "FAIL"
    frozen_hardpack = dict(hardpack)
    frozen_hardpack["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    frozen_hardpack["status"] = status
    frozen_hardpack["cases"] = frozen_cases
    if valid_only:
        frozen_hardpack["hardpack_version"] = (
            f"{str(hardpack.get('hardpack_version') or 'agent_modelica_hardpack_v1')}_valid_only"
        )
        frozen_hardpack["fixture_mode"] = "valid_only"
        frozen_hardpack["excluded_missing_cases"] = [
            str(x.get("mutation_id") or "") for x in missing_files
        ]
    frozen_hardpack["sources"] = {
        "source_hardpack": hardpack_path,
        "fixture_root": str(root),
    }
    _write_json(frozen_hardpack_path, frozen_hardpack)

    manifest = {
        "schema_version": "agent_modelica_track_a_fixture_freeze_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source_hardpack": hardpack_path,
        "fixture_root": str(root),
        "frozen_hardpack_path": str(frozen_hardpack_path),
        "fixture_mode": "valid_only" if valid_only else "strict",
        "total_cases": len(cases),
        "copied_cases": len(frozen_cases),
        "copied_sources": copied_sources,
        "copied_mutants": copied_mutants,
        "missing_files": missing_files,
    }
    _write_json(manifest_path, manifest)

    summary = {
        "schema_version": "agent_modelica_track_a_fixture_summary_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "fixture_root": str(root),
        "source_hardpack": hardpack_path,
        "frozen_hardpack_path": str(frozen_hardpack_path),
        "fixture_mode": "valid_only" if valid_only else "strict",
        "total_cases": len(cases),
        "copied_cases": len(frozen_cases),
        "copied_sources": copied_sources,
        "copied_mutants": copied_mutants,
        "missing_files": len(missing_files),
    }
    _write_json(summary_path, summary)
    _write_markdown(_default_md_path(summary_path), summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze Track A benchmark fixtures into assets_private")
    parser.add_argument("--hardpack", required=True)
    parser.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    parser.add_argument("--out-hardpack-name", default="hardpack_frozen.json")
    parser.add_argument(
        "--valid-only",
        action="store_true",
        help="Freeze only cases whose source/mutated files currently exist",
    )
    args = parser.parse_args()

    summary = freeze_hardpack_fixture(
        hardpack_path=args.hardpack,
        out_root=args.out_root,
        out_hardpack_name=args.out_hardpack_name,
        valid_only=args.valid_only,
    )
    print(json.dumps({"status": summary.get("status"), "copied_cases": summary.get("copied_cases")}))


if __name__ == "__main__":
    main()
