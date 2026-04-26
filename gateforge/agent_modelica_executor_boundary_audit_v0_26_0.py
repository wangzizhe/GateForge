from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from . import agent_modelica_l2_plan_replan_engine_v1 as planner
from . import llm_provider_adapter
from .llm_provider_adapter import DeepSeekProviderAdapter


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "executor_boundary_audit_v0_26_0"
EXECUTOR_PATH = REPO_ROOT / "gateforge" / "agent_modelica_live_executor_v1.py"
ADAPTER_PATH = REPO_ROOT / "gateforge" / "llm_provider_adapter.py"
PLANNER_PATH = REPO_ROOT / "gateforge" / "agent_modelica_l2_plan_replan_engine_v1.py"

FORBIDDEN_ADAPTER_DECISION_TERMS = (
    "candidate_score",
    "rank_candidate",
    "select_candidate",
    "omc_diagnose",
    "modelica_diagnose",
    "deterministic_repair",
    "apply_patch",
    "case_specific",
)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _line_hits(text: str, needles: tuple[str, ...]) -> dict[str, int]:
    hits: dict[str, int] = {}
    lowered = text.lower()
    for needle in needles:
        count = lowered.count(needle.lower())
        if count:
            hits[needle] = count
    return hits


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def build_executor_boundary_audit(
    *,
    executor_path: Path = EXECUTOR_PATH,
    adapter_path: Path = ADAPTER_PATH,
    planner_path: Path = PLANNER_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    executor_text = _read_text(executor_path)
    adapter_text = _read_text(adapter_path)
    planner_text = _read_text(planner_path)
    deepseek_adapter_source = inspect.getsource(DeepSeekProviderAdapter)

    registered_adapters = sorted(llm_provider_adapter._ADAPTERS.keys())  # type: ignore[attr-defined]
    deepseek_provider_registered = "deepseek" in registered_adapters
    deepseek_planner_family = planner.planner_family_for_provider("deepseek")
    deepseek_planner_adapter = planner.planner_adapter_for_provider("deepseek")

    executor_deepseek_mentions = _line_hits(executor_text, ("deepseek", "deepseek-v4-flash"))
    deepseek_adapter_decision_hits = _line_hits(deepseek_adapter_source, FORBIDDEN_ADAPTER_DECISION_TERMS)
    source_presence = {
        "executor": bool(executor_text),
        "adapter": bool(adapter_text),
        "planner": bool(planner_text),
    }
    boundary_clean = (
        all(source_presence.values())
        and deepseek_provider_registered
        and deepseek_planner_family == "llm"
        and deepseek_planner_adapter == "gateforge_deepseek_planner_v1"
        and not executor_deepseek_mentions
        and not deepseek_adapter_decision_hits
    )

    summary = {
        "version": "v0.26.0",
        "status": "PASS" if boundary_clean else "REVIEW",
        "analysis_scope": "executor_boundary_audit",
        "source_presence": source_presence,
        "provider_adapter_matrix": {
            "registered_adapters": registered_adapters,
            "deepseek_provider_registered": deepseek_provider_registered,
            "deepseek_model": "deepseek-v4-flash",
            "deepseek_api_shape": "openai_compatible_chat_completions",
        },
        "planner_profile_boundary": {
            "deepseek_planner_family": deepseek_planner_family,
            "deepseek_planner_adapter": deepseek_planner_adapter,
            "profile_changes_repair_strategy": False,
        },
        "executor_boundary": {
            "executor_path": _display_path(executor_path),
            "provider_specific_deepseek_mentions": executor_deepseek_mentions,
            "executor_provider_specific_logic_added": bool(executor_deepseek_mentions),
        },
        "adapter_boundary": {
            "adapter_path": _display_path(adapter_path),
            "forbidden_decision_term_hits": deepseek_adapter_decision_hits,
            "adapter_makes_repair_decisions": bool(deepseek_adapter_decision_hits),
        },
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
            "public_changelog_update": "defer_until_public_phase_closeout",
            "env_file_inspected": False,
        },
        "decision": (
            "deepseek_can_enter_as_provider_adapter_boundary_only"
            if boundary_clean
            else "executor_boundary_needs_review_before_live_benchmark"
        ),
        "next_focus": "v0.26.1_observation_contract",
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
