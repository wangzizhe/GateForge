from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


DEFAULT_OM_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
OM_DOCKER_IMAGE_ENV = "GATEFORGE_OM_IMAGE"
OM_SCRIPT_ENV = "GATEFORGE_OM_SCRIPT"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OM_SCRIPT = "examples/openmodelica/minimal_probe.mos"


class Runner(Protocol):
    """Execution backend contract. Future FMU backend should implement this."""

    def run(self) -> dict:
        ...


class MockRunner:
    def __init__(self, script_path: str | None = None):
        self.script_path = script_path

    def run(self) -> dict:
        return {
            "status": "success",
            "failure_type": "none",
            "events": 12,
            "log_excerpt": "mock simulation completed",
            "model_script": self.script_path,
            "exit_code": 0,
            "check_ok": True,
            "simulate_ok": True,
        }


class OpenModelicaProbeRunner:
    def run(self) -> dict:
        return _run_openmodelica_probe()


class OpenModelicaDockerRunner:
    def __init__(self, script_path: str | None = None):
        self.script_path = script_path

    def run(self) -> dict:
        return _run_openmodelica_docker_probe(script_path=self.script_path)


def run_pipeline(
    backend: str = "mock",
    out_path: str = "artifacts/evidence.json",
    report_path: str | None = None,
    script_path: str | None = None,
) -> dict:
    # Single entry point: execute backend, normalize outputs, emit evidence.
    started = time.time()
    result = _run_backend(backend, script_path=script_path)
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
        "model_script": result["model_script"],
        "exit_code": result["exit_code"],
        "check_ok": result["check_ok"],
        "simulate_ok": result["simulate_ok"],
        "gate": gate_decision(result["status"], result["failure_type"]),
    }

    validate_evidence(evidence)
    _write_json(out_path, evidence)
    _write_markdown_report(_resolve_report_path(out_path, report_path), evidence)
    return evidence


def _run_backend(backend: str, script_path: str | None = None) -> dict:
    runner = _get_runner(backend, script_path=script_path)
    return runner.run()


def _get_runner(backend: str, script_path: str | None = None) -> Runner:
    if backend == "mock":
        return MockRunner(script_path=script_path)
    if backend == "openmodelica":
        return OpenModelicaProbeRunner()
    if backend == "openmodelica_docker":
        return OpenModelicaDockerRunner(script_path=script_path)
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
            "model_script": None,
            "exit_code": -1,
            "check_ok": False,
            "simulate_ok": False,
        }

    if proc.returncode != 0:
        return {
            "status": "failed",
            "failure_type": "compile_error",
            "events": 0,
            "log_excerpt": (proc.stderr or proc.stdout).strip()[:200],
            "model_script": None,
            "exit_code": proc.returncode,
            "check_ok": False,
            "simulate_ok": False,
        }

    return {
        "status": "success",
        "failure_type": "none",
        "events": 1,
        "log_excerpt": proc.stdout.strip()[:200],
        "model_script": None,
        "exit_code": proc.returncode,
        "check_ok": False,
        "simulate_ok": False,
    }


def _run_openmodelica_docker_probe(
    image: str = DEFAULT_OM_DOCKER_IMAGE,
    script_path: str | None = None,
) -> dict:
    selected_image = os.getenv(OM_DOCKER_IMAGE_ENV, image)
    script_rel = script_path or os.getenv(OM_SCRIPT_ENV, DEFAULT_OM_SCRIPT)
    script_abs = PROJECT_ROOT / script_rel
    if not script_abs.exists():
        return {
            "status": "failed",
            "failure_type": "config_error",
            "events": 0,
            "log_excerpt": f"missing script: {script_rel}",
            "model_script": script_rel,
            "exit_code": -1,
            "check_ok": False,
            "simulate_ok": False,
        }

    # Run inside an ephemeral workspace so OMC artifacts never pollute the repo.
    with tempfile.TemporaryDirectory(prefix="gateforge-om-") as tmpdir:
        tmp_root = Path(tmpdir)
        src_dir = PROJECT_ROOT / "examples" / "openmodelica"
        dst_dir = tmp_root / "examples" / "openmodelica"
        dst_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_dir, dst_dir)

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{tmp_root}:/workspace",
            "-w",
            "/workspace",
            selected_image,
            "omc",
            script_rel,
        ]
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=40,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {
                "status": "failed",
                "failure_type": "tool_missing",
                "events": 0,
                "log_excerpt": "docker not found or docker probe timed out",
                "model_script": script_rel,
                "exit_code": -1,
                "check_ok": False,
                "simulate_ok": False,
            }

        # Keep parsing logic backend-agnostic by extracting booleans from raw logs.
        merged_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        check_ok, simulate_ok = _extract_om_success_flags(merged_output)
        classified_failure = _classify_om_failure(merged_output, check_ok, simulate_ok)

        if proc.returncode != 0 or classified_failure != "none":
            return {
                "status": "failed",
                "failure_type": classified_failure,
                "events": 0,
                "log_excerpt": f"[{selected_image}] {(proc.stderr or proc.stdout).strip()[:170]}",
                "model_script": script_rel,
                "exit_code": proc.returncode,
                "check_ok": check_ok,
                "simulate_ok": simulate_ok,
            }

        return {
            "status": "success",
            "failure_type": "none",
            "events": 1 if simulate_ok else 0,
            "log_excerpt": f"[{selected_image}] {(proc.stdout or proc.stderr).strip()[:170]}",
            "model_script": script_rel,
            "exit_code": proc.returncode,
            "check_ok": check_ok,
            "simulate_ok": simulate_ok,
        }


