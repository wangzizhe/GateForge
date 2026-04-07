"""Proactive environment compatibility detector for OpenModelica Docker.

Implements a dependency-ordered probe chain that validates infrastructure
health BEFORE expensive agent work begins. Each probe depends on the
previous one passing; failures propagate as ``skipped_dependency``.

Probe chain:
  1. docker_reachable   -- Docker daemon responds
  2. docker_image       -- OMC Docker image available locally
  3. check_model        -- Known-good model passes checkModel
  4. simulate           -- Known-good model passes simulate
  5. whitelist_models   -- (optional) All whitelist models pass

Note: msl_load is intentionally omitted. The openmodelica minimal image
does not bundle MSL; the whitelist models (MinimalProbe, MediumOscillator)
do not import Modelica.* so MSL availability is not required to validate
the compile-and-simulate pipeline.

Transferable AI agent pattern: Infrastructure Probe Chain with
structured diagnostic output and fail-fast behavior.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    """Outcome of a single compatibility probe."""

    probe_id: str
    status: str  # "pass" | "fail" | "skipped_dependency"
    latency_sec: float
    timestamp_utc: str
    error_detail: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class CompatibilityReport:
    """Aggregated compatibility report across all probes."""

    schema_version: str
    run_id: str
    timestamp_utc: str
    docker_image: str
    overall_status: str  # "pass" | "fail"
    first_failure: str  # probe_id of first failing probe, or ""
    total_latency_sec: float
    probes: list[ProbeResult] = field(default_factory=list)
    environment_failure_kinds: list[str] = field(default_factory=list)


SCHEMA_VERSION = "agent_modelica_compatibility_detector_v1"

# Map probe failures to the vocabulary used by _classify_failure_domain_v1
# in agent_modelica_run_contract_v1.py for consistent attribution.
_PROBE_TO_FAILURE_KIND: dict[str, str] = {
    "docker_reachable": "docker_unavailable",
    "docker_image": "docker_unavailable",
    "check_model": "source_block_incompatible",
    "simulate": "source_block_incompatible",
}


# ---------------------------------------------------------------------------
# Utility: known-good model for check/simulate probes
# ---------------------------------------------------------------------------

_ANCHOR_MODEL_RELATIVE = "examples/openmodelica/MinimalProbe.mo"
_ANCHOR_MODEL_NAME = "MinimalProbe"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Individual probes
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _skip(probe_id: str) -> ProbeResult:
    return ProbeResult(
        probe_id=probe_id,
        status="skipped_dependency",
        latency_sec=0.0,
        timestamp_utc=_now_utc(),
        error_detail="skipped: earlier probe failed",
    )


def _probe_docker_reachable(timeout_sec: int = 15) -> ProbeResult:
    """Check that the Docker daemon is reachable."""
    from .agent_modelica_live_executor_v1 import _run_cmd

    ts = _now_utc()
    t0 = time.monotonic()
    code, output = _run_cmd(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        timeout_sec=timeout_sec,
    )
    elapsed = time.monotonic() - t0
    if code == 0 and output.strip():
        return ProbeResult(
            probe_id="docker_reachable",
            status="pass",
            latency_sec=round(elapsed, 3),
            timestamp_utc=ts,
            metadata={"docker_version": output.strip().splitlines()[0]},
        )
    return ProbeResult(
        probe_id="docker_reachable",
        status="fail",
        latency_sec=round(elapsed, 3),
        timestamp_utc=ts,
        error_detail=output[:500] if output else "docker info returned no output",
    )


def _probe_docker_image(image: str, pull_timeout_sec: int = 120) -> ProbeResult:
    """Check that the OMC Docker image is available locally."""
    from .agent_modelica_live_executor_v1 import _run_cmd

    ts = _now_utc()
    t0 = time.monotonic()
    code, output = _run_cmd(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        timeout_sec=15,
    )
    if code == 0 and output.strip():
        elapsed = time.monotonic() - t0
        return ProbeResult(
            probe_id="docker_image",
            status="pass",
            latency_sec=round(elapsed, 3),
            timestamp_utc=ts,
            metadata={"image": image, "pulled": False},
        )
    # Image not found locally -- attempt pull.
    code, output = _run_cmd(
        ["docker", "pull", image],
        timeout_sec=pull_timeout_sec,
    )
    elapsed = time.monotonic() - t0
    if code == 0:
        return ProbeResult(
            probe_id="docker_image",
            status="pass",
            latency_sec=round(elapsed, 3),
            timestamp_utc=ts,
            metadata={"image": image, "pulled": True},
        )
    return ProbeResult(
        probe_id="docker_image",
        status="fail",
        latency_sec=round(elapsed, 3),
        timestamp_utc=ts,
        error_detail=output[:500],
        metadata={"image": image},
    )


def _probe_msl_load(image: str, timeout_sec: int = 60) -> ProbeResult:
    """Check that the Modelica Standard Library loads in OMC."""
    from .agent_modelica_live_executor_v1 import _run_omc_script_docker

    ts = _now_utc()
    t0 = time.monotonic()
    script = 'loadModel(Modelica); getErrorString();\n'
    with tempfile.TemporaryDirectory(prefix="gf_compat_msl_") as tmpdir:
        code, output = _run_omc_script_docker(
            script_text=script,
            timeout_sec=timeout_sec,
            cwd=tmpdir,
            image=image,
        )
    elapsed = time.monotonic() - t0
    lower = (output or "").lower()
    if code == 0 and "true" in lower and "error" not in lower:
        return ProbeResult(
            probe_id="msl_load",
            status="pass",
            latency_sec=round(elapsed, 3),
            timestamp_utc=ts,
        )
    return ProbeResult(
        probe_id="msl_load",
        status="fail",
        latency_sec=round(elapsed, 3),
        timestamp_utc=ts,
        error_detail=output[:500] if output else "msl load produced no output",
    )


def _probe_check_model(image: str, timeout_sec: int = 60) -> ProbeResult:
    """Check that a known-good model passes checkModel."""
    from .agent_modelica_live_executor_v1 import (
        _run_omc_script_docker,
        _extract_om_success_flags,
    )

    ts = _now_utc()
    t0 = time.monotonic()
    model_src = _repo_root() / _ANCHOR_MODEL_RELATIVE
    if not model_src.exists():
        return ProbeResult(
            probe_id="check_model",
            status="fail",
            latency_sec=0.0,
            timestamp_utc=ts,
            error_detail=f"anchor model not found: {model_src}",
        )
    with tempfile.TemporaryDirectory(prefix="gf_compat_check_") as tmpdir:
        dest = Path(tmpdir) / model_src.name
        shutil.copy2(model_src, dest)
        script = (
            f'loadFile("{model_src.name}"); getErrorString();\n'
            f'checkModel({_ANCHOR_MODEL_NAME}); getErrorString();\n'
        )
        code, output = _run_omc_script_docker(
            script_text=script,
            timeout_sec=timeout_sec,
            cwd=tmpdir,
            image=image,
        )
    elapsed = time.monotonic() - t0
    check_ok, _ = _extract_om_success_flags(output)
    if check_ok:
        return ProbeResult(
            probe_id="check_model",
            status="pass",
            latency_sec=round(elapsed, 3),
            timestamp_utc=ts,
            metadata={"model": _ANCHOR_MODEL_NAME},
        )
    return ProbeResult(
        probe_id="check_model",
        status="fail",
        latency_sec=round(elapsed, 3),
        timestamp_utc=ts,
        error_detail=output[:500] if output else "checkModel produced no output",
        metadata={"model": _ANCHOR_MODEL_NAME},
    )


def _probe_simulate(image: str, timeout_sec: int = 60) -> ProbeResult:
    """Check that a known-good model passes simulate."""
    from .agent_modelica_live_executor_v1 import (
        _run_omc_script_docker,
        _extract_om_success_flags,
    )

    ts = _now_utc()
    t0 = time.monotonic()
    model_src = _repo_root() / _ANCHOR_MODEL_RELATIVE
    if not model_src.exists():
        return ProbeResult(
            probe_id="simulate",
            status="fail",
            latency_sec=0.0,
            timestamp_utc=ts,
            error_detail=f"anchor model not found: {model_src}",
        )
    with tempfile.TemporaryDirectory(prefix="gf_compat_sim_") as tmpdir:
        dest = Path(tmpdir) / model_src.name
        shutil.copy2(model_src, dest)
        script = (
            f'loadFile("{model_src.name}"); getErrorString();\n'
            f'simulate({_ANCHOR_MODEL_NAME}, stopTime=1.0, numberOfIntervals=20); getErrorString();\n'
        )
        code, output = _run_omc_script_docker(
            script_text=script,
            timeout_sec=timeout_sec,
            cwd=tmpdir,
            image=image,
        )
    elapsed = time.monotonic() - t0
    _, sim_ok = _extract_om_success_flags(output)
    if sim_ok:
        return ProbeResult(
            probe_id="simulate",
            status="pass",
            latency_sec=round(elapsed, 3),
            timestamp_utc=ts,
            metadata={"model": _ANCHOR_MODEL_NAME},
        )
    return ProbeResult(
        probe_id="simulate",
        status="fail",
        latency_sec=round(elapsed, 3),
        timestamp_utc=ts,
        error_detail=output[:500] if output else "simulate produced no output",
        metadata={"model": _ANCHOR_MODEL_NAME},
    )


# ---------------------------------------------------------------------------
# Whitelist runner
# ---------------------------------------------------------------------------

def _load_whitelist(path: str) -> list[dict]:
    """Load whitelist JSON and return the models list."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data.get("models", []) if isinstance(data, dict) else []


