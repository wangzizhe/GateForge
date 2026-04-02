from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_dual_layer_mutation_v0_3_6 import build_dual_layer_multi_param_task


SCHEMA_VERSION = "agent_modelica_v0_3_13_runtime_pair_preview_taskset"
DEFAULT_SOURCE_MANIFEST = "artifacts/agent_modelica_v0_3_13_runtime_generation_source_current/manifest.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_runtime_pair_preview_taskset"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _build_task_id(source_task_id: str, pair: list[str]) -> str:
    pair_key = "_".join(_norm(name).lower() for name in pair if _norm(name))
    return f"{source_task_id}__pair_{pair_key}__preview"


def _preview_rows(manifest: dict) -> list[dict]:
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        return []
    rows = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        for pair_row in source.get("pair_statuses") or []:
            if not isinstance(pair_row, dict):
                continue
            if _norm(pair_row.get("status")) != "requires_preview":
                continue
            pair = [name for name in pair_row.get("param_names") if _norm(name)]
            if len(pair) != 2:
                continue
            rows.append({"source": source, "param_pair": pair})
    return rows


def build_runtime_pair_preview_taskset(
    *,
    source_manifest_path: str = DEFAULT_SOURCE_MANIFEST,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    manifest = _load_json(source_manifest_path)
    preview_rows = _preview_rows(manifest)
    tasks = []
    for row in preview_rows:
        source = row["source"]
        pair = row["param_pair"]
        task = build_dual_layer_multi_param_task(
            task_id=_build_task_id(_norm(source.get("source_task_id")), pair),
            clean_source_text=_norm(source.get("clean_model_text")),
            source_model_path=_norm(source.get("source_model_path")),
            source_library=_norm(source.get("source_library")),
            model_hint=_norm(source.get("model_hint")),
            hidden_base_operator=_norm(source.get("allowed_hidden_base_operator")) or "paired_value_collapse",
            hidden_base_param_names=(pair[0], pair[1]),
            hidden_base_replacement_values=tuple(
                str(value) for value in ((source.get("default_preset") or {}).get("replacement_values") or ["0.0", "0.0"])
            ),
        )
        task["v0_3_13_source_task_id"] = _norm(source.get("source_task_id"))
        task["v0_3_13_candidate_pair"] = pair
        task["v0_3_13_pair_seed_status"] = "requires_preview"
        tasks.append(task)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if tasks else "EMPTY",
        "source_manifest_path": str(Path(source_manifest_path).resolve()) if Path(source_manifest_path).exists() else str(source_manifest_path),
        "task_count": len(tasks),
        "task_ids": [row["task_id"] for row in tasks],
        "tasks": tasks,
    }
    out_root = Path(out_dir)
    for task in tasks:
        _write_json(out_root / "tasks" / f"{task['task_id']}.json", task)
    _write_json(out_root / "taskset.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.13 Runtime Pair Preview Taskset",
                "",
                f"- status: `{payload.get('status')}`",
                f"- task_count: `{payload.get('task_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 runtime pair preview taskset.")
    parser.add_argument("--source-manifest", default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_runtime_pair_preview_taskset(
        source_manifest_path=str(args.source_manifest),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
