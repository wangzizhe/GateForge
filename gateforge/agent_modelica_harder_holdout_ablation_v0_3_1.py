from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_harder_holdout_ablation_v0_3_1"
DEFAULT_PACK = "artifacts/agent_modelica_layer4_holdout_pack_v0_3_1/hardpack_frozen.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_harder_holdout_ablation_v0_3_1"
DEFAULT_EXPERIENCE_SOURCE = "artifacts/agent_modelica_planner_sensitive_eval_v1/experience_replay_plus_planner.json"
CONFIG_MATRIX = (
    {"config_label": "baseline", "experience_replay": "off", "planner_experience_injection": "off"},
    {"config_label": "replay_only", "experience_replay": "on", "planner_experience_injection": "off"},
    {"config_label": "planner_only", "experience_replay": "off", "planner_experience_injection": "on"},
    {"config_label": "replay_plus_planner", "experience_replay": "on", "planner_experience_injection": "on"},
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


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _norm(value: object) -> str:
    return str(value or "").strip()


def build_config_commands(
    *,
    pack_path: str,
    out_dir: str,
    planner_backend: str,
    max_rounds: int,
    timeout_sec: int,
    experience_source: str,
    planner_experience_max_tokens: int,
) -> list[dict]:
    rows: list[dict] = []
    for cfg in CONFIG_MATRIX:
        label = str(cfg["config_label"])
        cfg_dir = Path(out_dir) / label
        out_path = cfg_dir / "gf_results.json"
        cmd = [
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
            str(out_path),
        ]
        if str(experience_source or "").strip():
            cmd += ["--experience-source", str(experience_source)]
        rows.append(
            {
                "config_label": label,
                "experience_replay": str(cfg["experience_replay"]),
                "planner_experience_injection": str(cfg["planner_experience_injection"]),
                "results_path": str(out_path),
                "runner_cmd": cmd,
            }
        )
    return rows


def _summary_from_results(payload: dict) -> dict:
    rows = payload.get("results") if isinstance(payload.get("results"), list) else []
    valid_rows = [row for row in rows if isinstance(row, dict)]
    success_count = len([row for row in valid_rows if bool(row.get("success"))])
    planner_invoked_count = len([row for row in valid_rows if bool(row.get("planner_invoked"))])
    planner_decisive_count = len([row for row in valid_rows if bool(row.get("planner_decisive"))])
    replay_used_count = len([row for row in valid_rows if bool(row.get("replay_used"))])
    avg_rounds = _mean([float(row.get("rounds_used") or 0.0) for row in valid_rows])
    avg_elapsed_sec = _mean([float(row.get("elapsed_sec") or 0.0) for row in valid_rows])
    resolution_paths: dict[str, int] = {}
    dominant_stage_subtypes: dict[str, int] = {}
    for row in valid_rows:
        resolution_path = _norm(row.get("resolution_path") or "unresolved")
        resolution_paths[resolution_path] = int(resolution_paths.get(resolution_path) or 0) + 1
        dominant_stage = _norm(row.get("dominant_stage_subtype") or "stage_0_none")
        dominant_stage_subtypes[dominant_stage] = int(dominant_stage_subtypes.get(dominant_stage) or 0) + 1
    return {
        "task_count": len(valid_rows),
        "success_count": success_count,
        "success_rate_pct": _ratio(success_count, len(valid_rows)),
        "planner_invoked_count": planner_invoked_count,
        "planner_invoked_rate_pct": _ratio(planner_invoked_count, len(valid_rows)),
        "planner_decisive_count": planner_decisive_count,
        "planner_decisive_rate_pct": _ratio(planner_decisive_count, len(valid_rows)),
        "replay_used_count": replay_used_count,
        "replay_used_rate_pct": _ratio(replay_used_count, len(valid_rows)),
        "avg_rounds_used": avg_rounds,
        "avg_elapsed_sec": avg_elapsed_sec,
        "resolution_path_distribution": dict(sorted(resolution_paths.items())),
        "dominant_stage_subtype_distribution": dict(sorted(dominant_stage_subtypes.items())),
    }


def _activation_status(config_rows: list[dict]) -> dict:
    planner_rates = [
        float(((row.get("summary") or {}).get("planner_invoked_rate_pct") or 0.0))
        for row in config_rows
        if _norm(row.get("planner_experience_injection")) == "on"
    ]
    replay_rates = [
        float(((row.get("summary") or {}).get("replay_used_rate_pct") or 0.0))
        for row in config_rows
        if _norm(row.get("experience_replay")) == "on"
    ]
    max_planner_rate = max(planner_rates) if planner_rates else 0.0
    max_replay_rate = max(replay_rates) if replay_rates else 0.0
    inconclusive = max_planner_rate < 20.0 and max_replay_rate < 20.0
    return {
        "status": "inconclusive_low_activation" if inconclusive else "activation_observed",
        "max_planner_invoked_rate_pct": round(max_planner_rate, 2),
        "max_replay_used_rate_pct": round(max_replay_rate, 2),
    }


def _baseline_row(config_rows: list[dict]) -> dict:
    for row in config_rows:
        if _norm(row.get("config_label")) == "baseline":
            return row
    return {}


def _delta_rows(config_rows: list[dict]) -> list[dict]:
    baseline = _baseline_row(config_rows)
    baseline_summary = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
    baseline_success = float(baseline_summary.get("success_rate_pct") or 0.0)
    baseline_rounds = float(baseline_summary.get("avg_rounds_used") or 0.0)
    baseline_elapsed = float(baseline_summary.get("avg_elapsed_sec") or 0.0)
    rows: list[dict] = []
    for row in config_rows:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        rows.append(
            {
                "config_label": _norm(row.get("config_label")),
                "success_rate_delta_pct": round(float(summary.get("success_rate_pct") or 0.0) - baseline_success, 2),
                "avg_rounds_delta": round(float(summary.get("avg_rounds_used") or 0.0) - baseline_rounds, 2),
                "avg_elapsed_sec_delta": round(float(summary.get("avg_elapsed_sec") or 0.0) - baseline_elapsed, 2),
            }
        )
    return rows


def run_harder_holdout_ablation(
    *,
    pack_path: str = DEFAULT_PACK,
    out_dir: str = DEFAULT_OUT_DIR,
    planner_backend: str = "auto",
    max_rounds: int = 3,
    timeout_sec: int = 180,
    experience_source: str = DEFAULT_EXPERIENCE_SOURCE,
    planner_experience_max_tokens: int = 400,
    dry_run: bool = False,
) -> dict:
    rows = build_config_commands(
        pack_path=pack_path,
        out_dir=out_dir,
        planner_backend=planner_backend,
        max_rounds=max_rounds,
        timeout_sec=timeout_sec,
        experience_source=experience_source,
        planner_experience_max_tokens=planner_experience_max_tokens,
    )

    out_root = Path(out_dir)
    status = "PASS"
    config_rows: list[dict] = []
    for row in rows:
        entry = dict(row)
        if dry_run:
            entry["status"] = "PLANNED"
            config_rows.append(entry)
            continue
        if (_norm(row.get("experience_replay")) == "on" or _norm(row.get("planner_experience_injection")) == "on") and not str(experience_source or "").strip():
            entry["status"] = "FAIL"
            entry["reason"] = "experience_source_missing"
            config_rows.append(entry)
            status = "FAIL"
            break
        Path(entry["results_path"]).parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(entry["runner_cmd"], capture_output=True, text=True, check=False)
        entry["runner_exit_code"] = int(proc.returncode)
        entry["runner_stdout_tail"] = str(proc.stdout or "")[-500:]
        entry["runner_stderr_tail"] = str(proc.stderr or "")[-500:]
        if proc.returncode != 0:
            entry["status"] = "FAIL"
            entry["reason"] = "gf_runner_nonzero"
            config_rows.append(entry)
            status = "FAIL"
            break
        result_payload = _load_json(entry["results_path"])
        entry["summary"] = _summary_from_results(result_payload)
        entry["status"] = "PASS"
        config_rows.append(entry)

    activation = _activation_status(config_rows) if config_rows and not dry_run else {"status": "dry_run"}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status if not dry_run else "PASS",
        "dry_run": bool(dry_run),
        "pack_path": str(Path(pack_path).resolve()) if Path(pack_path).exists() else str(pack_path),
        "experience_source": str(Path(experience_source).resolve()) if str(experience_source).strip() and Path(experience_source).exists() else str(experience_source),
        "planner_backend": str(planner_backend),
        "max_rounds": int(max_rounds),
        "timeout_sec": int(timeout_sec),
        "configs": config_rows,
        "activation_summary": activation,
        "delta_vs_baseline": _delta_rows(config_rows) if config_rows and not dry_run else [],
        "ablation_conclusion": (
            "inconclusive_low_activation"
            if activation.get("status") == "inconclusive_low_activation"
            else ("configured" if dry_run else "signal_observed")
        ),
    }
    _write_json(out_root / "summary.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GateForge-only mini-ablation on the v0.3.1 harder Layer 4 holdout pack.")
    parser.add_argument("--pack", default=DEFAULT_PACK)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--planner-backend", choices=["auto", "rule", "gemini", "openai", "anthropic", "qwen", "deepseek", "minimax", "kimi", "glm"], default="auto")
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--experience-source", default=DEFAULT_EXPERIENCE_SOURCE)
    parser.add_argument("--planner-experience-max-tokens", type=int, default=400)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    payload = run_harder_holdout_ablation(
        pack_path=str(args.pack),
        out_dir=str(args.out_dir),
        planner_backend=str(args.planner_backend),
        max_rounds=int(args.max_rounds),
        timeout_sec=int(args.timeout_sec),
        experience_source=str(args.experience_source),
        planner_experience_max_tokens=int(args.planner_experience_max_tokens),
        dry_run=bool(args.dry_run),
    )
    print(json.dumps({"status": payload.get("status"), "ablation_conclusion": payload.get("ablation_conclusion")}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
