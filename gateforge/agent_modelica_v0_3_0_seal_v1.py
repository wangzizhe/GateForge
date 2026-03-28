from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_0_seal_v1"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_0_seal_v1"
DEFAULT_REFERENCE_FILES = (
    {
        "artifact_id": "v0_3_0_release_summary",
        "path": "artifacts/agent_modelica_v0_3_0/summary.json",
        "kind": "summary",
    },
    {
        "artifact_id": "v0_3_0_layer4_hard_lane_taskset",
        "path": "artifacts/agent_modelica_layer4_hard_lane_v0_3_0/taskset_frozen.json",
        "kind": "taskset",
    },
    {
        "artifact_id": "v0_3_0_layer4_hard_lane_sidecar",
        "path": "artifacts/agent_modelica_layer4_hard_lane_v0_3_0/layer_metadata.json",
        "kind": "sidecar",
    },
    {
        "artifact_id": "v0_3_0_track_c_budget_calibration",
        "path": "artifacts/agent_modelica_track_c_pilot_v0_3_0/budget_calibration.json",
        "kind": "budget",
    },
    {
        "artifact_id": "v0_3_0_track_c_omc_mcp_contract",
        "path": "artifacts/agent_modelica_track_c_pilot_v0_3_0/omc_mcp_contract.json",
        "kind": "contract",
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


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_v0_3_0_seal(*, out_dir: str = DEFAULT_OUT_DIR, references: list[dict] | None = None) -> dict:
    rows: list[dict] = []
    missing: list[str] = []
    failing_summaries: list[str] = []

    for ref in references or list(DEFAULT_REFERENCE_FILES):
        artifact_id = str(ref.get("artifact_id") or "").strip()
        path = Path(str(ref.get("path") or ""))
        kind = str(ref.get("kind") or "artifact").strip()
        if not path.exists():
            missing.append(artifact_id or str(path))
            rows.append(
                {
                    "artifact_id": artifact_id,
                    "kind": kind,
                    "path": str(path),
                    "exists": False,
                    "sha256": "",
                    "status": "MISSING",
                }
            )
            continue
        payload = _load_json(path)
        status = str(payload.get("status") or "PASS").strip().upper() if payload else "PASS"
        if kind == "summary" and status != "PASS":
            failing_summaries.append(artifact_id or str(path))
        rows.append(
            {
                "artifact_id": artifact_id,
                "kind": kind,
                "path": str(path.resolve()),
                "exists": True,
                "sha256": _sha256_file(path),
                "status": status,
            }
        )

    budget_payload = _load_json("artifacts/agent_modelica_track_c_pilot_v0_3_0/budget_calibration.json")
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not missing and not failing_summaries else "FAIL",
        "reference_count": len(rows),
        "references": rows,
        "missing_artifacts": missing,
        "failing_summaries": failing_summaries,
        "track_c_budget_authority": {
            "path": str(Path("artifacts/agent_modelica_track_c_pilot_v0_3_0/budget_calibration.json").resolve())
            if Path("artifacts/agent_modelica_track_c_pilot_v0_3_0/budget_calibration.json").exists()
            else "artifacts/agent_modelica_track_c_pilot_v0_3_0/budget_calibration.json",
            "recommended_budget": budget_payload.get("recommended_budget") if isinstance(budget_payload, dict) else {},
            "sources_used": budget_payload.get("sources_used") if isinstance(budget_payload, dict) else [],
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", result)
    (out_root / "summary.md").write_text(
        "\n".join(
            [
                "# Agent Modelica v0.3.0 Seal v1",
                "",
                f"- status: `{result.get('status')}`",
                f"- reference_count: `{result.get('reference_count')}`",
                f"- missing_artifacts: `{','.join(result.get('missing_artifacts') or []) or 'none'}`",
                f"- failing_summaries: `{','.join(result.get('failing_summaries') or []) or 'none'}`",
            ]
        ),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze v0.3.0 reference artifacts as v0.3.1 baseline authority")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_0_seal(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "reference_count": int(payload.get("reference_count") or 0)}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
