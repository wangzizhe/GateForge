from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_runtime_pair_inventory"
DEFAULT_SOURCE_MANIFEST = "artifacts/agent_modelica_v0_3_13_runtime_generation_source_current/manifest.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_runtime_pair_inventory"


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


def build_runtime_pair_inventory(
    *,
    source_manifest_path: str = DEFAULT_SOURCE_MANIFEST,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    manifest = _load_json(source_manifest_path)
    sources = manifest.get("sources") if isinstance(manifest.get("sources"), list) else []
    inventory_rows = []
    status_counts: dict[str, int] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_task_id = _norm(source.get("source_task_id"))
        for pair_row in source.get("pair_statuses") or []:
            if not isinstance(pair_row, dict):
                continue
            status = _norm(pair_row.get("status")) or "unknown"
            row = {
                "source_task_id": source_task_id,
                "model_hint": _norm(source.get("model_hint")),
                "param_names": [name for name in pair_row.get("param_names") if _norm(name)],
                "status": status,
                "operator": _norm(source.get("allowed_hidden_base_operator")),
                "replacement_values": list((source.get("default_preset") or {}).get("replacement_values") or []),
            }
            inventory_rows.append(row)
            status_counts[status] = status_counts.get(status, 0) + 1

    preview_queue = [
        row for row in inventory_rows if _norm(row.get("status")) == "requires_preview"
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if inventory_rows else "EMPTY",
        "source_manifest_path": str(Path(source_manifest_path).resolve()) if Path(source_manifest_path).exists() else str(source_manifest_path),
        "inventory_count": len(inventory_rows),
        "status_counts": status_counts,
        "preview_queue_count": len(preview_queue),
        "preview_queue": preview_queue,
        "rows": inventory_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# v0.3.13 Runtime Pair Inventory",
        "",
        f"- status: `{payload.get('status')}`",
        f"- inventory_count: `{payload.get('inventory_count')}`",
        f"- preview_queue_count: `{payload.get('preview_queue_count')}`",
        "",
    ]
    for key, value in sorted((payload.get("status_counts") or {}).items()):
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 runtime pair inventory.")
    parser.add_argument("--source-manifest", default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_runtime_pair_inventory(
        source_manifest_path=str(args.source_manifest),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "preview_queue_count": payload.get("preview_queue_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
