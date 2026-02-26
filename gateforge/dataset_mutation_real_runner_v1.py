from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


def _extract_mutations(manifest: dict) -> list[dict]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _run_once(command: str, timeout_seconds: int, cwd: str | None, max_output_chars: int) -> tuple[dict, bool]:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            ["bash", "-lc", command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration = round(time.monotonic() - start, 4)
        row = {
            "timed_out": False,
            "exception": "",
            "return_code": int(proc.returncode),
            "duration_sec": duration,
            "stdout": _clip(proc.stdout or "", max_output_chars),
            "stderr": _clip(proc.stderr or "", max_output_chars),
        }
        return row, False
    except subprocess.TimeoutExpired as e:
        duration = round(time.monotonic() - start, 4)
        row = {
            "timed_out": True,
            "exception": "TimeoutExpired",
            "return_code": None,
            "duration_sec": duration,
            "stdout": _clip(str(e.stdout or ""), max_output_chars),
            "stderr": _clip(str(e.stderr or ""), max_output_chars),
        }
        return row, True
    except Exception as e:  # pragma: no cover - defensive
        duration = round(time.monotonic() - start, 4)
        row = {
            "timed_out": False,
            "exception": str(type(e).__name__),
            "return_code": None,
            "duration_sec": duration,
            "stdout": "",
            "stderr": _clip(str(e), max_output_chars),
        }
        return row, True


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Real Runner v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- executed_count: `{payload.get('executed_count')}`",
        f"- infra_error_count: `{payload.get('infra_error_count')}`",
        f"- timed_out_count: `{payload.get('timed_out_count')}`",
        f"- nonzero_exit_count: `{payload.get('nonzero_exit_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run validated mutation commands and collect raw execution observations")
    parser.add_argument("--validated-mutation-manifest", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--workdir", default=None)
    parser.add_argument("--max-output-chars", type=int, default=8000)
    parser.add_argument("--raw-observations-out", default="artifacts/dataset_mutation_real_runner_v1/raw_observations.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_real_runner_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.validated_mutation_manifest)
    mutations = _extract_mutations(manifest)

    reasons: list[str] = []
    if not manifest:
        reasons.append("validated_mutation_manifest_missing")
    if not mutations:
        reasons.append("validated_mutations_missing")

    observations: list[dict] = []
    infra_error_count = 0
    timed_out_count = 0
    executed_count = 0
    nonzero_exit_count = 0
    durations: list[float] = []

    for row in mutations:
        mutation_id = str(row.get("mutation_id") or "")
        command = str(row.get("repro_command") or "").strip()
        attempts: list[dict] = []
        max_attempts = max(1, int(args.max_retries) + 1)

        if not mutation_id:
            continue

        if not command:
            infra_error_count += 1
            observations.append(
                {
                    "mutation_id": mutation_id,
                    "target_model_id": str(row.get("target_model_id") or ""),
                    "target_scale": str(row.get("target_scale") or ""),
                    "repro_command": command,
                    "attempt_count": 0,
                    "attempts": [],
                    "final_return_code": None,
                    "execution_status": "INVALID_COMMAND",
                }
            )
            continue

        infra_error = False
        for _ in range(max_attempts):
            attempt, is_infra_error = _run_once(
                command,
                timeout_seconds=max(1, int(args.timeout_seconds)),
                cwd=args.workdir,
                max_output_chars=max(200, int(args.max_output_chars)),
            )
            attempts.append(attempt)

            if attempt.get("timed_out"):
                timed_out_count += 1
                infra_error = True
                continue

            if attempt.get("exception"):
                infra_error = True
                continue

            # Non-timeout execution completed; keep first completed attempt
            break

        final = attempts[-1] if attempts else {}
        final_rc = final.get("return_code")
        if isinstance(final_rc, int) and final_rc != 0:
            nonzero_exit_count += 1
        if isinstance(final.get("duration_sec"), float):
            durations.append(float(final.get("duration_sec")))

        if infra_error:
            infra_error_count += 1
            status = "INFRA_ERROR"
        else:
            status = "EXECUTED"
            executed_count += 1

        observations.append(
            {
                "mutation_id": mutation_id,
                "target_model_id": str(row.get("target_model_id") or ""),
                "target_scale": str(row.get("target_scale") or ""),
                "expected_failure_type": str(row.get("expected_failure_type") or ""),
                "repro_command": command,
                "attempt_count": len(attempts),
                "attempts": attempts,
                "final_return_code": final_rc,
                "execution_status": status,
            }
        )

    mean_duration = round(sum(durations) / len(durations), 4) if durations else 0.0

    status = "PASS"
    if "validated_mutation_manifest_missing" in reasons or "validated_mutations_missing" in reasons:
        status = "FAIL"
    elif infra_error_count > 0:
        status = "NEEDS_REVIEW"

    raw_payload = {
        "schema_version": "mutation_raw_observations_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "observations": observations,
    }
    _write_json(args.raw_observations_out, raw_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_mutations": len(mutations),
        "executed_count": executed_count,
        "infra_error_count": infra_error_count,
        "timed_out_count": timed_out_count,
        "nonzero_exit_count": nonzero_exit_count,
        "mean_duration_sec": mean_duration,
        "raw_observations_path": args.raw_observations_out,
        "reasons": sorted(set(reasons)),
        "sources": {"validated_mutation_manifest": args.validated_mutation_manifest},
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "executed_count": executed_count, "infra_error_count": infra_error_count}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
