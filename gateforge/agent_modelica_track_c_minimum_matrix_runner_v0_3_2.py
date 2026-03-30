from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_may_checkpoint_decision_v0_3_2 import build_may_checkpoint_decision
from .agent_modelica_track_c_matrix_v0_3_2 import (
    build_gateforge_bundle_from_results_paths,
    summarize_track_c_matrix,
)


SCHEMA_VERSION = "agent_modelica_track_c_minimum_matrix_runner_v0_3_2"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_minimum_matrix_runner_v0_3_2"
DEFAULT_TASKSET = "artifacts/agent_modelica_planner_sensitive_taskset_builder_v1/taskset_frozen.json"


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _provider_run_cmd(
    *,
    provider_name: str,
    taskset_path: str,
    out_dir: str,
    model_id: str,
    arm_id: str = "arm2_frozen_structured_prompt",
) -> list[str]:
    cmd = [
        sys.executable or "python3",
        "-m",
        "gateforge.agent_modelica_external_agent_live_runner_v0_3_1",
        "--provider",
        str(provider_name),
        "--arm-id",
        str(arm_id),
        "--taskset",
        str(taskset_path),
        "--out-dir",
        str(out_dir),
    ]
    if _norm(model_id):
        cmd += ["--model-id", str(model_id)]
    return cmd


def run_minimum_matrix(
    *,
    out_dir: str = DEFAULT_OUT_DIR,
    taskset_path: str = DEFAULT_TASKSET,
    gateforge_results_paths: list[str],
    claude_probe_summary_path: str,
    codex_probe_summary_path: str = "",
    slice_summary_path: str = "",
    repeat_count: int = 3,
    providers: list[str] | None = None,
    provider_model_ids: dict[str, str] | None = None,
    skip_existing: bool = True,
) -> dict:
    out_root = Path(out_dir)
    runs_root = out_root / "runs"
    providers = [str(x).strip().lower() for x in (providers or ["claude", "codex"]) if str(x).strip()]
    provider_model_ids = {str(k).strip().lower(): str(v) for k, v in (provider_model_ids or {}).items()}

    gateforge_bundle_path = out_root / "gateforge_authority_bundle.json"
    build_gateforge_bundle_from_results_paths(
        taskset_path=str(taskset_path),
        results_paths=[str(x) for x in gateforge_results_paths if str(x).strip()],
        out_path=str(gateforge_bundle_path),
    )

    bundle_paths = [str(gateforge_bundle_path)]
    run_records: list[dict] = []
    for provider_name in providers:
        for run_index in range(1, int(repeat_count) + 1):
            run_dir = runs_root / f"{provider_name}_run{run_index}"
            summary_path = run_dir / "summary.json"
            normalized_path = run_dir / "normalized_bundle.json"
            if bool(skip_existing) and summary_path.exists() and normalized_path.exists():
                run_records.append(
                    {
                        "provider_name": provider_name,
                        "run_index": run_index,
                        "out_dir": str(run_dir.resolve()),
                        "reused_existing": True,
                        "normalized_bundle_path": str(normalized_path.resolve()),
                    }
                )
                bundle_paths.append(str(normalized_path))
                continue

            cmd = _provider_run_cmd(
                provider_name=provider_name,
                taskset_path=str(taskset_path),
                out_dir=str(run_dir),
                model_id=provider_model_ids.get(provider_name, ""),
            )
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            run_record = {
                "provider_name": provider_name,
                "run_index": run_index,
                "out_dir": str(run_dir.resolve()),
                "reused_existing": False,
                "returncode": int(proc.returncode),
                "stdout_tail": str(proc.stdout or "")[-1000:],
                "stderr_tail": str(proc.stderr or "")[-1000:],
                "normalized_bundle_path": str(normalized_path.resolve()) if normalized_path.exists() else "",
            }
            run_records.append(run_record)
            if normalized_path.exists():
                bundle_paths.append(str(normalized_path))

    matrix_summary = summarize_track_c_matrix(bundle_paths=bundle_paths, out_dir=str(out_root / "matrix"))
    decision_summary = build_may_checkpoint_decision(
        matrix_summary_path=str(out_root / "matrix" / "summary.json"),
        claude_probe_summary_path=str(claude_probe_summary_path),
        codex_probe_summary_path=str(codex_probe_summary_path),
        slice_summary_path=str(slice_summary_path),
        out_dir=str(out_root / "decision"),
        min_repeated_runs=int(repeat_count),
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "taskset_path": str(Path(taskset_path).resolve()),
        "gateforge_bundle_path": str(gateforge_bundle_path.resolve()),
        "run_records": run_records,
        "matrix_summary_path": str((out_root / "matrix" / "summary.json").resolve()),
        "decision_summary_path": str((out_root / "decision" / "summary.json").resolve()),
        "classification": _norm(decision_summary.get("classification")),
    }
    _write_json(out_root / "summary.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the v0.3.2 minimum Track C repeated-run matrix.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--taskset", default=DEFAULT_TASKSET)
    parser.add_argument("--gateforge-results", action="append", default=[])
    parser.add_argument("--claude-probe-summary", required=True)
    parser.add_argument("--codex-probe-summary", default="")
    parser.add_argument("--slice-summary", default="")
    parser.add_argument("--repeat-count", type=int, default=3)
    parser.add_argument("--provider", action="append", default=[])
    parser.add_argument("--claude-model-id", default="")
    parser.add_argument("--codex-model-id", default="")
    parser.add_argument("--no-skip-existing", action="store_true")
    args = parser.parse_args()

    payload = run_minimum_matrix(
        out_dir=str(args.out_dir),
        taskset_path=str(args.taskset),
        gateforge_results_paths=[str(x) for x in (args.gateforge_results or []) if str(x).strip()],
        claude_probe_summary_path=str(args.claude_probe_summary),
        codex_probe_summary_path=str(args.codex_probe_summary),
        slice_summary_path=str(args.slice_summary),
        repeat_count=int(args.repeat_count),
        providers=[str(x) for x in (args.provider or []) if str(x).strip()] or ["claude", "codex"],
        provider_model_ids={
            "claude": str(args.claude_model_id),
            "codex": str(args.codex_model_id),
        },
        skip_existing=not bool(args.no_skip_existing),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
