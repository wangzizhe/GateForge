from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "substrate_manifest": REPO_ROOT / "artifacts" / "substrate_manifest_v0_25_3" / "summary.json",
    "golden_smoke_pack": REPO_ROOT / "artifacts" / "golden_smoke_pack_v0_24_4" / "summary.json",
    "replay_harness": REPO_ROOT / "artifacts" / "replay_harness_v0_24_5" / "summary.json",
    "boundary_audit": REPO_ROOT / "artifacts" / "public_private_boundary_audit_v0_25_4" / "summary.json",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "substrate_regression_gates_v0_25_5"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def evaluate_gate(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {"gate": name, "status": "FAIL", "reason": "missing_input"}
    if payload.get("status") != "PASS":
        return {"gate": name, "status": "FAIL", "reason": "non_pass_status"}
    if name == "substrate_manifest" and int(payload.get("validation_error_count") or 0) != 0:
        return {"gate": name, "status": "FAIL", "reason": "manifest_validation_errors"}
    if name == "golden_smoke_pack" and int(payload.get("validation_error_count") or 0) != 0:
        return {"gate": name, "status": "FAIL", "reason": "smoke_validation_errors"}
    if name == "replay_harness" and (
        int(payload.get("candidate_diff_count") or 0) != 0 or int(payload.get("family_diff_count") or 0) != 0
    ):
        return {"gate": name, "status": "FAIL", "reason": "replay_diff_nonzero"}
    if name == "boundary_audit" and int(payload.get("finding_count") or 0) != 0:
        return {"gate": name, "status": "FAIL", "reason": "boundary_findings"}
    return {"gate": name, "status": "PASS", "reason": "ok"}


def build_substrate_regression_gates(
    *,
    input_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    paths = input_paths or DEFAULT_INPUTS
    loaded = {name: load_json(path) for name, path in paths.items()}
    gate_rows = [evaluate_gate(name, payload) for name, payload in loaded.items()]
    failed = [row for row in gate_rows if row["status"] != "PASS"]
    status = "PASS" if gate_rows and not failed else "REVIEW"
    summary = {
        "version": "v0.25.5",
        "status": status,
        "analysis_scope": "substrate_regression_gates",
        "gate_count": len(gate_rows),
        "failed_gate_count": len(failed),
        "gate_statuses": {row["gate"]: row["status"] for row in gate_rows},
        "ci_safe_gate": "golden_smoke_pack",
        "full_local_gate": "substrate_manifest_plus_replay_plus_boundary",
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "regression_gate_is_harness_health_not_llm_gain": True,
        },
        "conclusion": (
            "substrate_regression_gates_ready_for_v0_25_synthesis"
            if status == "PASS"
            else "substrate_regression_gates_need_review"
        ),
    }
    write_outputs(out_dir=out_dir, gate_rows=gate_rows, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, gate_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "gate_results.jsonl").open("w", encoding="utf-8") as fh:
        for row in gate_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
