from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_1_release_summary"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_1"
DEFAULT_BLOCKS = (
    {
        "block_id": "block_0_v0_3_0_seal",
        "summary_path": "artifacts/agent_modelica_v0_3_0_seal_v1/summary.json",
    },
    {
        "block_id": "block_1_structural_singularity_trial",
        "summary_path": "artifacts/agent_modelica_structural_singularity_trial_v0_3_1/summary.json",
    },
    {
        "block_id": "block_2_layer4_holdout_pack",
        "summary_path": "artifacts/agent_modelica_layer4_holdout_pack_v0_3_1/summary.json",
    },
    {
        "block_id": "block_3_harder_holdout_ablation",
        "summary_path": "artifacts/agent_modelica_harder_holdout_ablation_v0_3_1/summary.json",
    },
    {
        "block_id": "block_4_external_mcp_surface",
        "summary_path": "artifacts/agent_modelica_external_agent_mcp_surface_v0_3_1/summary.json",
    },
    {
        "block_id": "block_5_track_c_live_matrix",
        "summary_path": "artifacts/agent_modelica_track_c_claim_gate_v0_3_1/summary.json",
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


def _block_status(block_id: str, payload: dict, *, external_surface: dict) -> str:
    if payload:
        status = str(payload.get("status") or "MISSING").strip().upper()
        if block_id == "block_4_external_mcp_surface" and status == "PASS":
            if str(payload.get("classification")) == "blocked_external_cli_mcp_tool_plane":
                return "BLOCKED_EXTERNAL"
        return status
    if block_id == "block_5_track_c_live_matrix":
        if str(external_surface.get("classification")) == "blocked_external_cli_mcp_tool_plane":
            return "DEFERRED_EXTERNAL"
    return "MISSING"


def build_v0_3_1_release_summary(*, out_dir: str = DEFAULT_OUT_DIR, blocks: list[dict] | None = None) -> dict:
    rows: list[dict] = []
    payloads: dict[str, dict] = {}
    for block in blocks or list(DEFAULT_BLOCKS):
        summary_path = str(block.get("summary_path") or "").strip()
        payloads[str(block.get("block_id") or "").strip()] = _load_json(summary_path)
    external_surface = payloads.get("block_4_external_mcp_surface") or {}

    internal_ok = True
    external_ready = bool(external_surface.get("live_comparison_ready"))
    for block in blocks or list(DEFAULT_BLOCKS):
        block_id = str(block.get("block_id") or "").strip()
        summary_path = str(block.get("summary_path") or "").strip()
        payload = payloads.get(block_id) or {}
        status = _block_status(block_id, payload, external_surface=external_surface)
        if block_id in {
            "block_0_v0_3_0_seal",
            "block_1_structural_singularity_trial",
            "block_2_layer4_holdout_pack",
            "block_3_harder_holdout_ablation",
        } and status != "PASS":
            internal_ok = False
        rows.append(
            {
                "block_id": block_id,
                "status": status,
                "summary_path": str(Path(summary_path).resolve()) if Path(summary_path).exists() else summary_path,
            }
        )

    completion_mode = "fail"
    overall_status = "FAIL"
    if internal_ok and str(external_surface.get("classification")) == "blocked_external_cli_mcp_tool_plane":
        completion_mode = "staged_internal_complete_external_blocked"
        overall_status = "PASS"
    elif internal_ok and external_ready and any(row.get("block_id") == "block_5_track_c_live_matrix" and row.get("status") == "PASS" for row in rows):
        completion_mode = "full_live_comparison_complete"
        overall_status = "PASS"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "completion_mode": completion_mode,
        "block_count": len(rows),
        "blocks": rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    (out_root / "summary.md").write_text(
        "\n".join(
            [
                "# GateForge v0.3.1 Release Summary",
                "",
                f"- status: `{payload.get('status')}`",
                f"- completion_mode: `{payload.get('completion_mode')}`",
                f"- block_count: `{payload.get('block_count')}`",
                "",
                *[f"- {row.get('block_id')}: `{row.get('status')}`" for row in rows],
            ]
        ),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize v0.3.1 block completion with staged external-block handling.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_1_release_summary(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "completion_mode": payload.get("completion_mode")}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
