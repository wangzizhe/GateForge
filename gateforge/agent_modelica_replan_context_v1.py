from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_replan_context_v1"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


@dataclass
class CandidateBranch:
    branch_id: str
    branch_kind: str
    trigger_signal: str
    viability_status: str = ""
    supporting_parameters: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "branch_id": self.branch_id,
            "branch_kind": self.branch_kind,
            "trigger_signal": self.trigger_signal,
            "viability_status": self.viability_status,
            "supporting_parameters": list(self.supporting_parameters),
        }


@dataclass
class AgentModelicaReplanContext:
    schema_version: str
    generated_at_utc: str
    task_id: str
    run_id: str
    previous_successful_action: str
    stall_signal: str
    current_branch: str
    candidate_branches: list[dict]
    continue_current_branch: bool
    switch_branch: bool
    selected_branch: str
    replan_count: int
    remaining_replan_budget: int
    decision_reason_code: str
    abandoned_branch: str = ""

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        run_id: str,
        previous_successful_action: str,
        stall_signal: str,
        current_branch: str,
        candidate_branches: list[CandidateBranch | dict],
        continue_current_branch: bool,
        switch_branch: bool,
        selected_branch: str,
        replan_count: int,
        remaining_replan_budget: int,
        decision_reason_code: str,
        abandoned_branch: str = "",
    ) -> "AgentModelicaReplanContext":
        normalized_branches: list[dict] = []
        for branch in candidate_branches:
            if isinstance(branch, CandidateBranch):
                payload = branch.to_dict()
            elif isinstance(branch, dict):
                payload = {
                    "branch_id": _norm(branch.get("branch_id")),
                    "branch_kind": _norm(branch.get("branch_kind")),
                    "trigger_signal": _norm(branch.get("trigger_signal")),
                    "viability_status": _norm(branch.get("viability_status")),
                    "supporting_parameters": [
                        _norm(item)
                        for item in (branch.get("supporting_parameters") or [])
                        if _norm(item)
                    ],
                }
            else:
                raise TypeError(f"Unsupported branch entry: {type(branch)!r}")
            if not payload["branch_id"]:
                raise ValueError("candidate branch missing branch_id")
            if not payload["branch_kind"]:
                raise ValueError(f"candidate branch {payload['branch_id']!r} missing branch_kind")
            normalized_branches.append(payload)

        if not normalized_branches:
            raise ValueError("candidate_branches must not be empty")
        if continue_current_branch and switch_branch:
            raise ValueError("continue_current_branch and switch_branch cannot both be true")
        if not continue_current_branch and not switch_branch:
            raise ValueError("one of continue_current_branch or switch_branch must be true")
        if switch_branch and not _norm(selected_branch):
            raise ValueError("selected_branch is required when switch_branch is true")
        if _norm(abandoned_branch) and _norm(abandoned_branch) == _norm(selected_branch):
            raise ValueError("abandoned_branch must differ from selected_branch")

        return cls(
            schema_version=SCHEMA_VERSION,
            generated_at_utc=_now_utc(),
            task_id=_norm(task_id),
            run_id=_norm(run_id),
            previous_successful_action=_norm(previous_successful_action),
            stall_signal=_norm(stall_signal),
            current_branch=_norm(current_branch),
            candidate_branches=normalized_branches,
            continue_current_branch=bool(continue_current_branch),
            switch_branch=bool(switch_branch),
            selected_branch=_norm(selected_branch),
            replan_count=int(replan_count),
            remaining_replan_budget=int(remaining_replan_budget),
            decision_reason_code=_norm(decision_reason_code),
            abandoned_branch=_norm(abandoned_branch),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def build_replan_context_dict(**kwargs) -> dict:
    return AgentModelicaReplanContext.create(**kwargs).to_dict()
