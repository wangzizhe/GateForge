"""L2 Plan/Replan Engine — GateForge Modelica Agent.

Provides:
- LLM provider resolution (env-based, provider-agnostic)
- Planner contract and prompt builders
- Budget-gated LLM request sending
- Unified repair-text generation (Adapter Unification Pattern)
- Multistep plan generation (plan / replan request kinds)

Extracted from agent_modelica_live_executor_v1 using the
Planner-as-Module Pattern and Adapter Unification Pattern.

Adapter Unification Pattern:
    The legacy provider-specific repair functions (_gemini_repair_model_text,
    _openai_repair_model_text) are now thin wrappers that delegate to the
    single unified llm_repair_model_text implementation, eliminating ~90 lines
    of duplicated prompt-construction code.

All public names are exported without underscore prefix.
The executor imports them with Re-export Alias Pattern:

    from .agent_modelica_l2_plan_replan_engine_v1 import (
        llm_generate_repair_plan as _llm_generate_repair_plan,
        ...
    )
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

from .llm_budget import (
    _live_budget_config,
    _record_live_request_429,
    _record_live_request_success,
    _reserve_live_request,
)
from .llm_response import extract_json_object as _extract_json_object_impl


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

MULTISTEP_PLANNER_CONTRACT_VERSION = "agent_modelica_multistep_planner_contract_v1"

_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OPENAI_MODEL_HINT_PATTERN = re.compile(r"^(gpt|o[0-9]|chatgpt|gpt-5)", re.IGNORECASE)
_TIMESTAMP_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d(?::[0-5]\d)?")
_TASK_ID_PATTERN = re.compile(r"\b[a-z]+[0-9]+_[a-z0-9_]+\b")
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|[\s:=])/(?:Users|home|tmp|var)/")


# ---------------------------------------------------------------------------
# Source-mode helper
# ---------------------------------------------------------------------------

def behavioral_robustness_source_mode() -> str:
    """Return 'source_blind' or 'source_aware' based on env var."""
    mode = str(os.getenv("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE") or "").strip().lower()
    if mode in {"blind", "source_blind", "source-blind"}:
        return "source_blind"
    return "source_aware"


# ---------------------------------------------------------------------------
# Env-file bootstrap helpers
# ---------------------------------------------------------------------------

def parse_env_assignment(line: str) -> tuple[str, str] | tuple[None, None]:
    """Parse a single .env line into (key, value) or (None, None)."""
    text = str(line or "").strip()
    if not text or text.startswith("#"):
        return None, None
    if text.startswith("export "):
        text = text[len("export "):].strip()
    if "=" not in text:
        return None, None
    key, raw_value = text.split("=", 1)
    key = key.strip()
    if not _ENV_KEY_PATTERN.match(key):
        return None, None
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _load_env_file(path: Path, allowed_keys: set[str] | None = None) -> int:
    if not path.exists():
        return 0
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    loaded = 0
    for line in content.splitlines():
        key, value = parse_env_assignment(line)
        if not key:
            continue
        if isinstance(allowed_keys, set) and key not in allowed_keys:
            continue
        if str(os.getenv(key) or "").strip():
            continue
        os.environ[key] = value
        loaded += 1
    return loaded


def bootstrap_env_from_repo(allowed_keys: set[str] | None = None) -> int:
    """Load .env keys from repo root or CWD, skipping already-set vars."""
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [Path.cwd() / ".env", repo_root / ".env"]
    loaded = 0
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        loaded += _load_env_file(path, allowed_keys=allowed_keys)
    return loaded


# ---------------------------------------------------------------------------
# LLM provider resolution
# ---------------------------------------------------------------------------

def resolve_llm_provider(requested_backend: str) -> tuple[str, str, str]:
    """Resolve (provider_name, model_name, api_key) from env + request.

    Returns:
        Tuple of (provider, model, api_key).  provider is one of
        'gemini', 'openai', or 'rule'.
    """
    bootstrap_env_from_repo(
        allowed_keys={
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "LLM_MODEL",
            "GATEFORGE_GEMINI_MODEL",
            "GEMINI_MODEL",
            "OPENAI_MODEL",
            "LLM_PROVIDER",
            "GATEFORGE_LIVE_PLANNER_BACKEND",
        }
    )
    requested = str(requested_backend or "").strip().lower()
    if requested == "rule":
        return "rule", "", ""

    model = (
        str(os.getenv("LLM_MODEL") or "").strip()
        or str(os.getenv("OPENAI_MODEL") or "").strip()
        or str(os.getenv("GATEFORGE_GEMINI_MODEL") or "").strip()
        or str(os.getenv("GEMINI_MODEL") or "").strip()
    )
    if not model:
        raise ValueError("missing_llm_model")
    explicit = requested if requested in {"gemini", "openai"} else ""
    if not explicit:
        explicit = str(os.getenv("LLM_PROVIDER") or os.getenv("GATEFORGE_LIVE_PLANNER_BACKEND") or "").strip().lower()
    if explicit not in {"gemini", "openai"}:
        if _OPENAI_MODEL_HINT_PATTERN.search(model):
            explicit = "openai"
        elif "gemini" in model.lower():
            explicit = "gemini"
        else:
            raise ValueError(f"unsupported_llm_model:{model}")
    if explicit == "openai":
        api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise ValueError("missing_openai_api_key")
        return explicit, model, api_key
    api_key = str(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("missing_gemini_api_key")
    return explicit, model, api_key


# ---------------------------------------------------------------------------
# Planner contract and prompt builders
# ---------------------------------------------------------------------------

def planner_family_for_provider(provider: str) -> str:
    """Map provider name to planner family ('rule' | 'llm' | 'unknown')."""
    name = str(provider or "").strip().lower()
    if name == "rule":
        return "rule"
    if name in {"gemini", "openai"}:
        return "llm"
    return "unknown"


def planner_adapter_for_provider(provider: str) -> str:
    """Map provider name to adapter identifier string."""
    name = str(provider or "").strip().lower()
    mapping = {
        "rule": "gateforge_rule_planner_v1",
        "gemini": "gateforge_gemini_planner_v1",
        "openai": "gateforge_openai_planner_v1",
    }
    return mapping.get(name, "gateforge_unknown_planner_v1")


def build_source_blind_multistep_planner_contract(
    *,
    resolved_provider: str,
    request_kind: str,
    stage_context: dict,
    llm_reason: str,
    replan_context: dict | None = None,
    model_name: str = "",
    failure_type: str = "",
) -> dict:
    """Build the planner contract dict embedded in each LLM prompt."""
    return {
        "schema_version": MULTISTEP_PLANNER_CONTRACT_VERSION,
        "planner_family": planner_family_for_provider(resolved_provider),
        "planner_adapter": planner_adapter_for_provider(resolved_provider),
        "planner_request_kind": str(request_kind or "").strip().lower(),
        "realism_version": str((replan_context or {}).get("realism_version") or "").strip().lower(),
        "model_name": str(model_name or "").strip(),
        "failure_type": str(failure_type or "").strip().lower(),
        "current_stage": str(stage_context.get("current_stage") or "").strip().lower(),
        "current_branch": str(stage_context.get("stage_2_branch") or "").strip().lower(),
        "preferred_branch": str(stage_context.get("preferred_stage_2_branch") or "").strip().lower(),
        "current_fail_bucket": str(stage_context.get("current_fail_bucket") or "").strip().lower(),
        "branch_mode": str(stage_context.get("branch_mode") or "").strip().lower(),
        "trap_branch": bool(stage_context.get("trap_branch")),
        "llm_reason": str(llm_reason or "").strip().lower(),
        "previous_plan_failed_signal": str((replan_context or {}).get("previous_plan_failed_signal") or "").strip().lower(),
        "replan_count_before": int((replan_context or {}).get("replan_count_before") or 0),
    }


def build_source_blind_multistep_planner_prompt(
    *,
    original_text: str,
    failure_type: str,
    expected_stage: str,
    error_excerpt: str,
    repair_actions: list[str],
    model_name: str,
    workflow_goal: str = "",
    current_round: int,
    stage_context: dict,
    llm_reason: str,
    request_kind: str,
    replan_context: dict | None,
    resolved_provider: str,
    planner_experience_context: dict | None = None,
) -> tuple[str, dict]:
    """Build (prompt_text, planner_contract) for plan/replan LLM requests."""
    from .agent_modelica_repair_action_policy_v0 import build_multistep_llm_plan_prompt_hints_v1
    from .agent_modelica_stage_branch_controller_v1 import extract_source_blind_multistep_markers

    planner_contract = build_source_blind_multistep_planner_contract(
        resolved_provider=resolved_provider,
        request_kind=request_kind,
        stage_context=stage_context,
        llm_reason=llm_reason,
        replan_context=replan_context,
        model_name=model_name,
        failure_type=failure_type,
    )
    prompt_hints = build_multistep_llm_plan_prompt_hints_v1(
        request_kind=request_kind,
        current_stage=str(stage_context.get("current_stage") or ""),
        current_branch=str(stage_context.get("stage_2_branch") or ""),
        preferred_branch=str(stage_context.get("preferred_stage_2_branch") or ""),
        previous_plan_failed_signal=str((replan_context or {}).get("previous_plan_failed_signal") or ""),
        realism_version=str((replan_context or {}).get("realism_version") or extract_source_blind_multistep_markers(original_text).get("realism_version") or ""),
        replan_count=int((replan_context or {}).get("replan_count_before") or 0),
        guided_search_observation_available=bool((replan_context or {}).get("guided_search_observation")),
    )
    planner_experience_block = ""
    planner_experience_summary = {
        "used": False,
        "positive_hint_count": 0,
        "caution_hint_count": 0,
        "prompt_token_estimate": 0,
        "truncated": False,
    }
    if isinstance(planner_experience_context, dict) and planner_experience_context:
        planner_experience_summary = {
            "used": bool(planner_experience_context.get("used")),
            "positive_hint_count": int(planner_experience_context.get("positive_hint_count") or 0),
            "caution_hint_count": int(planner_experience_context.get("caution_hint_count") or 0),
            "prompt_token_estimate": int(planner_experience_context.get("prompt_token_estimate") or 0),
            "truncated": bool(planner_experience_context.get("truncated")),
        }
        if bool(planner_experience_context.get("used")):
            planner_experience_block = (
                "Planner experience hints below are advisory only; prefer current diagnostic evidence when they conflict.\n"
                f"{str(planner_experience_context.get('prompt_context_text') or '').strip()}\n"
            )
    prompt = (
        "You are planning a Modelica repair.\n"
        "Return ONLY a JSON object with keys:\n"
        "diagnosed_stage, diagnosed_branch, preferred_branch, repair_goal, candidate_parameters, candidate_value_directions, why_not_other_branch, stop_condition, rationale, new_branch, branch_choice_reason, continue_current_branch, switch_to_branch, replan_budget_total, replan_budget_for_branch_diagnosis, replan_budget_for_branch_escape, replan_budget_for_resolution, guided_search_bucket_sequence.\n"
        "Constraints:\n"
        "- Do not output markdown.\n"
        "- candidate_parameters must be a short list of existing numeric parameter names already present in the model text.\n"
        "- candidate_value_directions should describe small-step directions like increase/decrease/normalize.\n"
        f"- planner_contract: {json.dumps(planner_contract, ensure_ascii=True)}\n"
        f"- prompt_hints: {json.dumps(prompt_hints, ensure_ascii=True)}\n"
        f"- planner_experience_summary: {json.dumps(planner_experience_summary, ensure_ascii=True)}\n"
        f"- expected_stage: {expected_stage}\n"
        f"- current_round: {current_round}\n"
        f"- workflow_goal: {str(workflow_goal or '').strip()}\n"
        f"- previous_branch: {str((replan_context or {}).get('previous_branch') or '')}\n"
        f"- previous_candidate_parameters: {json.dumps((replan_context or {}).get('previous_candidate_parameters') or [], ensure_ascii=True)}\n"
        f"- previous_candidate_value_directions: {json.dumps((replan_context or {}).get('previous_candidate_value_directions') or [], ensure_ascii=True)}\n"
        f"- branch_choice_reason_hint: {str((replan_context or {}).get('branch_choice_reason') or '')}\n"
        f"- guided_search_observation: {json.dumps((replan_context or {}).get('guided_search_observation') or {}, ensure_ascii=True)}\n"
        f"- replan_budget_total_hint: {int((replan_context or {}).get('replan_budget_total') or 0)}\n"
        f"- replan_budget_for_branch_diagnosis_hint: {int((replan_context or {}).get('replan_budget_for_branch_diagnosis') or 0)}\n"
        f"- replan_budget_for_branch_escape_hint: {int((replan_context or {}).get('replan_budget_for_branch_escape') or 0)}\n"
        f"- replan_budget_for_resolution_hint: {int((replan_context or {}).get('replan_budget_for_resolution') or 0)}\n"
        f"- suggested_actions: {json.dumps(repair_actions, ensure_ascii=True)}\n"
        f"- error_excerpt: {error_excerpt}\n"
        f"{planner_experience_block}"
        "Model text below:\n"
        "-----BEGIN_MODEL-----\n"
        f"{original_text}\n"
        "-----END_MODEL-----\n"
    )
    return prompt, planner_contract


def estimate_prompt_token_count(text: str) -> int:
    raw = str(text or "").strip()
    if not raw:
        return 0
    return max(1, int(math.ceil(len(raw) / 4.0)))


def audit_planner_prompt_surface(
    *,
    prompt: str,
    workflow_goal: str,
    error_excerpt: str,
) -> dict:
    raw_prompt = str(prompt or "")
    prefix = raw_prompt.split("Model text below:\n", 1)[0]
    workflow_goal_text = str(workflow_goal or "").strip()
    error_text = str(error_excerpt or "")
    return {
        "workflow_goal_reanchoring_observed": bool(workflow_goal_text) and workflow_goal_text in raw_prompt,
        "dynamic_system_prompt_field_audit_result": {
            "static_prefix_stable": not any(
                [
                    bool(_TIMESTAMP_PATTERN.search(prefix)),
                    bool(_TASK_ID_PATTERN.search(prefix)),
                    bool(_ABSOLUTE_PATH_PATTERN.search(prefix)),
                ]
            ),
            "dynamic_timestamp_found": bool(_TIMESTAMP_PATTERN.search(prefix)),
            "dynamic_task_id_found": bool(_TASK_ID_PATTERN.search(prefix)),
            "absolute_path_found": bool(_ABSOLUTE_PATH_PATTERN.search(prefix)),
        },
        "full_omc_error_propagation_observed": bool(error_text) and error_text in raw_prompt,
        "prompt_token_estimate": estimate_prompt_token_count(raw_prompt),
    }


# ---------------------------------------------------------------------------
# Budget-gated LLM request sender
# ---------------------------------------------------------------------------

def send_with_budget(
    adapter: "LLMProviderAdapter",  # type: ignore[name-defined]
    prompt: str,
    config: "LLMProviderConfig",  # type: ignore[name-defined]
) -> tuple[str, str]:
    """Send a prompt through the adapter with budget-gated retry on 429.

    Integrates the adapter's single-shot send with the budget tracking
    and exponential backoff retry loop for rate-limited responses.

    Returns:
        Tuple of (response_text, error_string). Empty error means success.
    """
    cfg = _live_budget_config()
    while True:
        allowed, _ledger = _reserve_live_request(cfg)
        if not allowed:
            return "", "live_request_budget_exceeded"
        text, err = adapter.send_text_request(prompt, config)
        if not err:
            _record_live_request_success(cfg)
            return text, ""
        if "_rate_limited" in err:
            stop_reason, _ledger = _record_live_request_429(cfg)
            if stop_reason:
                return "", stop_reason
            continue
        return "", err


# ---------------------------------------------------------------------------
# Round constraints (prompt modifier for failure type / round index)
# ---------------------------------------------------------------------------

def llm_round_constraints(*, failure_type: str, current_round: int) -> str:
    """Return extra prompt constraints for the given failure type and round."""
    failure = str(failure_type or "").strip().lower()
    try:
        round_idx = max(1, int(current_round))
    except Exception:
        round_idx = 1
    if failure in {
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    }:
        source_mode_constraints = ""
        if behavioral_robustness_source_mode() != "source_aware":
            source_mode_constraints = (
                "- This run is source-blind; do not restore the model to the source version and do not copy source text verbatim.\n"
                "- Infer a localized numeric repair from the current model and observed robustness miss only.\n"
            )
        return (
            "- This is a behavioral robustness task; preserve the existing component declarations and connect structure.\n"
            "- Do not add or remove components, connectors, extends clauses, outputs, or equations unrelated to the failing parameters.\n"
            "- Restrict edits to existing numeric parameters, timing values, gains, offsets, widths, periods, thresholds, or initial-condition shaping values.\n"
            "- Do not invent new parameter names on Modelica.Blocks.Logical.Switch or other existing components; only edit parameters that already appear in the source text.\n"
            "- Do not perform broad source rewrites or declaration-level cleanup; keep the model compile-safe while improving robustness across neighboring scenarios.\n"
            + source_mode_constraints
            + (
                "- In round 1, patch only one localized parameter cluster and rerun the scenario set before broader edits.\n"
                if round_idx == 1
                else ""
            )
        )
    if failure not in {"cascading_structural_failure", "coupled_conflict_failure", "false_friend_patch_trap"}:
        return ""
    if round_idx != 1:
        return ""
    return (
        "- This is a multi-round repair task; in round 1 fix only the first exposed failure layer.\n"
        "- Do not rewrite the whole model or restore all suspicious changes at once.\n"
        "- Limit the patch to one localized repair cluster and preserve other suspicious edits for later rounds.\n"
        "- Do not perform broad cleanup, broad source restoration, or multi-site semantic normalization in round 1.\n"
    )


# ---------------------------------------------------------------------------
# Unified repair-text generation (Adapter Unification Pattern)
# ---------------------------------------------------------------------------

def llm_repair_model_text(
    *,
    planner_backend: str,
    original_text: str,
    failure_type: str,
    expected_stage: str,
    error_excerpt: str,
    repair_actions: list[str],
    model_name: str,
    workflow_goal: str = "",
    current_round: int = 1,
) -> tuple[str | None, str, str]:
    """Generate a repaired model text via the resolved LLM provider.

    This is the single canonical implementation for text-level repair.
    Provider-specific wrappers (gemini_repair_model_text,
    openai_repair_model_text) delegate here via Adapter Unification Pattern.

    Returns:
        Tuple of (patched_text | None, error_string, resolved_provider).
    """
    from .llm_provider_adapter import resolve_provider_adapter
    adapter, config = resolve_provider_adapter(planner_backend)
    provider = config.provider_name
    if provider == "rule":
        return None, "rule_backend_selected", "rule"
    if not config.api_key:
        return None, f"{provider}_api_key_missing", provider
    if not config.model:
        return None, f"{provider}_model_missing", provider
    prompt_constraints = llm_round_constraints(
        failure_type=failure_type,
        current_round=current_round,
    )
    prompt = (
        "You are fixing a Modelica model.\n"
        "Return ONLY JSON object with keys: patched_model_text, rationale.\n"
        "Constraints:\n"
        "- Keep model name unchanged.\n"
        "- Keep edits minimal and compile-oriented.\n"
        "- Do not output markdown.\n"
        f"{prompt_constraints}"
        f"- model_name: {model_name}\n"
        f"- failure_type: {failure_type}\n"
        f"- expected_stage: {expected_stage}\n"
        f"- workflow_goal: {str(workflow_goal or '').strip()}\n"
        f"- error_excerpt: {error_excerpt}\n"
        f"- suggested_actions: {json.dumps(repair_actions, ensure_ascii=True)}\n"
        "Model text below:\n"
        "-----BEGIN_MODEL-----\n"
        f"{original_text}\n"
        "-----END_MODEL-----\n"
    )
    text, err = send_with_budget(adapter, prompt, config)
    if err:
        return None, err, provider
    payload = _extract_json_object_impl(text, strict=False)
    patched = payload.get("patched_model_text")
    if not isinstance(patched, str) or not patched.strip():
        return None, f"{provider}_missing_patched_model_text", provider
    return patched, "", provider


def gemini_repair_model_text(
    *,
    original_text: str,
    failure_type: str,
    expected_stage: str,
    error_excerpt: str,
    repair_actions: list[str],
    model_name: str,
    workflow_goal: str = "",
    current_round: int = 1,
) -> tuple[str | None, str]:
    """Gemini-specific repair wrapper.  Delegates to llm_repair_model_text.

    Kept for backward compatibility with existing call sites and tests.
    Returns (patched_text | None, error_string) without the provider field.
    """
    patched, err, _provider = llm_repair_model_text(
        planner_backend="gemini",
        original_text=original_text,
        failure_type=failure_type,
        expected_stage=expected_stage,
        error_excerpt=error_excerpt,
        repair_actions=repair_actions,
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=current_round,
    )
    return patched, err


def openai_repair_model_text(
    *,
    original_text: str,
    failure_type: str,
    expected_stage: str,
    error_excerpt: str,
    repair_actions: list[str],
    model_name: str,
    workflow_goal: str = "",
    current_round: int = 1,
) -> tuple[str | None, str]:
    """OpenAI-specific repair wrapper.  Delegates to llm_repair_model_text.

    Kept for backward compatibility with existing call sites and tests.
    Returns (patched_text | None, error_string) without the provider field.
    """
    patched, err, _provider = llm_repair_model_text(
        planner_backend="openai",
        original_text=original_text,
        failure_type=failure_type,
        expected_stage=expected_stage,
        error_excerpt=error_excerpt,
        repair_actions=repair_actions,
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=current_round,
    )
    return patched, err


# ---------------------------------------------------------------------------
# Multistep plan generation
# ---------------------------------------------------------------------------

def llm_generate_repair_plan(
    *,
    planner_backend: str,
    original_text: str,
    failure_type: str,
    expected_stage: str,
    error_excerpt: str,
    repair_actions: list[str],
    model_name: str,
    workflow_goal: str = "",
    current_round: int,
    stage_context: dict,
    llm_reason: str,
    request_kind: str = "plan",
    replan_context: dict | None = None,
    planner_experience_context: dict | None = None,
) -> tuple[dict | None, str, str]:
    """Generate a structured repair plan (or replan) via LLM.

    Returns:
        Tuple of (plan_payload | None, error_string, resolved_provider).
    """
    from .llm_provider_adapter import resolve_provider_adapter
    adapter, config = resolve_provider_adapter(planner_backend)
    provider = config.provider_name
    if provider == "rule":
        return None, "rule_backend_selected", "rule"
    if not config.api_key:
        return None, f"{provider}_api_key_missing", provider
    if not config.model:
        return None, f"{provider}_model_missing", provider
    from .agent_modelica_prompt_surface_v1 import build_planner_prompt_surface

    prompt, _planner_contract = build_planner_prompt_surface(
        original_text=original_text,
        failure_type=failure_type,
        expected_stage=expected_stage,
        error_excerpt=error_excerpt,
        repair_actions=repair_actions,
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=current_round,
        stage_context=stage_context,
        llm_reason=llm_reason,
        request_kind=request_kind,
        replan_context=replan_context,
        resolved_provider=provider,
        planner_experience_context=planner_experience_context,
    )
    prompt_audit = audit_planner_prompt_surface(
        prompt=prompt,
        workflow_goal=workflow_goal,
        error_excerpt=error_excerpt,
    )
    text, err = send_with_budget(adapter, prompt, config)
    if err:
        return None, err, provider
    payload = _extract_json_object_impl(text, strict=False)
    if not payload:
        return None, f"{provider}_missing_repair_plan", provider
    payload["_prompt_surface_audit"] = prompt_audit
    return payload, "", provider
