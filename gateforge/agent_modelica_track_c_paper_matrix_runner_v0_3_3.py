from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_track_c_matrix_v0_3_2 import build_gateforge_bundle_from_results_paths
from .agent_modelica_track_c_paper_matrix_v0_3_3 import summarize_paper_matrix


SCHEMA_VERSION = "agent_modelica_track_c_paper_matrix_runner_v0_3_3"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_paper_matrix_runner_v0_3_3"
DEFAULT_TASKSET = "artifacts/agent_modelica_track_c_primary_slice_v0_3_3_w15a_w15b/taskset_frozen.json"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def run_paper_matrix(
    *,
    taskset_path: str = DEFAULT_TASKSET,
    gateforge_results_paths: list[str],
    out_dir: str = DEFAULT_OUT_DIR,
    primary_provider: str = "",
    secondary_provider: str = "",
    primary_repeat: int = 3,
    secondary_repeat: int = 1,
    primary_model_id: str = "",
    secondary_model_id: str = "",
    skip_existing: bool = True,
) -> dict:
    out_root = Path(out_dir)
    runs_root = out_root / "runs"
    primary_provider = _norm(primary_provider).lower()
    secondary_provider = _norm(secondary_provider).lower()
    if not primary_provider:
        raise ValueError("primary_provider_required_for_track_c_paper_matrix")
    primary_repeat = int(primary_repeat)
    secondary_repeat = int(secondary_repeat)
    primary_model_id = _norm(primary_model_id)
    secondary_model_id = _norm(secondary_model_id)

    gateforge_bundle_path = out_root / "gateforge_authority_bundle.json"
    build_gateforge_bundle_from_results_paths(
        taskset_path=str(taskset_path),
        results_paths=[str(x) for x in gateforge_results_paths if _norm(x)],
        out_path=str(gateforge_bundle_path),
        model_id="gateforge-v0.3.3/authority",
    )

    bundle_paths = [str(gateforge_bundle_path.resolve())]
    run_records: list[dict] = []
    provider_repeats = {
        primary_provider: max(0, int(primary_repeat)),
        secondary_provider: max(0, int(secondary_repeat)),
    }
    provider_models = {
        primary_provider: str(primary_model_id),
        secondary_provider: str(secondary_model_id),
    }

    for provider_name, repeat_count in provider_repeats.items():
        for run_index in range(1, repeat_count + 1):
            run_dir = runs_root / f"{provider_name}_run{run_index}"
            normalized_path = run_dir / "normalized_bundle.json"
            summary_path = run_dir / "summary.json"
            if skip_existing and normalized_path.exists() and summary_path.exists():
                run_records.append(
                    {
                        "provider_name": provider_name,
                        "run_index": run_index,
                        "out_dir": str(run_dir.resolve()),
                        "reused_existing": True,
                        "returncode": 0,
                        "normalized_bundle_path": str(normalized_path.resolve()),
                    }
                )
                bundle_paths.append(str(normalized_path.resolve()))
                continue

            cmd = _provider_run_cmd(
                provider_name=provider_name,
                taskset_path=str(taskset_path),
                out_dir=str(run_dir),
                model_id=provider_models.get(provider_name, ""),
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
                bundle_paths.append(str(normalized_path.resolve()))

    paper_matrix = summarize_paper_matrix(
        bundle_paths=bundle_paths,
        out_dir=str(out_root / "paper_matrix"),
        primary_provider=primary_provider,
        primary_min_clean_runs=max(1, int(primary_repeat)) if int(primary_repeat) > 0 else 1,
        supplementary_min_clean_runs=max(1, int(secondary_repeat)) if int(secondary_repeat) > 0 else 1,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "taskset_path": str(Path(taskset_path).resolve()),
        "gateforge_bundle_path": str(gateforge_bundle_path.resolve()),
        "paper_matrix_summary_path": str((out_root / "paper_matrix" / "summary.json").resolve()),
        "run_records": run_records,
        "provider_repeats": provider_repeats,
        "provider_rows": paper_matrix.get("provider_rows") if isinstance(paper_matrix.get("provider_rows"), list) else [],
    }
    _write_json(out_root / "summary.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the v0.3.3 Track C paper-matrix comparative runner.")
    parser.add_argument("--taskset", default=DEFAULT_TASKSET)
    parser.add_argument("--gateforge-results", action="append", default=[])
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--primary-provider", default="")
    parser.add_argument("--secondary-provider", default="")
    parser.add_argument("--primary-repeat", type=int, default=3)
    parser.add_argument("--secondary-repeat", type=int, default=1)
    parser.add_argument("--primary-model-id", default="")
    parser.add_argument("--secondary-model-id", default="")
    parser.add_argument("--no-skip-existing", action="store_true")
    args = parser.parse_args()
    payload = run_paper_matrix(
        taskset_path=str(args.taskset),
        gateforge_results_paths=[str(x) for x in (args.gateforge_results or []) if _norm(x)],
        out_dir=str(args.out_dir),
        primary_provider=str(args.primary_provider),
        secondary_provider=str(args.secondary_provider),
        primary_repeat=int(args.primary_repeat),
        secondary_repeat=int(args.secondary_repeat),
        primary_model_id=str(args.primary_model_id),
        secondary_model_id=str(args.secondary_model_id),
        skip_existing=not bool(args.no_skip_existing),
    )
    print(json.dumps({"status": payload.get("status"), "provider_rows": len(payload.get("provider_rows") or [])}))


if __name__ == "__main__":
    main()
