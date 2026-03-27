from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)


SCHEMA_VERSION = "agent_modelica_cross_domain_source_viability_filter_v1"


def _read_registry(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"schema_version": "dataset_open_source_model_intake_v1", "models": []}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": "dataset_open_source_model_intake_v1", "models": []}
    if not isinstance(payload, dict):
        return {"schema_version": "dataset_open_source_model_intake_v1", "models": []}
    models = payload.get("models")
    if not isinstance(models, list):
        payload["models"] = []
    return payload


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_viability_check(
    *,
    row: dict,
    backend: str,
    docker_image: str,
    timeout_sec: int,
    stop_time: float,
    intervals: int,
    extra_model_loads: list[str],
) -> dict:
    source_model_path = Path(str(row.get("source_path") or "")).resolve()
    source_library_path = str(row.get("source_library_path") or "")
    source_package_name = str(row.get("source_package_name") or "")
    source_library_model_path = str(row.get("source_library_model_path") or "")
    source_qualified_model_name = str(row.get("source_qualified_model_name") or "").strip()
    model_name = source_qualified_model_name.rsplit(".", 1)[-1] if source_qualified_model_name else source_model_path.stem

    if not source_model_path.exists():
        return {
            "status": "REJECT",
            "reason": "source_model_missing",
            "check_model_pass": False,
            "simulate_pass": False,
            "rc": None,
            "stderr_snippet": "",
        }

    with temporary_workspace("gf_cross_domain_viability_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(source_model_path.name),
            primary_model_name=model_name,
            source_library_path=source_library_path,
            source_package_name=source_package_name,
            source_library_model_path=source_library_model_path,
            source_qualified_model_name=source_qualified_model_name,
        )
        layout.model_write_path.write_text(source_model_path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        rc, output, check_ok, sim_ok = run_check_and_simulate(
            workspace=workspace,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=int(timeout_sec),
            backend=backend,
            docker_image=docker_image,
            stop_time=float(stop_time),
            intervals=int(intervals),
            extra_model_loads=list(extra_model_loads or []),
        )
    snippet = str(output or "")[-2000:]
    if bool(check_ok and sim_ok):
        return {
            "status": "PASS",
            "reason": "source_model_viable",
            "check_model_pass": True,
            "simulate_pass": True,
            "rc": int(rc) if rc is not None else None,
            "stderr_snippet": snippet,
        }
    if bool(check_ok) and not bool(sim_ok):
        reason = "simulate_failed_on_source_model"
    elif not bool(check_ok):
        reason = "check_model_failed_on_source_model"
    else:
        reason = "source_model_not_viable"
    return {
        "status": "REJECT",
        "reason": reason,
        "check_model_pass": bool(check_ok),
        "simulate_pass": bool(sim_ok),
        "rc": int(rc) if rc is not None else None,
        "stderr_snippet": snippet,
    }


def filter_registry(
    *,
    registry_path: str,
    registry_out: str,
    out: str,
    backend: str = "openmodelica_docker",
    docker_image: str = "openmodelica/openmodelica:v1.26.1-minimal",
    timeout_sec: int = 300,
    stop_time: float = 0.2,
    intervals: int = 20,
    extra_model_loads: list[str] | None = None,
) -> dict:
    registry = _read_registry(registry_path)
    models = registry.get("models") if isinstance(registry.get("models"), list) else []
    accepted: list[dict] = []
    rejected: list[dict] = []
    by_scale: dict[str, dict[str, int]] = {}
    checks: list[dict] = []

    for row in models:
        if not isinstance(row, dict):
            continue
        viability = _run_viability_check(
            row=row,
            backend=backend,
            docker_image=docker_image,
            timeout_sec=timeout_sec,
            stop_time=stop_time,
            intervals=intervals,
            extra_model_loads=list(extra_model_loads or []),
        )
        model_copy = dict(row)
        model_copy["source_viability"] = dict(viability)
        scale = str(row.get("suggested_scale") or "unknown").strip().lower() or "unknown"
        bucket = by_scale.setdefault(scale, {"accepted": 0, "rejected": 0})
        checks.append(
            {
                "model_id": str(row.get("model_id") or ""),
                "source_qualified_model_name": str(row.get("source_qualified_model_name") or ""),
                "suggested_scale": scale,
                **viability,
            }
        )
        if viability.get("status") == "PASS":
            accepted.append(model_copy)
            bucket["accepted"] += 1
        else:
            rejected.append(model_copy)
            bucket["rejected"] += 1

    filtered_registry = {
        "schema_version": str(registry.get("schema_version") or "dataset_open_source_model_intake_v1"),
        "models": accepted,
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "backend": backend,
        "docker_image": docker_image,
        "registry_path": str(registry_path),
        "registry_out": str(registry_out),
        "total_models": len(models),
        "accepted_models": len(accepted),
        "rejected_models": len(rejected),
        "by_scale": by_scale,
        "checks": checks,
    }
    _write_json(registry_out, filtered_registry)
    _write_json(out, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter cross-domain source models by direct OMC viability.")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-out", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--backend", default="openmodelica_docker")
    parser.add_argument("--docker-image", default="openmodelica/openmodelica:v1.26.1-minimal")
    parser.add_argument("--timeout-sec", type=int, default=300)
    parser.add_argument("--stop-time", type=float, default=0.2)
    parser.add_argument("--intervals", type=int, default=20)
    parser.add_argument("--extra-model-load", action="append", dest="extra_model_loads", default=[])
    args = parser.parse_args()

    summary = filter_registry(
        registry_path=str(args.registry),
        registry_out=str(args.registry_out),
        out=str(args.out),
        backend=str(args.backend),
        docker_image=str(args.docker_image),
        timeout_sec=int(args.timeout_sec),
        stop_time=float(args.stop_time),
        intervals=int(args.intervals),
        extra_model_loads=list(args.extra_model_loads or []),
    )
    print(json.dumps({"status": summary.get("status"), "accepted_models": summary.get("accepted_models"), "rejected_models": summary.get("rejected_models")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