def _run_whitelist_models(
    models: list[dict],
    image: str,
    timeout_sec: int,
) -> list[ProbeResult]:
    """Run checkModel + simulate for each whitelist model."""
    from .agent_modelica_live_executor_v1 import (
        _run_omc_script_docker,
        _extract_om_success_flags,
    )

    results: list[ProbeResult] = []
    for entry in models:
        model_id = str(entry.get("model_id") or "unknown")
        model_path = str(entry.get("model_path") or "")
        model_name = str(entry.get("model_name") or "")
        stop_time = float(entry.get("stop_time") or 1.0)

        model_src = _repo_root() / model_path
        if not model_src.exists():
            results.append(ProbeResult(
                probe_id=f"whitelist:{model_id}",
                status="fail",
                latency_sec=0.0,
                timestamp_utc=_now_utc(),
                error_detail=f"model file not found: {model_src}",
                metadata={"model_id": model_id},
            ))
            continue

        ts = _now_utc()
        t0 = time.monotonic()
        with tempfile.TemporaryDirectory(prefix=f"gf_compat_wl_{model_id}_") as tmpdir:
            dest = Path(tmpdir) / model_src.name
            shutil.copy2(model_src, dest)
            script = (
                f'loadFile("{model_src.name}"); getErrorString();\n'
                f'checkModel({model_name}); getErrorString();\n'
                f'simulate({model_name}, stopTime={stop_time}, numberOfIntervals=20); getErrorString();\n'
            )
            code, output = _run_omc_script_docker(
                script_text=script,
                timeout_sec=timeout_sec,
                cwd=tmpdir,
                image=image,
            )
        elapsed = time.monotonic() - t0
        check_ok, sim_ok = _extract_om_success_flags(output)

        expect_check = bool(entry.get("expect_check_pass", True))
        expect_sim = bool(entry.get("expect_simulate_pass", True))
        passed = (check_ok or not expect_check) and (sim_ok or not expect_sim)

        error = ""
        if not passed:
            parts = []
            if expect_check and not check_ok:
                parts.append("checkModel failed")
            if expect_sim and not sim_ok:
                parts.append("simulate failed")
            error = "; ".join(parts) + f" | {output[:300]}"

        results.append(ProbeResult(
            probe_id=f"whitelist:{model_id}",
            status="pass" if passed else "fail",
            latency_sec=round(elapsed, 3),
            timestamp_utc=ts,
            error_detail=error,
            metadata={
                "model_id": model_id,
                "check_ok": check_ok,
                "simulate_ok": sim_ok,
            },
        ))
    return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_compatibility_probes(
    docker_image: str,
    timeout_sec: int = 180,
    whitelist_path: str | None = None,
) -> CompatibilityReport:
    """Run the full ordered probe chain and return a compatibility report.

    The probe chain is dependency-ordered: if an early probe fails, all
    downstream probes are marked ``skipped_dependency`` instead of
    wasting time on attempts that cannot succeed.
    """
    run_id = str(uuid.uuid4())[:12]
    ts = _now_utc()
    t0 = time.monotonic()

    probes: list[ProbeResult] = []
    failed = False

    # Per-probe timeout slice: divide total budget across base probes.
    per_probe = max(10, timeout_sec // 5)

    # Probe 1: Docker reachable
    p = _probe_docker_reachable(timeout_sec=min(per_probe, 15))
    probes.append(p)
    if p.status != "pass":
        failed = True

    # Probe 2: Docker image available
    if not failed:
        p = _probe_docker_image(docker_image, pull_timeout_sec=min(per_probe * 2, 120))
        probes.append(p)
        if p.status != "pass":
            failed = True
    else:
        probes.append(_skip("docker_image"))

    # Probe 3: checkModel
    if not failed:
        p = _probe_check_model(docker_image, timeout_sec=per_probe)
        probes.append(p)
        if p.status != "pass":
            failed = True
    else:
        probes.append(_skip("check_model"))

    # Probe 4: simulate
    if not failed:
        p = _probe_simulate(docker_image, timeout_sec=per_probe)
        probes.append(p)
        if p.status != "pass":
            failed = True
    else:
        probes.append(_skip("simulate"))

    # Optional probe 5: whitelist models
    if not failed and whitelist_path:
        models = _load_whitelist(whitelist_path)
        wl_results = _run_whitelist_models(models, docker_image, timeout_sec=per_probe)
        probes.extend(wl_results)
        if any(r.status == "fail" for r in wl_results):
            failed = True

    total_elapsed = time.monotonic() - t0

    # Determine first failure and environment failure kinds.
    first_failure = ""
    env_kinds: list[str] = []
    for pr in probes:
        if pr.status == "fail":
            if not first_failure:
                first_failure = pr.probe_id
            base_id = pr.probe_id.split(":")[0] if ":" in pr.probe_id else pr.probe_id
            kind = _PROBE_TO_FAILURE_KIND.get(base_id, "")
            if kind and kind not in env_kinds:
                env_kinds.append(kind)

    return CompatibilityReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        timestamp_utc=ts,
        docker_image=docker_image,
        overall_status="fail" if failed else "pass",
        first_failure=first_failure,
        total_latency_sec=round(total_elapsed, 3),
        probes=probes,
        environment_failure_kinds=env_kinds,
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def report_to_dict(report: CompatibilityReport) -> dict:
    """Serialize a CompatibilityReport to a JSON-safe dict."""
    return {
        "schema_version": report.schema_version,
        "run_id": report.run_id,
        "timestamp_utc": report.timestamp_utc,
        "docker_image": report.docker_image,
        "overall_status": report.overall_status,
        "first_failure": report.first_failure,
        "total_latency_sec": report.total_latency_sec,
        "environment_failure_kinds": report.environment_failure_kinds,
        "probes": [
            {
                "probe_id": p.probe_id,
                "status": p.status,
                "latency_sec": p.latency_sec,
                "timestamp_utc": p.timestamp_utc,
                "error_detail": p.error_detail,
                "metadata": p.metadata,
            }
            for p in report.probes
        ],
    }


def write_compatibility_report(
    report: CompatibilityReport,
    out_path: str,
    md_path: str | None = None,
) -> None:
    """Write the compatibility report as JSON (and optionally markdown)."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report_to_dict(report), indent=2), encoding="utf-8")

    if md_path:
        mp = Path(md_path)
        mp.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Compatibility Report ({report.run_id})",
            "",
            f"- **Overall**: {report.overall_status}",
            f"- **Docker image**: {report.docker_image}",
            f"- **Total latency**: {report.total_latency_sec:.1f}s",
            f"- **First failure**: {report.first_failure or '(none)'}",
            f"- **Environment failure kinds**: {', '.join(report.environment_failure_kinds) or '(none)'}",
            "",
            "## Probes",
            "",
            "| Probe | Status | Latency | Error |",
            "|-------|--------|---------|-------|",
        ]
        for pr in report.probes:
            err = pr.error_detail[:80].replace("|", "/") if pr.error_detail else ""
            lines.append(f"| {pr.probe_id} | {pr.status} | {pr.latency_sec:.1f}s | {err} |")
        lines.append("")
        mp.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run OpenModelica environment compatibility probes."
    )
    parser.add_argument(
        "--docker-image",
        default="openmodelica/openmodelica:v1.26.1-minimal",
        help="Docker image to probe (default: openmodelica/openmodelica:v1.26.1-minimal)",
    )
    parser.add_argument(
        "--whitelist",
        default=None,
        help="Path to whitelist JSON with known-good models",
    )
    parser.add_argument(
        "--out",
        default="artifacts/compatibility_smoke/compatibility_report.json",
        help="Output path for the JSON report",
    )
    parser.add_argument(
        "--md-out",
        default=None,
        help="Optional output path for a markdown report",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=180,
        help="Total timeout budget in seconds (default: 180)",
    )
    args = parser.parse_args()

    report = run_compatibility_probes(
        docker_image=args.docker_image,
        timeout_sec=args.timeout_sec,
        whitelist_path=args.whitelist,
    )
    write_compatibility_report(report, out_path=args.out, md_path=args.md_out)

    # Print summary to stdout.
    print(json.dumps(report_to_dict(report), indent=2))

    if report.overall_status != "pass":
        print(
            f"\nCOMPATIBILITY SMOKE FAILED: first_failure={report.first_failure}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
