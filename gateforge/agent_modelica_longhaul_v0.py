from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_longhaul_v0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _write_markdown(path: Path, payload: dict) -> None:
    lines = [
        "# Agent Modelica Longhaul v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- stop_reason: `{payload.get('stop_reason')}`",
        f"- segments_total: `{payload.get('segments_total')}`",
        f"- segments_completed: `{payload.get('segments_completed')}`",
        f"- segments_failed: `{payload.get('segments_failed')}`",
        f"- elapsed_runtime_sec: `{payload.get('elapsed_runtime_sec')}`",
        f"- target_runtime_sec: `{payload.get('target_runtime_sec')}`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _run_segment_attempt(
    *,
    command: str,
    cwd: Path,
    timeout_sec: int,
    env: dict[str, str],
    log_path: Path,
) -> dict:
    start = time.monotonic()
    started_at = _utc_now()
    timed_out = False
    return_code = 0
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=max(1, int(timeout_sec)),
        )
        return_code = int(proc.returncode)
        stdout = str(proc.stdout or "")
        stderr = str(proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        return_code = 124
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
    elapsed = round(time.monotonic() - start, 3)
    ended_at = _utc_now()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                f"[started_at] {started_at}",
                f"[ended_at] {ended_at}",
                f"[elapsed_sec] {elapsed}",
                f"[return_code] {return_code}",
                f"[timed_out] {timed_out}",
                "",
                "[stdout]",
                stdout,
                "",
                "[stderr]",
                stderr,
            ]
        ),
        encoding="utf-8",
    )
    return {
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "elapsed_sec": elapsed,
        "return_code": return_code,
        "timed_out": timed_out,
        "log_path": str(log_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a command repeatedly for multi-hour longhaul execution")
    parser.add_argument("--command", required=True)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_longhaul_v0")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--total-minutes", type=float, default=240.0)
    parser.add_argument("--segment-timeout-sec", type=int, default=1200)
    parser.add_argument("--max-segments", type=int, default=0)
    parser.add_argument("--retry-per-segment", type=int, default=0)
    parser.add_argument("--continue-on-fail", type=int, default=1)
    parser.add_argument("--sleep-between-sec", type=float, default=2.0)
    parser.add_argument("--resume", type=int, default=1)
    parser.add_argument("--summary-out", default="")
    parser.add_argument("--report-out", default="")
    parser.add_argument("--state-out", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    cwd = Path(args.cwd).resolve()
    total_target_sec = max(1.0, float(args.total_minutes) * 60.0)
    max_segments = max(0, int(args.max_segments))
    retry_per_segment = max(0, int(args.retry_per_segment))
    continue_on_fail = int(args.continue_on_fail) == 1
    sleep_between_sec = max(0.0, float(args.sleep_between_sec))
    resume = int(args.resume) == 1
    segment_timeout_sec = max(1, int(args.segment_timeout_sec))

    out_dir.mkdir(parents=True, exist_ok=True)
    segments_dir = out_dir / "segments"
    runs_dir = out_dir / "runs"
    segments_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.state_out).resolve() if str(args.state_out).strip() else (out_dir / "state.json")
    segments_jsonl = out_dir / "segments.jsonl"
    summary_path = Path(args.summary_out).resolve() if str(args.summary_out).strip() else (out_dir / "summary.json")
    report_path = Path(args.report_out).resolve() if str(args.report_out).strip() else (out_dir / "summary.md")

    state = _load_json(state_path) if resume else {}
    if not state:
        state = {
            "schema_version": SCHEMA_VERSION,
            "created_at_utc": _utc_now(),
            "command": str(args.command),
            "cwd": str(cwd),
            "target_runtime_sec": round(total_target_sec, 3),
            "segment_timeout_sec": segment_timeout_sec,
            "max_segments": max_segments,
            "retry_per_segment": retry_per_segment,
            "continue_on_fail": continue_on_fail,
            "sleep_between_sec": sleep_between_sec,
            "segments_total": 0,
            "segments_completed": 0,
            "segments_failed": 0,
            "next_segment_index": 1,
            "elapsed_runtime_sec": 0.0,
            "status": "RUNNING",
            "stop_reason": "",
            "last_updated_at_utc": _utc_now(),
        }

    stop_reason = ""
    status = "PASS"

    while True:
        elapsed_runtime_sec = float(state.get("elapsed_runtime_sec") or 0.0)
        next_segment_index = int(state.get("next_segment_index") or 1)
        segments_total = int(state.get("segments_total") or 0)
        segments_failed = int(state.get("segments_failed") or 0)

        if elapsed_runtime_sec >= total_target_sec:
            stop_reason = "target_runtime_reached"
            break
        if max_segments > 0 and segments_total >= max_segments:
            stop_reason = "max_segments_reached"
            break

        attempts = []
        segment_ok = False
        segment_run_dir = runs_dir / f"segment_{next_segment_index:04d}"
        segment_run_dir.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, retry_per_segment + 2):
            segment_env = dict(os.environ)
            segment_env["GATEFORGE_AGENT_LONGHAUL_SEGMENT_INDEX"] = str(next_segment_index)
            segment_env["GATEFORGE_AGENT_LONGHAUL_SEGMENT_ATTEMPT"] = str(attempt)
            segment_env["GATEFORGE_AGENT_LONGHAUL_SEGMENT_OUT_DIR"] = str(segment_run_dir)
            log_path = segments_dir / f"segment_{next_segment_index:04d}_attempt_{attempt}.log"
            attempt_row = _run_segment_attempt(
                command=str(args.command),
                cwd=cwd,
                timeout_sec=segment_timeout_sec,
                env=segment_env,
                log_path=log_path,
            )
            attempts.append(attempt_row)
            state["elapsed_runtime_sec"] = round(
                float(state.get("elapsed_runtime_sec") or 0.0) + float(attempt_row.get("elapsed_sec") or 0.0),
                3,
            )
            if int(attempt_row.get("return_code") or 0) == 0:
                segment_ok = True
                break

        segment_row = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": _utc_now(),
            "segment_index": next_segment_index,
            "status": "PASS" if segment_ok else "FAIL",
            "attempt_count": len(attempts),
            "attempts": attempts,
            "segment_out_dir": str(segment_run_dir),
        }
        _append_jsonl(segments_jsonl, segment_row)

        state["segments_total"] = int(state.get("segments_total") or 0) + 1
        if segment_ok:
            state["segments_completed"] = int(state.get("segments_completed") or 0) + 1
        else:
            state["segments_failed"] = int(state.get("segments_failed") or 0) + 1
        state["next_segment_index"] = next_segment_index + 1
        state["last_updated_at_utc"] = _utc_now()
        _write_json(state_path, state)

        if not segment_ok and not continue_on_fail:
            stop_reason = "segment_failed"
            status = "FAIL"
            break
        if not segment_ok:
            segments_failed += 1
        if sleep_between_sec > 0:
            time.sleep(sleep_between_sec)

    if not stop_reason:
        stop_reason = "completed"
    if status != "FAIL":
        if int(state.get("segments_completed") or 0) <= 0:
            status = "FAIL"
            stop_reason = "no_successful_segments"
        elif int(state.get("segments_failed") or 0) > 0:
            status = "NEEDS_REVIEW" if continue_on_fail else "FAIL"
        else:
            status = "PASS"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "status": status,
        "stop_reason": stop_reason,
        "command": str(args.command),
        "cwd": str(cwd),
        "target_runtime_sec": round(total_target_sec, 3),
        "elapsed_runtime_sec": round(float(state.get("elapsed_runtime_sec") or 0.0), 3),
        "segment_timeout_sec": segment_timeout_sec,
        "max_segments": max_segments,
        "retry_per_segment": retry_per_segment,
        "continue_on_fail": continue_on_fail,
        "sleep_between_sec": sleep_between_sec,
        "segments_total": int(state.get("segments_total") or 0),
        "segments_completed": int(state.get("segments_completed") or 0),
        "segments_failed": int(state.get("segments_failed") or 0),
        "next_segment_index": int(state.get("next_segment_index") or 1),
        "paths": {
            "state": str(state_path),
            "segments_jsonl": str(segments_jsonl),
            "segments_dir": str(segments_dir),
            "runs_dir": str(runs_dir),
        },
    }
    state["status"] = status
    state["stop_reason"] = stop_reason
    state["last_updated_at_utc"] = _utc_now()
    _write_json(state_path, state)
    _write_json(summary_path, summary)
    _write_markdown(report_path, summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "stop_reason": summary.get("stop_reason"),
                "segments_total": summary.get("segments_total"),
                "segments_completed": summary.get("segments_completed"),
                "segments_failed": summary.get("segments_failed"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
