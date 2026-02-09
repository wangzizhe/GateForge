from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def run_pipeline(backend: str = "mock", out_path: str = "artifacts/evidence.json") -> dict:
    started = time.time()
    result = _run_backend(backend)
    duration = time.time() - started

    evidence = {
        "schema_version": "0.1.0",
        "run_id": f"run-{int(started)}",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": backend,
        "status": result["status"],
        "failure_type": result["failure_type"],
        "metrics": {
            "runtime_seconds": round(duration, 4),
            "events": result["events"],
        },
        "artifacts": {
            "log_excerpt": result["log_excerpt"],
        },
        "gate": gate_decision(result["status"], result["failure_type"]),
    }

    validate_evidence(evidence)
    _write_json(out_path, evidence)
    return evidence


def _run_backend(backend: str) -> dict:
    if backend == "mock":
        return {
            "status": "success",
            "failure_type": "none",
            "events": 12,
            "log_excerpt": "mock simulation completed",
        }
    if backend == "openmodelica":
        return _run_openmodelica_probe()
    raise ValueError(f"Unsupported backend: {backend}")


def _run_openmodelica_probe() -> dict:
    try:
        proc = subprocess.run(
            ["omc", "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {
            "status": "failed",
            "failure_type": "tool_missing",
            "events": 0,
            "log_excerpt": "omc not found or timed out",
        }

    if proc.returncode != 0:
        return {
            "status": "failed",
            "failure_type": "compile_error",
            "events": 0,
            "log_excerpt": (proc.stderr or proc.stdout).strip()[:200],
        }

    return {
        "status": "success",
        "failure_type": "none",
        "events": 1,
        "log_excerpt": proc.stdout.strip()[:200],
    }


def gate_decision(status: str, failure_type: str) -> str:
    if status == "success":
        return "PASS"
    if failure_type == "tool_missing":
        return "NEEDS_REVIEW"
    return "FAIL"


def validate_evidence(evidence: dict) -> None:
    required_top = {
        "schema_version",
        "run_id",
        "timestamp_utc",
        "backend",
        "status",
        "failure_type",
        "metrics",
        "artifacts",
        "gate",
    }
    missing = required_top - set(evidence.keys())
    if missing:
        raise ValueError(f"Missing required evidence keys: {sorted(missing)}")

    if evidence["backend"] not in {"mock", "openmodelica"}:
        raise ValueError("backend must be mock/openmodelica")
    if evidence["status"] not in {"success", "failed"}:
        raise ValueError("status must be success/failed")
    if evidence["gate"] not in {"PASS", "FAIL", "NEEDS_REVIEW"}:
        raise ValueError("gate must be PASS/FAIL/NEEDS_REVIEW")

    metrics = evidence["metrics"]
    artifacts = evidence["artifacts"]
    if not isinstance(metrics.get("runtime_seconds"), (int, float)) or metrics["runtime_seconds"] < 0:
        raise ValueError("metrics.runtime_seconds must be non-negative number")
    if not isinstance(metrics.get("events"), int) or metrics["events"] < 0:
        raise ValueError("metrics.events must be non-negative integer")
    if not isinstance(artifacts.get("log_excerpt"), str):
        raise ValueError("artifacts.log_excerpt must be a string")


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
