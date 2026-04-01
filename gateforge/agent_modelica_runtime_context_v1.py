from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_runtime_context_v1"
DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_planner_backend_from_env() -> str:
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return ""


@dataclass
class AgentModelicaRuntimeContext:
    schema_version: str
    generated_at_utc: str
    task_id: str
    run_id: str
    arm_kind: str
    artifact_root: str
    planner_backend: str
    omc_backend: str
    docker_image: str
    source_model_path: str
    mutated_model_path: str
    result_path: str
    declared_failure_type: str
    expected_stage: str
    max_rounds: int
    simulate_stop_time: float
    simulate_intervals: int
    timeout_sec: int
    baseline_measurement_protocol: dict

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        run_id: str,
        arm_kind: str,
        artifact_root: str | Path,
        source_model_path: str | Path,
        mutated_model_path: str | Path,
        result_path: str | Path,
        declared_failure_type: str,
        expected_stage: str,
        max_rounds: int,
        simulate_stop_time: float,
        simulate_intervals: int,
        timeout_sec: int,
        planner_backend: str = "",
        omc_backend: str = "openmodelica_docker",
        docker_image: str = DEFAULT_DOCKER_IMAGE,
        protocol_version: str = "v0_3_6_single_sweep_baseline_authority_v1",
        enabled_policy_flags: dict | None = None,
    ) -> "AgentModelicaRuntimeContext":
        backend = str(planner_backend or resolve_planner_backend_from_env()).strip()
        policy_flags = dict(enabled_policy_flags or {})
        baseline_protocol = {
            "protocol_version": str(protocol_version),
            "baseline_lever_name": "simulate_error_parameter_recovery_sweep",
            "baseline_reference_version": "v0.3.5",
            "max_rounds": int(max_rounds),
            "timeout_sec": int(timeout_sec),
            "simulate_stop_time": float(simulate_stop_time),
            "simulate_intervals": int(simulate_intervals),
            "planner_backend": backend,
            "enabled_policy_flags": policy_flags,
        }
        return cls(
            schema_version=SCHEMA_VERSION,
            generated_at_utc=_now_utc(),
            task_id=str(task_id),
            run_id=str(run_id),
            arm_kind=str(arm_kind),
            artifact_root=str(Path(artifact_root).resolve()),
            planner_backend=backend,
            omc_backend=str(omc_backend),
            docker_image=str(docker_image),
            source_model_path=str(Path(source_model_path).resolve()),
            mutated_model_path=str(Path(mutated_model_path).resolve()),
            result_path=str(Path(result_path).resolve()),
            declared_failure_type=str(declared_failure_type),
            expected_stage=str(expected_stage),
            max_rounds=int(max_rounds),
            simulate_stop_time=float(simulate_stop_time),
            simulate_intervals=int(simulate_intervals),
            timeout_sec=int(timeout_sec),
            baseline_measurement_protocol=baseline_protocol,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def executor_command(self) -> list[str]:
        return [
            sys.executable,
            "-m",
            "gateforge.agent_modelica_live_executor_gemini_v1",
            "--task-id",
            self.task_id,
            "--failure-type",
            self.declared_failure_type,
            "--expected-stage",
            self.expected_stage,
            "--mutated-model-path",
            self.mutated_model_path,
            "--source-model-path",
            self.source_model_path,
            "--backend",
            self.omc_backend,
            "--docker-image",
            self.docker_image,
            "--planner-backend",
            self.planner_backend,
            "--max-rounds",
            str(self.max_rounds),
            "--simulate-stop-time",
            str(self.simulate_stop_time),
            "--simulate-intervals",
            str(self.simulate_intervals),
            "--out",
            self.result_path,
        ]

