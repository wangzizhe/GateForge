from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Failure-Repair Corpus v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- row_count: `{payload.get('row_count')}`",
        "",
        "## Failure Type Distribution",
        "",
    ]
    dist = payload.get("failure_type_distribution", {})
    if isinstance(dist, dict) and dist:
        for key in sorted(dist.keys()):
            lines.append(f"- {key}: `{dist[key]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _collect_manifest_rows(paths: list[str]) -> list[dict]:
    out: list[dict] = []
    for path in paths:
        payload = _load_json(path)
        rows = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
        out.extend([x for x in rows if isinstance(x, dict)])
    return out


def _load_run_results(path: str | None) -> dict[str, dict]:
    if not isinstance(path, str) or not path.strip():
        return {}
    payload = _load_json(path)
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    out: dict[str, dict] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        mutation_id = str(rec.get("mutation_id") or "").strip()
        task_id = str(rec.get("task_id") or "").strip()
        if not mutation_id and task_id.startswith("task_"):
            mutation_id = task_id[5:]
        if mutation_id:
            out[mutation_id] = rec
    return out


def _hard_fail_tags(record: dict) -> list[str]:
    hard = record.get("hard_checks") if isinstance(record.get("hard_checks"), dict) else {}
    out: list[str] = []
    if hard and not bool(hard.get("check_model_pass")):
        out.append("check_model_fail")
    if hard and not bool(hard.get("simulate_pass")):
        out.append("simulate_fail")
    if hard and not bool(hard.get("physics_contract_pass")):
        out.append("physics_fail")
    if hard and not bool(hard.get("regression_pass")):
        out.append("regression_fail")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build failure->repair corpus from existing mutation databases")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--extra-mutation-manifest", action="append", default=[])
    parser.add_argument("--run-results", default=None)
    parser.add_argument("--max-rows", type=int, default=50000)
    parser.add_argument("--out", default="artifacts/agent_modelica_failure_repair_corpus_v1/corpus.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest_paths = [args.mutation_manifest, *[str(x) for x in (args.extra_mutation_manifest or []) if str(x).strip()]]
    rows = _collect_manifest_rows(manifest_paths)
    rows = sorted(
        rows,
        key=lambda x: (
            str(x.get("target_scale") or "").lower(),
            str(x.get("expected_failure_type") or "").lower(),
            str(x.get("mutation_id") or ""),
        ),
    )
    run_map = _load_run_results(args.run_results)

    out_rows: list[dict] = []
    failure_counter: Counter[str] = Counter()
    scale_counter: Counter[str] = Counter()
    for row in rows[: max(1, int(args.max_rows))]:
        mutation_id = str(row.get("mutation_id") or "").strip()
        if not mutation_id:
            continue
        failure_type = str(row.get("expected_failure_type") or "unknown").strip().lower()
        scale = str(row.get("target_scale") or "unknown").strip().lower()
        stage = str(row.get("expected_stage") or "unknown").strip().lower()
        rec = run_map.get(mutation_id, {})
        hard_fail_tags = _hard_fail_tags(rec)
        physics_reasons = [str(x) for x in (rec.get("physics_contract_reasons") or []) if isinstance(x, str)]
        regression_reasons = [str(x) for x in (rec.get("regression_reasons") or []) if isinstance(x, str)]

        out_rows.append(
            {
                "case_id": f"case_{mutation_id}",
                "mutation_id": mutation_id,
                "scale": scale,
                "failure_type": failure_type,
                "expected_stage": stage,
                "failure_signature": f"{scale}:{failure_type}:{stage}",
                "source_model_path": str(row.get("source_model_path") or ""),
                "mutated_model_path": str(row.get("mutated_model_path") or ""),
                "repro_command": str(row.get("repro_command") or ""),
                "operator": str(row.get("operator") or ""),
                "seed": row.get("seed"),
                "hard_fail_tags": hard_fail_tags,
                "physics_reasons": physics_reasons,
                "regression_reasons": regression_reasons,
            }
        )
        failure_counter[failure_type] += 1
        scale_counter[scale] += 1

    payload = {
        "schema_version": "agent_modelica_failure_repair_corpus_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if out_rows else "NEEDS_REVIEW",
        "row_count": len(out_rows),
        "failure_type_distribution": dict(failure_counter),
        "scale_distribution": dict(scale_counter),
        "rows": out_rows,
        "sources": {
            "mutation_manifest": manifest_paths,
            "run_results": args.run_results,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "row_count": payload.get("row_count")}))


if __name__ == "__main__":
    main()