def _extract_om_success_flags(output: str) -> tuple[bool, bool]:
    # Lightweight signal extraction for now; can be replaced by structured parser later.
    lower = output.lower()
    check_ok = "check of" in lower and "completed successfully" in lower
    has_sim_result = "record simulationresult" in lower
    result_file_empty = 'resultfile = ""' in lower
    sim_error_markers = (
        "simulation execution failed" in lower
        or "error occurred while solving" in lower
        or "division by zero" in lower
        or "assertion" in lower
        or "integrator failed" in lower
    )
    simulate_ok = has_sim_result and not result_file_empty and not sim_error_markers
    return check_ok, simulate_ok


def _classify_om_failure(output: str, check_ok: bool, simulate_ok: bool) -> str:
    # Failure taxonomy v0 from log patterns; conservative fallback keeps unknowns visible.
    lower = output.lower()
    if (
        "permission denied while trying to connect to the docker api" in lower
        or "cannot connect to the docker daemon" in lower
        or "docker daemon" in lower and "not running" in lower
    ):
        return "docker_error"
    if (
        "no viable alternative near token" in lower
        or "syntax error" in lower
        or "missing token" in lower
    ):
        return "script_parse_error"
    if "undeclared variable" in lower or "variable y not found" in lower:
        return "model_check_error"
    # Only treat explicit model-check failures as model_check_error.
    if re.search(r"check of .* failed", lower) is not None:
        return "model_check_error"
    if (
        "simulation execution failed" in lower
        or "error occurred while solving" in lower
        or "division by zero" in lower
        or "assertion" in lower
    ):
        return "simulate_error"
    if not check_ok:
        return "model_check_error"
    if not simulate_ok:
        return "simulate_error"
    if "error:" in lower:
        return "docker_error"
    return "none"


def gate_decision(status: str, failure_type: str) -> str:
    if status == "success":
        return "PASS"
    if failure_type == "tool_missing":
        return "NEEDS_REVIEW"
    return "FAIL"


def validate_evidence(evidence: dict) -> None:
    # Hard schema checks prevent silent drift in gate/checker inputs.
    required_top = {
        "schema_version",
        "run_id",
        "timestamp_utc",
        "backend",
        "status",
        "failure_type",
        "metrics",
        "artifacts",
        "model_script",
        "exit_code",
        "check_ok",
        "simulate_ok",
        "gate",
    }
    missing = required_top - set(evidence.keys())
    if missing:
        raise ValueError(f"Missing required evidence keys: {sorted(missing)}")

    if evidence["backend"] not in {"mock", "openmodelica", "openmodelica_docker"}:
        raise ValueError("backend must be mock/openmodelica/openmodelica_docker")
    if evidence["status"] not in {"success", "failed"}:
        raise ValueError("status must be success/failed")
    if evidence["gate"] not in {"PASS", "FAIL", "NEEDS_REVIEW"}:
        raise ValueError("gate must be PASS/FAIL/NEEDS_REVIEW")
    if evidence["model_script"] is not None and not isinstance(evidence["model_script"], str):
        raise ValueError("model_script must be string or null")
    if not isinstance(evidence["exit_code"], int):
        raise ValueError("exit_code must be integer")
    if not isinstance(evidence["check_ok"], bool):
        raise ValueError("check_ok must be boolean")
    if not isinstance(evidence["simulate_ok"], bool):
        raise ValueError("simulate_ok must be boolean")

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


def _resolve_report_path(out_path: str, report_path: str | None) -> str:
    if report_path:
        return report_path
    out = Path(out_path)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_path}.md"


def _write_markdown_report(path: str, evidence: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Run Report",
        "",
        f"- gate: `{evidence['gate']}`",
        f"- status: `{evidence['status']}`",
        f"- failure_type: `{evidence['failure_type']}`",
        f"- backend: `{evidence['backend']}`",
        f"- model_script: `{evidence['model_script']}`",
        f"- check_ok: `{evidence['check_ok']}`",
        f"- simulate_ok: `{evidence['simulate_ok']}`",
        f"- exit_code: `{evidence['exit_code']}`",
        f"- runtime_seconds: `{evidence['metrics']['runtime_seconds']}`",
        "",
        "## Log Excerpt",
        "",
        "```text",
        evidence["artifacts"]["log_excerpt"],
        "```",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
