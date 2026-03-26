from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_FAILURE_TYPES = ("model_check_error", "simulate_error", "semantic_regression")
DEFAULT_SCALES = ("small", "medium", "large")
DEFAULT_PUBLIC_HARDPACK_OUT = "benchmarks/agent_modelica_hardpack_v1.json"
DEFAULT_PRIVATE_HARDPACK_OUT = "benchmarks/private/agent_modelica_hardpack_v1.json"


def _load_json(path: str) -> dict:
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


def _default_hardpack_out_path() -> str:
    return DEFAULT_PRIVATE_HARDPACK_OUT


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Hardpack Lock v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- hardpack_version: `{payload.get('hardpack_version')}`",
        f"- total_cases: `{payload.get('total_cases')}`",
        "",
        "## Counts By Scale",
        "",
    ]
    cbs = payload.get("counts_by_scale", {})
    if isinstance(cbs, dict) and cbs:
        for key in sorted(cbs.keys()):
            lines.append(f"- {key}: `{cbs.get(key)}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Missing Targets", ""])
    missing = payload.get("missing_targets", [])
    if isinstance(missing, list) and missing:
        lines.extend([f"- `{x}`" for x in missing])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _collect_rows(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        payload = _load_json(path)
        muts = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
        rows.extend([x for x in muts if isinstance(x, dict)])
    return rows


def _to_case(row: dict) -> dict:
    return {
        "mutation_id": str(row.get("mutation_id") or ""),
        "target_scale": str(row.get("target_scale") or "unknown"),
        "expected_failure_type": str(row.get("expected_failure_type") or "unknown"),
        "expected_stage": str(row.get("expected_stage") or "unknown"),
        "source_model_path": str(row.get("source_model_path") or ""),
        "mutated_model_path": str(row.get("mutated_model_path") or ""),
        "repro_command": str(row.get("repro_command") or ""),
    }


def _matches_include_patterns(row: dict, patterns: list[str]) -> bool:
    if not patterns:
        return True
    haystacks = [
        str(row.get("mutation_id") or ""),
        str(row.get("target_model_id") or ""),
        str(row.get("model_id") or ""),
        str(row.get("source_model_path") or ""),
        str(row.get("mutated_model_path") or ""),
        str(row.get("recipe_id") or ""),
        str(row.get("operator_family") or ""),
        str(row.get("operator") or ""),
    ]
    text = "\n".join(haystacks)
    for pattern in patterns:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        except re.error:
            if pattern.lower() in text.lower():
                return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Lock a deterministic Modelica hard-case benchmark pack")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--extra-mutation-manifest", action="append", default=[])
    parser.add_argument("--hardpack-version", default="agent_modelica_hardpack_v1")
    parser.add_argument("--scales", default=",".join(DEFAULT_SCALES))
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--per-scale-total", type=int, default=12)
    parser.add_argument("--per-scale-failure-targets", default="4,4,4")
    parser.add_argument("--include-pattern", action="append", default=[])
    parser.add_argument("--track-id", default="")
    parser.add_argument("--pack-label", default="")
    parser.add_argument("--library-load-model", action="append", default=[])
    parser.add_argument("--out", default=_default_hardpack_out_path())
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    scales = [x.strip().lower() for x in str(args.scales).split(",") if x.strip()]
    if not scales:
        scales = list(DEFAULT_SCALES)
    failure_types = [x.strip().lower() for x in str(args.failure_types).split(",") if x.strip()]
    if not failure_types:
        failure_types = list(DEFAULT_FAILURE_TYPES)

    targets = [int(x.strip()) for x in str(args.per_scale_failure_targets).split(",") if x.strip()]
    if len(targets) != len(failure_types):
        raise SystemExit("--per-scale-failure-targets must match --failure-types length")

    paths = [str(args.mutation_manifest), *[str(x) for x in (args.extra_mutation_manifest or []) if str(x).strip()]]
    rows = _collect_rows(paths)
    include_patterns = [str(x).strip() for x in (args.include_pattern or []) if str(x).strip()]
    filtered_rows = [row for row in rows if _matches_include_patterns(row, include_patterns)]
    buckets: dict[str, dict[str, list[dict]]] = {s: {f: [] for f in failure_types} for s in scales}
    for row in sorted(
        filtered_rows,
        key=lambda x: (
            str(x.get("target_scale") or "").lower(),
            str(x.get("expected_failure_type") or "").lower(),
            str(x.get("mutation_id") or ""),
        ),
    ):
        scale = str(row.get("target_scale") or "").strip().lower()
        ftype = str(row.get("expected_failure_type") or "").strip().lower()
        if scale in buckets and ftype in buckets[scale]:
            mutation_id = str(row.get("mutation_id") or "").strip()
            if mutation_id:
                buckets[scale][ftype].append(row)

    per_scale_total = max(1, int(args.per_scale_total))
    target_by_type = {failure_types[i]: max(0, int(targets[i])) for i in range(len(failure_types))}
    selected: list[dict] = []
    counts_by_scale = {s: 0 for s in scales}
    counts_by_scale_failure = {s: {f: 0 for f in failure_types} for s in scales}
    missing_targets: list[str] = []

    for scale in scales:
        scale_cases: list[dict] = []
        for ftype in failure_types:
            target = int(target_by_type.get(ftype, 0))
            pool = buckets[scale][ftype]
            picked = pool[:target]
            for row in picked:
                case = _to_case(row)
                scale_cases.append(case)
                counts_by_scale_failure[scale][ftype] = int(counts_by_scale_failure[scale][ftype]) + 1
            if len(picked) < target:
                missing_targets.append(f"{scale}:{ftype}:need_{target}_got_{len(picked)}")

        if len(scale_cases) < per_scale_total:
            used_ids = {str(x.get("mutation_id") or "") for x in scale_cases}
            topup: list[dict] = []
            for ftype in failure_types:
                topup.extend([x for x in buckets[scale][ftype] if str(x.get("mutation_id") or "") not in used_ids])
            need = per_scale_total - len(scale_cases)
            for row in topup[:need]:
                case = _to_case(row)
                scale_cases.append(case)
                ftype = str(case.get("expected_failure_type") or "unknown")
                counts_by_scale_failure[scale][ftype] = int(counts_by_scale_failure[scale].get(ftype, 0)) + 1

        if len(scale_cases) < per_scale_total:
            missing_targets.append(f"{scale}:total:need_{per_scale_total}_got_{len(scale_cases)}")

        locked = scale_cases[:per_scale_total]
        selected.extend(locked)
        counts_by_scale[scale] = len(locked)

    status = "PASS" if not missing_targets else "NEEDS_REVIEW"
    payload = {
        "schema_version": "agent_modelica_hardpack_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "hardpack_version": str(args.hardpack_version),
        "track_id": str(args.track_id or "").strip(),
        "pack_label": str(args.pack_label or "").strip(),
        "scales": scales,
        "failure_types": failure_types,
        "per_scale_total_target": per_scale_total,
        "per_scale_failure_targets": target_by_type,
        "total_cases": len(selected),
        "input_row_count": len(rows),
        "filtered_row_count": len(filtered_rows),
        "include_patterns": include_patterns,
        "library_load_models": [str(x) for x in (args.library_load_model or []) if str(x).strip()],
        "counts_by_scale": counts_by_scale,
        "counts_by_scale_failure_type": counts_by_scale_failure,
        "missing_targets": missing_targets,
        "cases": selected,
        "sources": {"mutation_manifest": paths},
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "total_cases": payload.get("total_cases")}))


if __name__ == "__main__":
    main()
