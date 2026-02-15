from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return int(proc.returncode), proc.stdout or "", proc.stderr or ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run repair pipeline: tasks -> pack -> batch")
    parser.add_argument("--source", required=True, help="Failing run/regression summary JSON path")
    parser.add_argument("--out-dir", default="artifacts/repair_orchestrate", help="Output directory")
    parser.add_argument("--planner-backend", default="rule", choices=["rule", "gemini", "openai"])
    parser.add_argument("--strategy-profile", default="default", help="repair_pack strategy profile")
    parser.add_argument("--policy-profile", default=None, help="Optional policy profile for generated cases")
    parser.add_argument("--baseline", default="auto", help="Baseline path for repair_batch")
    parser.add_argument("--continue-on-fail", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-cases", type=int, default=5, help="Maximum fix_plan tasks to convert")
    parser.add_argument("--pack-id", default="repair_orchestrate_pack_v0", help="Generated pack id")
    parser.add_argument("--out", default=None, help="Optional summary JSON path")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_out = str(out_dir / "tasks.json")
    tasks_md = str(out_dir / "tasks.md")
    pack_out = str(out_dir / "pack.json")
    batch_out = str(out_dir / "batch_summary.json")
    batch_md = str(out_dir / "batch_summary.md")
    summary_out = args.out or str(out_dir / "summary.json")

    tasks_cmd = [
        sys.executable,
        "-m",
        "gateforge.repair_tasks",
        "--source",
        args.source,
        "--out",
        tasks_out,
        "--report",
        tasks_md,
    ]
    if args.policy_profile:
        tasks_cmd.extend(["--policy-profile", args.policy_profile])
    tasks_code, tasks_stdout, tasks_stderr = _run_cmd(tasks_cmd)

    pack_cmd = [
        sys.executable,
        "-m",
        "gateforge.repair_pack",
        "--tasks-summary",
        tasks_out,
        "--pack-id",
        args.pack_id,
        "--planner-backend",
        args.planner_backend,
        "--strategy-profile",
        args.strategy_profile,
        "--max-cases",
        str(args.max_cases),
        "--out",
        pack_out,
    ]
    if args.policy_profile:
        pack_cmd.extend(["--policy-profile", args.policy_profile])
    pack_code, pack_stdout, pack_stderr = _run_cmd(pack_cmd) if tasks_code == 0 else (99, "", "tasks step failed")

    batch_cmd = [
        sys.executable,
        "-m",
        "gateforge.repair_batch",
        "--pack",
        pack_out,
        "--planner-backend",
        args.planner_backend,
        "--baseline",
        args.baseline,
        "--summary-out",
        batch_out,
        "--report-out",
        batch_md,
    ]
    if args.continue_on_fail:
        batch_cmd.append("--continue-on-fail")
    else:
        batch_cmd.append("--no-continue-on-fail")
    if args.policy_profile:
        batch_cmd.extend(["--policy-profile", args.policy_profile])
    batch_code, batch_stdout, batch_stderr = _run_cmd(batch_cmd) if pack_code == 0 else (99, "", "pack step failed")

    status = "PASS" if tasks_code == 0 and pack_code == 0 and batch_code == 0 else "FAIL"
    summary = {
        "status": status,
        "source": args.source,
        "planner_backend": args.planner_backend,
        "strategy_profile": args.strategy_profile,
        "policy_profile": args.policy_profile,
        "tasks_path": tasks_out,
        "pack_path": pack_out,
        "batch_summary_path": batch_out,
        "step_exit_codes": {
            "repair_tasks": tasks_code,
            "repair_pack": pack_code,
            "repair_batch": batch_code,
        },
        "step_stderr_tail": {
            "repair_tasks": tasks_stderr[-400:],
            "repair_pack": pack_stderr[-400:],
            "repair_batch": batch_stderr[-400:],
        },
    }
    _write_json(summary_out, summary)
    print(json.dumps({"status": status, "summary": summary_out}))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
