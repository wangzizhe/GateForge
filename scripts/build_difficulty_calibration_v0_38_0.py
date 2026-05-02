#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_difficulty_calibration_v0_38_0 import (  # noqa: E402
    build_difficulty_calibration_summary,
)


DEFAULT_REGISTRY = REPO_ROOT / "artifacts" / "hard_pool_registry_v0_37_12" / "registry.jsonl"
DEFAULT_GATE = REPO_ROOT / "artifacts" / "hard_pool_registry_v0_37_12" / "gate_summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "difficulty_calibration_v0_38_0"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def load_gate_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    results = payload.get("results") if isinstance(payload, dict) else None
    return results if isinstance(results, list) else []


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.38 difficulty calibration from the hard pool registry.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--gate-summary", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    seeds = load_jsonl(args.registry)
    gate_rows = load_gate_rows(args.gate_summary)
    summary = build_difficulty_calibration_summary(seeds, gate_rows=gate_rows)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": summary["status"], "bucket_counts": summary["bucket_counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

