from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_0_release_summary"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_0"
DEFAULT_BLOCKS = (
    {
        "block_id": "block_0_foundation_acceptance",
        "summary_path": "artifacts/agent_modelica_foundation_acceptance_v0/v0_3_0/summary.json",
    },
    {
        "block_id": "block_1_layer4_family_spec",
        "summary_path": "artifacts/agent_modelica_layer4_family_spec_v0_3_0/summary.json",
    },
    {
        "block_id": "block_2_layer4_hard_lane",
        "summary_path": "artifacts/agent_modelica_layer4_hard_lane_v0_3_0/summary.json",
    },
    {
        "block_id": "block_3_layer_balance_refresh",
        "summary_path": "artifacts/agent_modelica_difficulty_layer_v0_3_0/summary.json",
    },
    {
        "block_id": "block_4_track_c_pilot",
        "summary_path": "artifacts/agent_modelica_track_c_pilot_v0_3_0/summary.json",
    },
)


def _load_json(path: str | Path) -> dict:
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


def build_v0_3_0_release_summary(*, out_dir: str = DEFAULT_OUT_DIR, blocks: list[dict] | None = None) -> dict:
    rows: list[dict] = []
    overall_status = "PASS"
    for block in blocks or list(DEFAULT_BLOCKS):
        block_id = str(block.get("block_id") or "").strip()
        summary_path = str(block.get("summary_path") or "").strip()
        payload = _load_json(summary_path)
        status = str(payload.get("status") or "MISSING").strip().upper() if payload else "MISSING"
        if status != "PASS":
            overall_status = "FAIL"
        rows.append(
            {
                "block_id": block_id,
                "status": status,
                "summary_path": str(Path(summary_path).resolve()) if Path(summary_path).exists() else summary_path,
            }
        )
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "block_count": len(rows),
        "blocks": rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", result)
    (out_root / "summary.md").write_text(
        "\n".join(
            [
                "# GateForge v0.3.0 Release Summary",
                "",
                f"- status: `{result.get('status')}`",
                f"- block_count: `{result.get('block_count')}`",
                "",
                *[
                    f"- {row.get('block_id')}: `{row.get('status')}`"
                    for row in rows
                ],
            ]
        ),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize v0.3.0 block completion")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    payload = build_v0_3_0_release_summary(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "block_count": int(payload.get("block_count") or 0)}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
