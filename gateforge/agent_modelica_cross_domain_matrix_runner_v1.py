from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_cross_domain_matrix_runner_v1"
CONFIG_MATRIX = (
    {"label": "baseline", "experience_replay": "off", "planner_experience_injection": "off"},
    {"label": "replay_only", "experience_replay": "on", "planner_experience_injection": "off"},
    {"label": "planner_only", "experience_replay": "off", "planner_experience_injection": "on"},
    {"label": "replay_plus_planner", "experience_replay": "on", "planner_experience_injection": "on"},
)


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str | Path) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str | Path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent Modelica Cross-Domain Matrix Runner v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- track_id: `{payload.get('track_id')}`",
        f"- pack_path: `{payload.get('pack_path')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        "",
        "## Configs",
        "",
    ]
    for row in payload.get("configs") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"- `{row.get('config_label')}`: `{row.get('status')}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def build_config_commands(
    *,
    pack_path: str,
    out_dir: str,
    planner_backend: str,
    comparison_backend: str,
    max_rounds: int,
    timeout_sec: int,
    comparison_timeout_sec: int,
    experience_source: str,
    planner_experience_max_tokens: int,
) -> list[dict]:
    root = Path(out_dir)
    rows: list[dict] = []
    for cfg in CONFIG_MATRIX:
        label = str(cfg["label"])
        cfg_dir = root / label
        gf_results = cfg_dir / "gf_results.json"
        comparison_summary = cfg_dir / "comparison.json"
        runner_cmd = [
            sys.executable,
            "-m",
            "gateforge.agent_modelica_gf_hardpack_runner_v1",
            "--pack",
            str(pack_path),
            "--planner-backend",
            str(planner_backend),
            "--max-rounds",
            str(int(max_rounds)),
            "--timeout-sec",
            str(int(timeout_sec)),
            "--experience-replay",
            str(cfg["experience_replay"]),
            "--planner-experience-injection",
            str(cfg["planner_experience_injection"]),
            "--planner-experience-max-tokens",
            str(int(planner_experience_max_tokens)),
            "--out",
            str(gf_results),
        ]
        if str(experience_source or "").strip():
            runner_cmd += ["--experience-source", str(experience_source)]
        comparison_cmd = [
            sys.executable,
            "-m",
            "gateforge.agent_modelica_generalization_benchmark_v1",
            "--pack",
            str(pack_path),
            "--backend",
            str(comparison_backend),
            "--gateforge-results",
            str(gf_results),
            "--timeout-sec",
            str(int(comparison_timeout_sec)),
            "--out",
            str(comparison_summary),
        ]
        rows.append(
            {
                "config_label": label,
                "experience_replay": str(cfg["experience_replay"]),
                "planner_experience_injection": str(cfg["planner_experience_injection"]),
                "gateforge_results": str(gf_results),
                "comparison_summary": str(comparison_summary),
                "runner_cmd": runner_cmd,
                "comparison_cmd": comparison_cmd,
            }
        )
    return rows


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return int(proc.returncode), str(proc.stdout or ""), str(proc.stderr or "")


def run_matrix(
    *,
    track_id: str,
    library: str,
    pack_path: str,
    out_dir: str,
    planner_backend: str = "gemini",
    comparison_backend: str = "gemini",
    max_rounds: int = 8,
    timeout_sec: int = 300,
    comparison_timeout_sec: int = 120,
    experience_source: str = "",
    planner_experience_max_tokens: int = 400,
    dry_run: bool = False,
) -> dict:
    rows = build_config_commands(
        pack_path=pack_path,
        out_dir=out_dir,
        planner_backend=planner_backend,
        comparison_backend=comparison_backend,
        max_rounds=max_rounds,
        timeout_sec=timeout_sec,
        comparison_timeout_sec=comparison_timeout_sec,
        experience_source=experience_source,
        planner_experience_max_tokens=planner_experience_max_tokens,
    )

    status = "PASS"
    config_rows: list[dict] = []
    for row in rows:
        Path(row["gateforge_results"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["comparison_summary"]).parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "config_label": row["config_label"],
            "experience_replay": row["experience_replay"],
            "planner_experience_injection": row["planner_experience_injection"],
            "gateforge_results": row["gateforge_results"],
            "comparison_summary": row["comparison_summary"],
            "runner_cmd": row["runner_cmd"],
            "comparison_cmd": row["comparison_cmd"],
            "status": "PLANNED" if dry_run else "PENDING",
        }
        if dry_run:
            config_rows.append(entry)
            continue
        if row["experience_replay"] == "on" or row["planner_experience_injection"] == "on":
            if not str(experience_source or "").strip():
                entry["status"] = "FAIL"
                entry["reason"] = "experience_source_missing"
                config_rows.append(entry)
                status = "FAIL"
                break
        rc1, stdout1, stderr1 = _run(row["runner_cmd"])
        entry["runner_exit_code"] = rc1
        entry["runner_stdout_tail"] = stdout1[-500:]
        entry["runner_stderr_tail"] = stderr1[-500:]
        if rc1 != 0:
            entry["status"] = "FAIL"
            entry["reason"] = "gf_runner_nonzero"
            config_rows.append(entry)
            status = "FAIL"
            break
        rc2, stdout2, stderr2 = _run(row["comparison_cmd"])
        entry["comparison_exit_code"] = rc2
        entry["comparison_stdout_tail"] = stdout2[-500:]
        entry["comparison_stderr_tail"] = stderr2[-500:]
        entry["status"] = "PASS" if rc2 == 0 else "FAIL"
        if rc2 != 0:
            entry["reason"] = "comparison_nonzero"
            status = "FAIL"
            config_rows.append(entry)
            break
        config_rows.append(entry)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "track_id": str(track_id or "").strip(),
        "library": str(library or "").strip(),
        "pack_path": str(pack_path),
        "out_dir": str(out_dir),
        "planner_backend": str(planner_backend),
        "comparison_backend": str(comparison_backend),
        "experience_source": str(experience_source or ""),
        "planner_experience_max_tokens": int(planner_experience_max_tokens),
        "dry_run": bool(dry_run),
        "configs": config_rows,
    }
    out_path = Path(out_dir) / "matrix_summary.json"
    _write_json(out_path, summary)
    _write_markdown(_default_md_path(out_path), summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a 4-way cross-domain benchmark matrix for a single track")
    parser.add_argument("--track-id", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--pack", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--planner-backend", default="gemini")
    parser.add_argument("--comparison-backend", default="gemini")
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--timeout-sec", type=int, default=300)
    parser.add_argument("--comparison-timeout-sec", type=int, default=120)
    parser.add_argument("--experience-source", default="")
    parser.add_argument("--planner-experience-max-tokens", type=int, default=400)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = run_matrix(
        track_id=args.track_id,
        library=args.library,
        pack_path=args.pack,
        out_dir=args.out_dir,
        planner_backend=args.planner_backend,
        comparison_backend=args.comparison_backend,
        max_rounds=args.max_rounds,
        timeout_sec=args.timeout_sec,
        comparison_timeout_sec=args.comparison_timeout_sec,
        experience_source=args.experience_source,
        planner_experience_max_tokens=args.planner_experience_max_tokens,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps({"status": summary.get("status"), "config_count": len(summary.get("configs") or []), "dry_run": summary.get("dry_run")}))
    if str(summary.get("status") or "") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
