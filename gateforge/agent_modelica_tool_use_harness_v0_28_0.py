from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_l2_plan_replan_engine_v1 import resolve_llm_provider
from .agent_modelica_observation_contract_v0_26_1 import build_observation_event, validate_observation_event
from .agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from .llm_provider_adapter import (
    LLMProviderAdapter,
    LLMProviderConfig,
    ToolResponse,
    resolve_provider_adapter,
)
from .agent_modelica_structural_tools_v0_28_1 import (
    dispatch_structural_tool,
    get_structural_tool_defs,
)
from .agent_modelica_connector_balance_tool_v0_29_9 import (
    dispatch_connector_balance_tool,
    get_connector_balance_tool_defs,
)
from .agent_modelica_replaceable_partial_tool_v0_29_16 import (
    dispatch_replaceable_partial_tool,
    get_replaceable_partial_tool_defs,
)
from .agent_modelica_replaceable_policy_tool_v0_29_18 import (
    dispatch_replaceable_policy_tool,
    get_replaceable_policy_tool_defs,
)
from .agent_modelica_candidate_critique_tool_v0_30_0 import (
    dispatch_candidate_critique_tool,
    get_candidate_critique_tool_defs,
)
from .agent_modelica_structure_strategy_tool_v0_30_10 import (
    dispatch_structure_strategy_tool,
    get_structure_strategy_tool_defs,
)
from .agent_modelica_structure_coverage_tool_v0_31_0 import (
    dispatch_structure_coverage_tool,
    get_structure_coverage_tool_defs,
)
from .agent_modelica_connector_contract_tool_v0_32_6 import (
    dispatch_connector_contract_tool,
    get_connector_contract_tool_defs,
)
from .agent_modelica_connector_flow_semantics_tool_v0_34_15 import (
    dispatch_connector_flow_semantics_tool,
    get_connector_flow_semantics_tool_defs,
)
from .agent_modelica_connector_flow_state_tool_v0_35_9 import (
    dispatch_connector_flow_state_tool,
    get_connector_flow_state_tool_defs,
)
from .agent_modelica_repair_hypothesis_tool_v0_35_12 import (
    dispatch_repair_hypothesis_tool,
    get_repair_hypothesis_tool_defs,
)
from .agent_modelica_arrayed_shared_bus_tool_v0_35_18 import (
    dispatch_arrayed_shared_bus_tool,
    get_arrayed_shared_bus_tool_defs,
)
from .agent_modelica_omc_unmatched_flow_tool_v0_35_20 import (
    dispatch_omc_unmatched_flow_tool,
    get_omc_unmatched_flow_tool_defs,
)
from .agent_modelica_residual_hypothesis_consistency_tool_v0_35_21 import (
    dispatch_residual_hypothesis_consistency_tool,
    get_residual_hypothesis_consistency_tool_defs,
)
from .agent_modelica_equation_delta_portfolio_tool_v0_35_26 import (
    dispatch_equation_delta_portfolio_tool,
    get_equation_delta_portfolio_tool_defs,
)
from .agent_modelica_candidate_preference_tool_v0_35_29 import (
    dispatch_candidate_preference_tool,
    get_candidate_preference_tool_defs,
)
from .agent_modelica_final_decision_record_tool_v0_34_13 import (
    dispatch_final_decision_record_tool,
    get_final_decision_record_tool_defs,
)
from .agent_modelica_memory_selection_tool_v0_34_4 import (
    dispatch_memory_selection_tool,
    get_memory_selection_tool_defs,
)
from .agent_modelica_reusable_contract_oracle_tool_v0_34_10 import (
    dispatch_reusable_contract_oracle_tool,
    get_reusable_contract_oracle_tool_defs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "tool_use_harness_v0_28_0"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

BASE_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "check_model",
        "description": (
            "Run OMC checkModel on the provided Modelica model text and return raw compiler output. "
            "Returns check results, equation counts, and any errors."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {
                    "type": "string",
                    "description": "Complete Modelica model source code to check.",
                },
            },
            "required": ["model_text"],
        },
    },
    {
        "name": "simulate_model",
        "description": (
            "Run OMC simulate on the provided Modelica model text and return simulation output. "
            "Runs checkModel first, then simulate with given stopTime and intervals."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {
                    "type": "string",
                    "description": "Complete Modelica model source code to simulate.",
                },
                "stop_time": {
                    "type": "number",
                    "description": "Simulation stop time in seconds. Default: 0.05",
                },
                "intervals": {
                    "type": "integer",
                    "description": "Number of simulation intervals. Default: 100",
                },
            },
            "required": ["model_text"],
        },
    },
    {
        "name": "submit_final",
        "description": (
            "Submit the final repaired model for evaluation. "
            "Call this when you believe the model is correct. "
            "The submitted model will be evaluated with checkModel and simulate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {
                    "type": "string",
                    "description": "The final complete Modelica model source code.",
                },
            },
            "required": ["model_text"],
        },
    },
]

# Default profile keeps the v0.28.1 structural tools enabled.
TOOL_DEFS = BASE_TOOL_DEFS + get_structural_tool_defs()
CONNECTOR_TOOL_DEFS = TOOL_DEFS + get_connector_balance_tool_defs()
CONNECTOR_CONTRACT_TOOL_DEFS = BASE_TOOL_DEFS + get_connector_contract_tool_defs()
CONNECTOR_FLOW_SEMANTICS_TOOL_DEFS = BASE_TOOL_DEFS + get_connector_flow_semantics_tool_defs()
CONNECTOR_FLOW_SEMANTICS_FINAL_DECISION_TOOL_DEFS = (
    CONNECTOR_FLOW_SEMANTICS_TOOL_DEFS + get_final_decision_record_tool_defs()
)
CONNECTOR_FLOW_STATE_TOOL_DEFS = BASE_TOOL_DEFS + get_connector_flow_state_tool_defs()
CONNECTOR_FLOW_HYPOTHESIS_TOOL_DEFS = (
    CONNECTOR_FLOW_STATE_TOOL_DEFS + get_repair_hypothesis_tool_defs()
)
CONNECTOR_FLOW_ARRAYED_BUS_TOOL_DEFS = (
    CONNECTOR_FLOW_HYPOTHESIS_TOOL_DEFS + get_arrayed_shared_bus_tool_defs()
)
CONNECTOR_FLOW_OMC_NAMED_TOOL_DEFS = (
    CONNECTOR_FLOW_ARRAYED_BUS_TOOL_DEFS + get_omc_unmatched_flow_tool_defs()
)
CONNECTOR_FLOW_RESIDUAL_CONSISTENCY_TOOL_DEFS = (
    CONNECTOR_FLOW_OMC_NAMED_TOOL_DEFS + get_residual_hypothesis_consistency_tool_defs()
)
CONNECTOR_FLOW_DELTA_PORTFOLIO_TOOL_DEFS = (
    CONNECTOR_FLOW_RESIDUAL_CONSISTENCY_TOOL_DEFS + get_equation_delta_portfolio_tool_defs()
)
CONNECTOR_FLOW_CANDIDATE_PREFERENCE_TOOL_DEFS = (
    CONNECTOR_FLOW_DELTA_PORTFOLIO_TOOL_DEFS + get_candidate_preference_tool_defs()
)
SEMANTIC_MEMORY_SELECTION_TOOL_DEFS = BASE_TOOL_DEFS + get_memory_selection_tool_defs()
REUSABLE_CONTRACT_ORACLE_TOOL_DEFS = BASE_TOOL_DEFS + get_reusable_contract_oracle_tool_defs()
REUSABLE_CONTRACT_ORACLE_FINAL_DECISION_TOOL_DEFS = (
    REUSABLE_CONTRACT_ORACLE_TOOL_DEFS + get_final_decision_record_tool_defs()
)
SEMANTIC_TOOL_NAMES = {"get_unmatched_vars", "causalized_form"}
SEMANTIC_TOOL_DEFS = BASE_TOOL_DEFS + [
    tool for tool in get_structural_tool_defs() if str(tool.get("name") or "") in SEMANTIC_TOOL_NAMES
]
REPLACEABLE_TOOL_DEFS = BASE_TOOL_DEFS + get_replaceable_partial_tool_defs()
REPLACEABLE_POLICY_TOOL_DEFS = REPLACEABLE_TOOL_DEFS + get_replaceable_policy_tool_defs()
REPLACEABLE_CRITIQUE_TOOL_DEFS = REPLACEABLE_POLICY_TOOL_DEFS + get_candidate_critique_tool_defs()
REPLACEABLE_STRATEGY_TOOL_DEFS = REPLACEABLE_CRITIQUE_TOOL_DEFS + get_structure_strategy_tool_defs()
REPLACEABLE_COVERAGE_TOOL_DEFS = REPLACEABLE_CRITIQUE_TOOL_DEFS + get_structure_coverage_tool_defs()


def get_tool_defs(tool_profile: str = "structural") -> list[dict[str, Any]]:
    if tool_profile == "base":
        return list(BASE_TOOL_DEFS)
    if tool_profile == "base_submit_checkpoint":
        return list(BASE_TOOL_DEFS)
    if tool_profile == "base_candidate_portfolio_checkpoint":
        return list(BASE_TOOL_DEFS)
    if tool_profile == "semantic":
        return list(SEMANTIC_TOOL_DEFS)
    if tool_profile == "semantic_memory_selection":
        return list(SEMANTIC_MEMORY_SELECTION_TOOL_DEFS)
    if tool_profile == "reusable_contract_oracle":
        return list(REUSABLE_CONTRACT_ORACLE_TOOL_DEFS)
    if tool_profile == "reusable_contract_oracle_final_decision":
        return list(REUSABLE_CONTRACT_ORACLE_FINAL_DECISION_TOOL_DEFS)
    if tool_profile == "reusable_contract_oracle_submit_checkpoint":
        return list(REUSABLE_CONTRACT_ORACLE_FINAL_DECISION_TOOL_DEFS)
    if tool_profile == "replaceable":
        return list(REPLACEABLE_TOOL_DEFS)
    if tool_profile == "replaceable_policy":
        return list(REPLACEABLE_POLICY_TOOL_DEFS)
    if tool_profile == "replaceable_policy_multicandidate":
        return list(REPLACEABLE_POLICY_TOOL_DEFS)
    if tool_profile == "replaceable_policy_submit_discipline":
        return list(REPLACEABLE_POLICY_TOOL_DEFS)
    if tool_profile == "replaceable_policy_oracle_boundary":
        return list(REPLACEABLE_POLICY_TOOL_DEFS)
    if tool_profile == "replaceable_policy_candidate_critique":
        return list(REPLACEABLE_CRITIQUE_TOOL_DEFS)
    if tool_profile == "replaceable_policy_candidate_critique_required":
        return list(REPLACEABLE_CRITIQUE_TOOL_DEFS)
    if tool_profile == "replaceable_policy_candidate_critique_checkpoint":
        return list(REPLACEABLE_CRITIQUE_TOOL_DEFS)
    if tool_profile == "replaceable_policy_multicandidate_checkpoint":
        return list(REPLACEABLE_CRITIQUE_TOOL_DEFS)
    if tool_profile == "replaceable_policy_structure_plan_checkpoint":
        return list(REPLACEABLE_STRATEGY_TOOL_DEFS)
    if tool_profile == "replaceable_policy_structure_coverage_checkpoint":
        return list(REPLACEABLE_COVERAGE_TOOL_DEFS)
    if tool_profile == "connector":
        return list(CONNECTOR_TOOL_DEFS)
    if tool_profile == "connector_contract":
        return list(CONNECTOR_CONTRACT_TOOL_DEFS)
    if tool_profile == "connector_flow_semantics":
        return list(CONNECTOR_FLOW_SEMANTICS_TOOL_DEFS)
    if tool_profile == "connector_flow_submit_checkpoint":
        return list(CONNECTOR_FLOW_SEMANTICS_FINAL_DECISION_TOOL_DEFS)
    if tool_profile == "connector_flow_state_checkpoint":
        return list(CONNECTOR_FLOW_STATE_TOOL_DEFS)
    if tool_profile == "connector_flow_hypothesis_checkpoint":
        return list(CONNECTOR_FLOW_HYPOTHESIS_TOOL_DEFS)
    if tool_profile == "connector_flow_minimal_contract_checkpoint":
        return list(CONNECTOR_FLOW_HYPOTHESIS_TOOL_DEFS)
    if tool_profile == "connector_flow_arrayed_bus_checkpoint":
        return list(CONNECTOR_FLOW_ARRAYED_BUS_TOOL_DEFS)
    if tool_profile == "connector_flow_omc_named_checkpoint":
        return list(CONNECTOR_FLOW_OMC_NAMED_TOOL_DEFS)
    if tool_profile == "connector_flow_residual_consistency_checkpoint":
        return list(CONNECTOR_FLOW_RESIDUAL_CONSISTENCY_TOOL_DEFS)
    if tool_profile == "connector_flow_residual_revision_checkpoint":
        return list(CONNECTOR_FLOW_RESIDUAL_CONSISTENCY_TOOL_DEFS)
    if tool_profile == "connector_flow_delta_portfolio_checkpoint":
        return list(CONNECTOR_FLOW_DELTA_PORTFOLIO_TOOL_DEFS)
    if tool_profile == "connector_flow_delta_coverage_checkpoint":
        return list(CONNECTOR_FLOW_DELTA_PORTFOLIO_TOOL_DEFS)
    if tool_profile == "connector_flow_delta_execution_checkpoint":
        return list(CONNECTOR_FLOW_DELTA_PORTFOLIO_TOOL_DEFS)
    if tool_profile == "connector_flow_candidate_preference_checkpoint":
        return list(CONNECTOR_FLOW_CANDIDATE_PREFERENCE_TOOL_DEFS)
    return list(TOOL_DEFS)


def get_tool_profile_guidance(tool_profile: str = "structural") -> str:
    if tool_profile == "base":
        return ""
    if tool_profile == "base_submit_checkpoint":
        return (
            "Use transparent submit discipline. If a candidate passes check_model with simulation success or passes "
            "simulate_model, do not keep exploring speculative alternatives. Call submit_final with that exact "
            "successful candidate unless you can name a concrete remaining requirement that the tool output did not "
            "validate. The harness will not auto-submit, select candidates, or generate patches.\n"
        )
    if tool_profile == "base_candidate_portfolio_checkpoint":
        return (
            "Use transparent candidate discovery plus submit discipline. After a failed check_model or simulate_model, "
            "do not repeat the same repair shape with small wording changes. Try a structurally distinct candidate "
            "before giving up: for example, compare whether the issue belongs in a reusable component contract, a "
            "local implementation, or the surrounding connection/topology. Test each candidate with OMC yourself. "
            "If a candidate passes check_model with simulation success or passes simulate_model, call submit_final "
            "with that exact successful model_text unless you can name a concrete remaining requirement that the "
            "tool output did not validate. The harness will not auto-submit, select candidates, or generate patches.\n"
        )
    if tool_profile == "semantic":
        return (
            "Two diagnostic tools are available for hard semantic Modelica cases. Each call costs tokens; "
            "use at most one diagnostic pass before trying a repair unless the compiler output is ambiguous:\n"
            "- get_unmatched_vars: use when check_model reports under-determined systems and the missing variable is not obvious.\n"
            "- causalized_form: use when acausal equations make dependencies hard to read.\n"
        )
    if tool_profile == "semantic_memory_selection":
        return (
            "Semantic memory units may be present in the external context. Before testing a second candidate, "
            "call record_semantic_memory_selection to record which memory unit you choose to use or reject and why. "
            "This tool will not retrieve memory, rank memory, generate patches, select candidates, or submit. "
            "You must still write and test the next candidate yourself.\n"
        )
    if tool_profile == "reusable_contract_oracle":
        return (
            "A reusable-contract oracle diagnostic is available. If a candidate passes OMC but you are unsure whether "
            "it preserves a reusable probe/adapter contract, call reusable_contract_oracle_diagnostic with that same "
            "candidate model_text. The diagnostic is audit-only: it does not generate patches, select candidates, "
            "or submit. You must still decide whether to call submit_final yourself.\n"
        )
    if tool_profile == "reusable_contract_oracle_final_decision":
        return (
            "A reusable-contract oracle diagnostic and a final-decision record tool are available. If a candidate "
            "passes OMC/simulation and reusable_contract_oracle_diagnostic, call record_final_decision_rationale "
            "before continuing search or submitting. The record tool is audit-only: it does not submit, select a "
            "candidate, generate patches, or change the model. If your recorded decision is submit, you must still "
            "call submit_final yourself.\n"
        )
    if tool_profile == "reusable_contract_oracle_submit_checkpoint":
        return (
            "Use transparent submit discipline with the reusable-contract oracle. If a candidate passes check_model "
            "with simulation success or passes simulate_model, do not keep searching for a more elegant candidate. "
            "If the reusable contract is still uncertain, call reusable_contract_oracle_diagnostic on that same "
            "candidate. Then call record_final_decision_rationale with either concrete blockers or a submit decision. "
            "If no concrete blocker remains, call submit_final yourself with that same successful model_text. "
            "The harness will not auto-submit, select candidates, or generate patches.\n"
        )
    if tool_profile == "replaceable":
        return (
            "A replaceable/partial diagnostic tool is available for hard Modelica interface cases. "
            "Call replaceable_partial_diagnostic once when the model uses replaceable model declarations, "
            "constrainedby bases, partial model interfaces, or flow-current equations in derived models. "
            "The tool reports structure and risks only; you must still decide and test the patch.\n"
        )
    if tool_profile == "replaceable_policy":
        return (
            "Two replaceable/partial diagnostic tools are available. "
            "Call replaceable_partial_diagnostic once to inspect the base/actual structure. "
            "Call replaceable_partial_policy_check before repeating a patch that moves flow-current equations into "
            "a partial constrainedby base or duplicates derived flow equations. "
            "Both tools are diagnostic-only; they do not generate patches or select candidates.\n"
        )
    if tool_profile == "replaceable_policy_multicandidate":
        return (
            "Use transparent multi-candidate repair. You must propose and test distinct candidate repairs yourself. "
            "For hard replaceable/partial cases, try to test at least two structurally different candidates with "
            "check_model before submit_final, unless the first candidate fully passes and is clearly correct. "
            "Call replaceable_partial_diagnostic once to inspect the base/actual structure. "
            "Call replaceable_partial_policy_check before repeating a patch that moves flow-current equations into "
            "a partial constrainedby base or duplicates derived flow equations. "
            "The harness will only run tools you call; it will not generate patches, select candidates, or hide failed attempts.\n"
        )
    if tool_profile == "replaceable_policy_submit_discipline":
        return (
            "Use transparent multi-candidate repair, but preserve submit discipline. "
            "If a candidate model has already passed check_model with simulation success or has passed simulate_model, "
            "do not keep exploring speculative alternatives. Call submit_final with that exact successful candidate unless "
            "you can name a concrete remaining requirement that the tool output did not validate. "
            "Call replaceable_partial_diagnostic once to inspect the base/actual structure. "
            "Call replaceable_partial_policy_check before repeating a patch that moves flow-current equations into "
            "a partial constrainedby base or duplicates derived flow equations. "
            "The harness will not auto-submit; you must explicitly call submit_final.\n"
        )
    if tool_profile == "replaceable_policy_oracle_boundary":
        return (
            "Use transparent multi-candidate repair with explicit oracle-boundary discipline. "
            "If a candidate has passed check_model with simulation success or has passed simulate_model, treat it as "
            "acceptable for this benchmark unless you can cite a specific task constraint or oracle requirement it violates. "
            "Do not reject a successful candidate based only on subjective physical concerns that are not stated in the task. "
            "If you reject a successful candidate, name the exact constraint it violates before trying another candidate. "
            "Otherwise call submit_final with that exact successful candidate. "
            "The harness will not auto-submit; you must explicitly call submit_final.\n"
        )
    if tool_profile == "replaceable_policy_candidate_critique":
        return (
            "Use transparent candidate critique. If a candidate has passed check_model with simulation success or "
            "passed simulate_model, and you are unsure whether to submit, call candidate_acceptance_critique with "
            "omc_passed=true, the explicit task constraints, and your concrete concern. "
            "The critique tool only evaluates whether your concern is tied to an explicit task/oracle boundary; "
            "it will not generate a patch, select a candidate, or submit. "
            "After receiving the critique, you must decide whether to call submit_final yourself.\n"
        )
    if tool_profile == "replaceable_policy_candidate_critique_required":
        return (
            "Use transparent candidate critique with strict discoverability. "
            "Whenever check_model or simulate_model shows a successful simulation result for a candidate, you have two choices: "
            "call submit_final with that same candidate, or call candidate_acceptance_critique before trying any other candidate. "
            "Do not abandon a successful candidate without first calling candidate_acceptance_critique with omc_passed=true, "
            "the explicit task constraints, and your concrete concern. "
            "The critique tool does not generate patches, select candidates, or submit; after it returns, you must decide the next tool call yourself.\n"
        )
    if tool_profile == "replaceable_policy_candidate_critique_checkpoint":
        return (
            "Use transparent candidate critique with an explicit checkpoint. "
            "Whenever the harness tells you that a candidate has passed OMC check/simulation evidence, your next action must be one of: "
            "call submit_final with the same successful candidate, or call candidate_acceptance_critique with omc_passed=true, "
            "the explicit task constraints, and your concrete concern. "
            "The checkpoint is advisory and transparent; the harness will not generate patches, select candidates, or submit for you.\n"
        )
    if tool_profile == "replaceable_policy_multicandidate_checkpoint":
        return (
            "Use transparent multi-candidate discovery with an explicit checkpoint. "
            "Before giving up on hard replaceable/partial cases, test at least two structurally different repair candidates with check_model "
            "unless one candidate passes OMC evidence first. Distinct means a different interface/equation placement strategy, not only renaming. "
            "Call replaceable_partial_diagnostic once to inspect the base/actual structure. "
            "Call replaceable_partial_policy_check before repeating a patch that moves flow-current equations into a partial constrainedby base "
            "or duplicates derived flow equations. "
            "Whenever the harness tells you that a candidate has passed OMC check/simulation evidence, your next action must be one of: "
            "call submit_final with the same successful candidate, or call candidate_acceptance_critique with omc_passed=true and your concrete concern. "
            "The harness will not generate patches, select candidates, hide failed attempts, or submit for you.\n"
        )
    if tool_profile == "replaceable_policy_structure_plan_checkpoint":
        return (
            "Use transparent structural strategy planning with checkpoint discipline. "
            "Before testing a second candidate, or after two failed candidates, call record_structure_strategies with "
            "two or three structurally distinct repair strategies and the strategy you will test next. "
            "Distinct means changing interface/equation placement, connector contract, replaceable/constrainedby structure, "
            "or flow-equation ownership, not only renaming or formatting. "
            "Call replaceable_partial_diagnostic once to inspect base/actual structure. "
            "Call replaceable_partial_policy_check before repeating a patch that moves flow-current equations into a partial constrainedby base "
            "or duplicates derived flow equations. "
            "Whenever the harness tells you that a candidate has passed OMC check/simulation evidence, your next action must be one of: "
            "call submit_final with the same successful candidate, or call candidate_acceptance_critique with omc_passed=true and your concrete concern. "
            "The strategy tool only records your plan; the harness will not generate patches, select candidates, hide failed attempts, or submit for you.\n"
        )
    if tool_profile == "replaceable_policy_structure_coverage_checkpoint":
        return (
            "Use transparent structure coverage diagnostics with checkpoint discipline. "
            "After at least two failed candidate checks, call structure_coverage_diagnostic with the candidate model_text values you already tested. "
            "Use it to see which structural clusters have been covered, especially flow-equation ownership, partial base structure, "
            "replaceable/constrainedby declarations, and connector contract shape. "
            "The coverage tool does not generate patches, choose candidates, or tell you which structure is correct. "
            "You must still write and test the next candidate yourself. "
            "Whenever the harness tells you that a candidate has passed OMC check/simulation evidence, your next action must be one of: "
            "call submit_final with the same successful candidate, or call candidate_acceptance_critique with omc_passed=true and your concrete concern. "
            "The harness will not generate patches, select candidates, hide failed attempts, or submit for you.\n"
        )
    if tool_profile == "connector_contract":
        return (
            "A narrow Modelica connector contract diagnostic is available. "
            "For arrayed connector buses, reusable probe/adapter interfaces, replaceable partial contracts, "
            "or repeated under/over-constrained flow ownership failures, call connector_contract_diagnostic once. "
            "It reports semantic risks around connection sets, flow variable ownership, and reusable interface contracts. "
            "It is diagnostic-only: it does not generate patches, choose candidates, or submit. "
            "You must still write and test the repair yourself with check_model and submit_final.\n"
        )
    if tool_profile == "connector_flow_semantics":
        return (
            "A connector-flow semantic diagnostic is available. Call connector_flow_semantics_diagnostic after "
            "OMC reports underdetermined, overdetermined, singular, or balanced-equation-count-without-simulation "
            "outcomes involving connector flow variables. Pass the candidate model_text and, when available, the "
            "recent OMC output as omc_output. The tool reports flow-equation patterns and semantic risks only; "
            "it does not generate patches, choose candidates, or submit. You must still write and test repairs "
            "yourself with check_model/simulate_model and submit_final.\n"
        )
    if tool_profile == "connector_flow_submit_checkpoint":
        return (
            "Use connector-flow diagnostics with transparent submit discipline. Call connector_flow_semantics_diagnostic "
            "after OMC reports underdetermined, overdetermined, singular, or balanced-equation-count-without-simulation "
            "outcomes involving connector flow variables. If a candidate then passes check_model with simulation success "
            "or passes simulate_model, do not keep searching for a more symmetric or elegant candidate unless you can "
            "name a concrete task constraint it violates. You may run simulate_model once for confirmation, call "
            "record_final_decision_rationale with concrete blockers or a submit decision, or call submit_final yourself. "
            "The harness will not auto-submit, select candidates, or generate patches.\n"
        )
    if tool_profile == "connector_flow_state_checkpoint":
        return (
            "Use connector-flow semantic state diagnostics with transparent submit discipline. "
            "Call connector_flow_state_diagnostic after the first model-check failure to inspect connection sets, "
            "flow-balance participants, and where flow equations are owned. The diagnostic reports facts only; it "
            "does not generate patches or choose candidates. If a candidate passes check_model with simulation "
            "success or passes simulate_model, call submit_final with that same successful model_text unless a "
            "concrete task requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_hypothesis_checkpoint":
        return (
            "Use connector-flow semantic state diagnostics plus explicit repair hypothesis recording. "
            "After the first model-check failure, call connector_flow_state_diagnostic. Before testing a nontrivial "
            "repair candidate, call record_repair_hypothesis to state the suspected semantic type, target boundary, "
            "candidate strategy, expected equation-count change, and a different fallback hypothesis. The hypothesis "
            "tool is audit-only: it does not generate patches, choose candidates, or submit. If a candidate passes "
            "check_model with simulation success or passes simulate_model, call submit_final with that same successful "
            "model_text unless a concrete task requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_minimal_contract_checkpoint":
        return (
            "Use connector-flow semantic state diagnostics plus minimal-contract hypothesis discipline. "
            "After the first model-check failure, call connector_flow_state_diagnostic. Before testing a nontrivial "
            "repair candidate, call record_repair_hypothesis. In that hypothesis, avoid assuming that every probe "
            "pin current must be set to zero. State the minimal equation-count change you expect and why it should "
            "be enough to close the connector-flow contract without over-constraining the connection sets. The "
            "hypothesis tool is audit-only: it does not generate patches, choose candidates, or submit. If a "
            "candidate passes check_model with simulation success or passes simulate_model, call submit_final with "
            "that same successful model_text unless a concrete task requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_arrayed_bus_checkpoint":
        return (
            "Use connector-flow semantic state diagnostics plus arrayed shared-bus observation. "
            "After the first model-check failure, call connector_flow_state_diagnostic and "
            "arrayed_shared_bus_diagnostic. Before testing a nontrivial repair candidate, call "
            "record_repair_hypothesis. Treat a large arrayed connection set as one shared flow-balance context, "
            "not as isolated branch-local connectors. Avoid assuming every probe pin current must be set to zero; "
            "state the minimal equation-count change you expect and why it should be enough to close the "
            "connector-flow contract without over-constraining the connection sets. The diagnostics and hypothesis "
            "tool are audit-only: they do not generate patches, choose candidates, or submit. If a candidate passes "
            "check_model with simulation success or passes simulate_model, call submit_final with that same "
            "successful model_text unless a concrete task requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_omc_named_checkpoint":
        return (
            "Use connector-flow semantic state diagnostics plus compiler-named residual discipline. "
            "After the first model-check failure, call connector_flow_state_diagnostic, "
            "arrayed_shared_bus_diagnostic, and omc_unmatched_flow_diagnostic with the recent OMC output. "
            "When OMC names specific unmatched flow variables, treat those names as stronger evidence than "
            "symmetry-based guesses. Before testing a nontrivial repair candidate, call record_repair_hypothesis "
            "and state the minimal equation-count change expected from the compiler-named residual. The diagnostics "
            "and hypothesis tool are audit-only: they do not generate patches, choose candidates, or submit. If a "
            "candidate passes check_model with simulation success or passes simulate_model, call submit_final with "
            "that same successful model_text unless a concrete task requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_residual_consistency_checkpoint":
        return (
            "Use connector-flow diagnostics plus transparent residual-hypothesis consistency. "
            "After the first model-check failure, call connector_flow_state_diagnostic, "
            "arrayed_shared_bus_diagnostic, and omc_unmatched_flow_diagnostic with the recent OMC output. "
            "Before testing a nontrivial repair candidate, call record_repair_hypothesis, then call "
            "residual_hypothesis_consistency_check using the same expected equation-count delta and candidate "
            "strategy. If the consistency check says the delta exceeds compiler-named residuals, revise the "
            "hypothesis before testing. This is an audit-only critique: it does not generate patches, choose "
            "candidates, or submit. If a candidate passes check_model with simulation success or passes "
            "simulate_model, call submit_final with that same successful model_text unless a concrete task "
            "requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_residual_revision_checkpoint":
        return (
            "Use connector-flow diagnostics plus strict residual-hypothesis revision discipline. "
            "After the first model-check failure, call connector_flow_state_diagnostic, "
            "arrayed_shared_bus_diagnostic, and omc_unmatched_flow_diagnostic with the recent OMC output. "
            "Before testing a nontrivial repair candidate, call record_repair_hypothesis, then call "
            "residual_hypothesis_consistency_check using the same expected equation-count delta and candidate "
            "strategy. If the consistency check says the expected delta exceeds compiler-named residuals, do not "
            "test that candidate yet. First record a revised repair hypothesis whose expected equation-count delta "
            "matches the compiler-named residual count, then test that revised candidate. These tools are "
            "audit-only: they do not generate patches, choose candidates, or submit. If a candidate passes "
            "check_model with simulation success or passes simulate_model, call submit_final with that same "
            "successful model_text unless a concrete task requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_delta_portfolio_checkpoint":
        return (
            "Use connector-flow diagnostics plus explicit candidate portfolio discipline. "
            "After the first model-check failure, call connector_flow_state_diagnostic, "
            "arrayed_shared_bus_diagnostic, and omc_unmatched_flow_diagnostic with the recent OMC output. "
            "Before testing a nontrivial repair candidate, call record_equation_delta_candidate_portfolio with at "
            "least two structurally distinct candidate strategies and their expected equation-count deltas. Include "
            "at least one candidate whose expected delta matches the compiler-named residual count, but you must "
            "still choose, write, and test the candidate yourself. Then call record_repair_hypothesis and "
            "residual_hypothesis_consistency_check for the selected candidate. These tools are audit-only: they do "
            "not generate patches, choose candidates, or submit. If a candidate passes check_model with simulation "
            "success or passes simulate_model, call submit_final with that same successful model_text unless a "
            "concrete task requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_delta_coverage_checkpoint":
        return (
            "Use connector-flow diagnostics plus strict equation-delta coverage discipline. "
            "After the first model-check failure, call connector_flow_state_diagnostic, "
            "arrayed_shared_bus_diagnostic, and omc_unmatched_flow_diagnostic with the recent OMC output. "
            "Before testing any nontrivial repair candidate, call record_equation_delta_candidate_portfolio with at "
            "least two structurally distinct candidate strategies and their expected equation-count deltas. The "
            "portfolio must include a candidate whose expected equation-count delta exactly matches the compiler-"
            "named residual count. If your first portfolio does not include that delta, do not test yet; call "
            "record_equation_delta_candidate_portfolio again with a revised portfolio that includes it. Then call "
            "record_repair_hypothesis and residual_hypothesis_consistency_check for the selected candidate. These "
            "tools are audit-only: they do not generate patches, choose candidates, or submit. If a candidate passes "
            "check_model with simulation success or passes simulate_model, call submit_final with that same "
            "successful model_text unless a concrete task requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_delta_execution_checkpoint":
        return (
            "Use connector-flow diagnostics plus strict equation-delta coverage and execution discipline. "
            "After the first model-check failure, call connector_flow_state_diagnostic, "
            "arrayed_shared_bus_diagnostic, and omc_unmatched_flow_diagnostic with the recent OMC output. "
            "Before testing any nontrivial repair candidate, call record_equation_delta_candidate_portfolio with at "
            "least two structurally distinct candidate strategies. The portfolio must include a candidate whose "
            "expected equation-count delta exactly matches the compiler-named residual count. Then call "
            "record_repair_hypothesis and residual_hypothesis_consistency_check for the selected residual-matching "
            "candidate. Do not stop after recording the hypothesis; test the selected candidate with check_model. "
            "These tools are audit-only: they do not generate patches, choose candidates, or submit. If a candidate "
            "passes check_model with simulation success or passes simulate_model, call submit_final with that same "
            "successful model_text unless a concrete task requirement remains unvalidated.\n"
        )
    if tool_profile == "connector_flow_candidate_preference_checkpoint":
        return (
            "Use connector-flow diagnostics plus explicit candidate preference discipline. "
            "After the first model-check failure, call connector_flow_state_diagnostic, "
            "arrayed_shared_bus_diagnostic, and omc_unmatched_flow_diagnostic with the recent OMC output. "
            "Before testing any nontrivial repair candidate, call record_equation_delta_candidate_portfolio. The "
            "portfolio must include a candidate whose expected equation-count delta exactly matches the compiler-"
            "named residual count. If a residual-matching candidate conflicts with a more symmetric or cleaner "
            "candidate, call record_candidate_preference_rationale and prefer compiler residual match over style, "
            "symmetry, or reusable-contract cleanliness for the next test. Then call record_repair_hypothesis and "
            "residual_hypothesis_consistency_check for that selected candidate, and test it with check_model. These "
            "tools are audit-only: they do not generate patches, choose candidates, or submit. If a candidate passes "
            "check_model with simulation success or passes simulate_model, call submit_final with that same "
            "successful model_text unless a concrete task requirement remains unvalidated.\n"
        )
    lines = [
        "Diagnostic tools are available for complex cases. Each call costs tokens — "
        "use only when check_model output alone is insufficient:\n"
        "- get_unmatched_vars: when check_model reports multiple under-determined errors "
        "and the root variable is not obvious from the output.\n"
        "- who_defines / who_uses: when you need to trace a specific variable's defining and referencing equations.\n"
        "- declared_but_unused: only after you have changed equation references and need to find leftover declarations.\n"
        "- causalized_form: Modelica equations have no direction — a=b and b=a are the same thing, "
        "unlike normal programming. This makes dependency relationships hard to read. "
        "Call causalized_form when you need to see which variable each equation actually computes.\n"
    ]
    if tool_profile == "connector":
        lines.append(
            "- connector_balance_diagnostic: when check_model passes but simulate fails, "
            "and the model has custom connectors with direct field equations. "
            "Use it once to diagnose — you must still decide the patch.\n"
        )
    return "".join(lines)


def _strip_ws(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _extract_model_name(text: str) -> str:
    m = re.search(r"^\s*model\s+(\w+)", text, re.MULTILINE)
    if m:
        return m.group(1)
    m = re.search(r"^\s*block\s+(\w+)", text, re.MULTILINE)
    if m:
        return m.group(1)
    return "model"


def _omc_success_result(tool_name: str, result: str) -> bool:
    if tool_name not in {"check_model", "simulate_model"}:
        return False
    text = str(result or "")
    return 'resultFile = "/workspace/' in text


def _checkpoint_enabled(tool_profile: str) -> bool:
    return tool_profile in {
        "base_submit_checkpoint",
        "base_candidate_portfolio_checkpoint",
        "replaceable_policy_candidate_critique_checkpoint",
        "replaceable_policy_multicandidate_checkpoint",
        "replaceable_policy_structure_coverage_checkpoint",
        "reusable_contract_oracle_submit_checkpoint",
        "connector_flow_submit_checkpoint",
        "connector_flow_state_checkpoint",
        "connector_flow_hypothesis_checkpoint",
        "connector_flow_minimal_contract_checkpoint",
        "connector_flow_arrayed_bus_checkpoint",
        "connector_flow_omc_named_checkpoint",
        "connector_flow_residual_consistency_checkpoint",
        "connector_flow_residual_revision_checkpoint",
        "connector_flow_delta_portfolio_checkpoint",
        "connector_flow_delta_coverage_checkpoint",
        "connector_flow_delta_execution_checkpoint",
        "connector_flow_candidate_preference_checkpoint",
    }


def _checkpoint_allowed_tools(tool_profile: str) -> set[str]:
    if tool_profile == "base_submit_checkpoint":
        return {"submit_final"}
    if tool_profile == "base_candidate_portfolio_checkpoint":
        return {"submit_final"}
    if tool_profile == "reusable_contract_oracle_submit_checkpoint":
        return {
            "submit_final",
            "reusable_contract_oracle_diagnostic",
            "record_final_decision_rationale",
        }
    if tool_profile == "connector_flow_submit_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_semantics_diagnostic",
            "record_final_decision_rationale",
        }
    if tool_profile == "connector_flow_state_checkpoint":
        return {"submit_final", "simulate_model", "connector_flow_state_diagnostic"}
    if tool_profile == "connector_flow_hypothesis_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "record_repair_hypothesis",
        }
    if tool_profile == "connector_flow_minimal_contract_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "record_repair_hypothesis",
        }
    if tool_profile == "connector_flow_arrayed_bus_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "arrayed_shared_bus_diagnostic",
            "record_repair_hypothesis",
        }
    if tool_profile == "connector_flow_omc_named_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "arrayed_shared_bus_diagnostic",
            "omc_unmatched_flow_diagnostic",
            "record_repair_hypothesis",
        }
    if tool_profile == "connector_flow_residual_consistency_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "arrayed_shared_bus_diagnostic",
            "omc_unmatched_flow_diagnostic",
            "record_repair_hypothesis",
            "residual_hypothesis_consistency_check",
        }
    if tool_profile == "connector_flow_residual_revision_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "arrayed_shared_bus_diagnostic",
            "omc_unmatched_flow_diagnostic",
            "record_repair_hypothesis",
            "residual_hypothesis_consistency_check",
        }
    if tool_profile == "connector_flow_delta_portfolio_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "arrayed_shared_bus_diagnostic",
            "omc_unmatched_flow_diagnostic",
            "record_equation_delta_candidate_portfolio",
            "record_repair_hypothesis",
            "residual_hypothesis_consistency_check",
        }
    if tool_profile == "connector_flow_delta_coverage_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "arrayed_shared_bus_diagnostic",
            "omc_unmatched_flow_diagnostic",
            "record_equation_delta_candidate_portfolio",
            "record_repair_hypothesis",
            "residual_hypothesis_consistency_check",
        }
    if tool_profile == "connector_flow_delta_execution_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "arrayed_shared_bus_diagnostic",
            "omc_unmatched_flow_diagnostic",
            "record_equation_delta_candidate_portfolio",
            "record_repair_hypothesis",
            "residual_hypothesis_consistency_check",
        }
    if tool_profile == "connector_flow_candidate_preference_checkpoint":
        return {
            "submit_final",
            "simulate_model",
            "connector_flow_state_diagnostic",
            "arrayed_shared_bus_diagnostic",
            "omc_unmatched_flow_diagnostic",
            "record_equation_delta_candidate_portfolio",
            "record_candidate_preference_rationale",
            "record_repair_hypothesis",
            "residual_hypothesis_consistency_check",
        }
    return {"submit_final", "candidate_acceptance_critique"}


def _candidate_checkpoint_message(*, tool_name: str, tool_profile: str = "") -> str:
    if tool_profile == "base_submit_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. The harness is not selecting or submitting for you. If no concrete requirement remains "
            "unvalidated, call submit_final with the same successful model_text. If a concrete blocker remains, "
            "state it briefly, then call submit_final only after resolving it."
        )
    if tool_profile == "base_candidate_portfolio_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. The harness is not selecting or submitting for you. Stop exploring alternate structures "
            "unless a concrete requirement remains unvalidated. Otherwise call submit_final with the same successful "
            "model_text."
        )
    if tool_profile == "reusable_contract_oracle_submit_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, choose explicitly: "
            "call reusable_contract_oracle_diagnostic on the same successful model_text if the reusable contract "
            "is still uncertain, call record_final_decision_rationale with concrete blockers or a submit decision, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_submit_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, choose explicitly: "
            "call simulate_model once for confirmation, call connector_flow_semantics_diagnostic with a concrete "
            "semantic concern, call record_final_decision_rationale, or call submit_final with the same successful "
            "model_text. Do not continue searching only for a more symmetric or elegant candidate. The harness is "
            "not selecting or submitting anything for you."
        )
    if tool_profile == "connector_flow_state_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call connector_flow_state_diagnostic with a concrete semantic concern, or call "
            "submit_final with the same successful model_text. The harness is not selecting or submitting anything "
            "for you."
        )
    if tool_profile == "connector_flow_hypothesis_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_minimal_contract_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_arrayed_bus_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_omc_named_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_residual_consistency_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_residual_revision_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_delta_portfolio_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_delta_coverage_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_delta_execution_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    if tool_profile == "connector_flow_candidate_preference_checkpoint":
        return (
            "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
            f"{tool_name}. Before testing another candidate or abandoning this one, either call simulate_model once "
            "for confirmation, call record_repair_hypothesis only if a concrete task requirement remains unresolved, "
            "or call submit_final with the same successful model_text. The harness is not selecting or submitting "
            "anything for you."
        )
    return (
        "Transparent checkpoint: the previous candidate produced successful OMC evidence via "
        f"{tool_name}. Before testing another candidate or abandoning this one, choose explicitly: "
        "call submit_final with the same successful model_text, or call candidate_acceptance_critique "
        "with omc_passed=true, the explicit task constraints, and your concrete concern. "
        "The harness is not selecting or submitting anything for you."
    )


def _checkpoint_guard_result(tool_name: str, *, tool_profile: str = "") -> str:
    allowed_tools = sorted(_checkpoint_allowed_tools(tool_profile))
    return json.dumps(
        {
            "error": "checkpoint_decision_required",
            "requested_tool": tool_name,
            "allowed_tools": allowed_tools,
            "diagnostic_only": True,
            "auto_submit": False,
            "candidate_selected": False,
            "guidance": (
                "A transparent checkpoint is active because a previous candidate produced successful OMC evidence. "
                "Use one of the allowed decision tools before using other tools."
            ),
        },
        sort_keys=True,
    )


def dispatch_tool(name: str, arguments: dict) -> str:
    model_text = str(arguments.get("model_text") or "")
    model_name = _extract_model_name(model_text) or "model"
    if name in ("check_model", "simulate_model", "submit_final"):
        if not model_text.strip():
            return json.dumps({"error": "model_text required"})
    if name == "check_model":
        _, output, check_ok, _sim = _run_omc(model_text, model_name)
        return str(output or "")
    if name == "simulate_model":
        stop_time = float(arguments.get("stop_time") or 0.05)
        intervals = max(1, int(arguments.get("intervals") or 100))
        _, output, _check_ok, _sim = _run_omc(model_text, model_name, stop_time=stop_time, intervals=intervals)
        return str(output or "")
    if name == "submit_final":
        return json.dumps({"status": "submitted", "model_name": model_name})
    if name == "connector_balance_diagnostic":
        return dispatch_connector_balance_tool(name, arguments)
    if name == "replaceable_partial_diagnostic":
        return dispatch_replaceable_partial_tool(name, arguments)
    if name == "replaceable_partial_policy_check":
        return dispatch_replaceable_policy_tool(name, arguments)
    if name == "candidate_acceptance_critique":
        return dispatch_candidate_critique_tool(name, arguments)
    if name == "record_structure_strategies":
        return dispatch_structure_strategy_tool(name, arguments)
    if name == "structure_coverage_diagnostic":
        return dispatch_structure_coverage_tool(name, arguments)
    if name == "connector_contract_diagnostic":
        return dispatch_connector_contract_tool(name, arguments)
    if name == "connector_flow_semantics_diagnostic":
        return dispatch_connector_flow_semantics_tool(name, arguments)
    if name == "connector_flow_state_diagnostic":
        return dispatch_connector_flow_state_tool(name, arguments)
    if name == "record_repair_hypothesis":
        return dispatch_repair_hypothesis_tool(name, arguments)
    if name == "arrayed_shared_bus_diagnostic":
        return dispatch_arrayed_shared_bus_tool(name, arguments)
    if name == "omc_unmatched_flow_diagnostic":
        return dispatch_omc_unmatched_flow_tool(name, arguments)
    if name == "residual_hypothesis_consistency_check":
        return dispatch_residual_hypothesis_consistency_tool(name, arguments)
    if name == "record_equation_delta_candidate_portfolio":
        return dispatch_equation_delta_portfolio_tool(name, arguments)
    if name == "record_candidate_preference_rationale":
        return dispatch_candidate_preference_tool(name, arguments)
    if name == "record_semantic_memory_selection":
        return dispatch_memory_selection_tool(name, arguments)
    if name == "reusable_contract_oracle_diagnostic":
        return dispatch_reusable_contract_oracle_tool(name, arguments)
    if name == "record_final_decision_rationale":
        return dispatch_final_decision_record_tool(name, arguments)
    return dispatch_structural_tool(name, arguments)


def _run_omc(
    model_text: str,
    model_name: str,
    stop_time: float = 0.05,
    intervals: int = 5,
) -> tuple[int | None, str, bool, bool]:
    with temporary_workspace("gf_v0280_tool_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(f"{model_name}.mo"),
            primary_model_name=model_name,
            source_library_path="",
            source_package_name="",
            source_library_model_path="",
            source_qualified_model_name=model_name,
        )
        layout.model_write_path.write_text(model_text, encoding="utf-8")
        return run_check_and_simulate(
            workspace=workspace,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=180,
            backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            stop_time=float(stop_time),
            intervals=int(intervals),
            extra_model_loads=[],
        )


def run_tool_use_case(
    case: dict[str, Any],
    *,
    max_steps: int,
    max_token_budget: int,
    planner_backend: str = "auto",
    tool_profile: str = "structural",
) -> dict[str, Any]:
    current_text = str(case["model_text"])
    model_name = str(case["model_name"])
    case_id = str(case["case_id"])
    workflow_goal = str(case.get("workflow_goal") or "")
    external_context = str(case.get("external_context") or "").strip()
    adapter, config = resolve_provider_adapter(planner_backend)
    provider = config.provider_name
    if provider == "rule":
        return _fail_result(case_id, model_name, "rule_backend_selected")
    tool_defs = get_tool_defs(tool_profile)

    system_prompt = (
        "You are fixing a Modelica model. You have tools for OMC operations and structural diagnostics.\n"
        "Use check_model to see current compiler output.\n"
        "Use simulate_model to run a simulation.\n"
        "When the model is correct, call submit_final.\n"
        "Keep edits minimal and compile-oriented.\n"
        f"{get_tool_profile_guidance(tool_profile)}"
    )
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Task: {workflow_goal}\n\n"
            f"External Modelica context:\n-----BEGIN_CONTEXT-----\n{external_context}\n-----END_CONTEXT-----\n\n"
            if external_context
            else ""
        ) + (
            f"Model name: {model_name}\n\n"
            f"Current model:\n-----BEGIN_MODEL-----\n{current_text}\n-----END_MODEL-----\n"
        )},
    ]
    steps: list[dict] = []
    token_used = 0
    final_verdict = "FAILED"
    final_model = current_text
    submitted = False
    provider_error = ""
    pending_checkpoint = False
    checkpoint_grace_steps_remaining = 0

    for step_idx in range(1, max(1, int(max_steps)) + 1):
        resp, err = adapter.send_tool_request(messages, tool_defs, config)
        if err:
            provider_error = err
            steps.append({"step": step_idx, "error": err})
            break
        if resp is None:
            steps.append({"step": step_idx, "error": "null_response"})
            break
        token_used += resp.usage.get("total_tokens", 0)
        step_record: dict = {
            "step": step_idx,
            "text": resp.text,
            "tool_calls": [{"name": tc.name, "arguments": tc.arguments} for tc in resp.tool_calls],
            "token_used": token_used,
        }
        if resp.tool_calls:
            assistant_msg: dict = {"role": "assistant", "content": resp.text or None}
            reasoning = resp.usage.get("_reasoning_content", "")
            if reasoning:
                assistant_msg["reasoning_content"] = reasoning
            tc_list = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in resp.tool_calls
            ]
            assistant_msg["tool_calls"] = tc_list
            messages.append(assistant_msg)
            tool_results = []
            should_break = False
            checkpoint_messages: list[str] = []
            checkpoint_guard_violations: list[str] = []
            checkpoint_decision_seen = False
            for tc in resp.tool_calls:
                args = dict(tc.arguments)
                if not args.get("model_text", "").strip():
                    args["model_text"] = current_text
                if pending_checkpoint and tc.name not in _checkpoint_allowed_tools(tool_profile):
                    result = _checkpoint_guard_result(tc.name, tool_profile=tool_profile)
                    checkpoint_guard_violations.append(tc.name)
                else:
                    result = dispatch_tool(tc.name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                tool_results.append({"name": tc.name, "result": result[:500]})
                if _checkpoint_enabled(tool_profile) and _omc_success_result(tc.name, result):
                    checkpoint_messages.append(_candidate_checkpoint_message(tool_name=tc.name, tool_profile=tool_profile))
                if pending_checkpoint and tc.name in _checkpoint_allowed_tools(tool_profile):
                    checkpoint_decision_seen = True
                if tc.name == "submit_final":
                    submitted = True
                    final_model = str(tc.arguments.get("model_text") or current_text)
                    should_break = True
            if checkpoint_decision_seen:
                pending_checkpoint = False
            if checkpoint_messages and not should_break:
                checkpoint_text = "\n".join(checkpoint_messages)
                messages.append({"role": "user", "content": checkpoint_text})
                step_record["checkpoint_messages"] = checkpoint_messages
                pending_checkpoint = True
                checkpoint_grace_steps_remaining = max(checkpoint_grace_steps_remaining, 2)
            if checkpoint_guard_violations:
                messages.append(
                    {
                        "role": "user",
                        "content": _candidate_checkpoint_message(
                            tool_name="previous_successful_tool",
                            tool_profile=tool_profile,
                        ),
                    }
                )
                step_record["checkpoint_guard_violations"] = checkpoint_guard_violations
                checkpoint_grace_steps_remaining = max(checkpoint_grace_steps_remaining, 1)
            step_record["tool_results"] = tool_results
            if should_break:
                steps.append(step_record)
                break
        else:
            messages.append({"role": "assistant", "content": resp.text})
        steps.append(step_record)
        if submitted:
            break
        if token_used >= max_token_budget:
            if pending_checkpoint and checkpoint_grace_steps_remaining > 0:
                checkpoint_grace_steps_remaining -= 1
                step_record["checkpoint_budget_grace_used"] = True
                continue
            break

    if submitted:
        final_model_name = _extract_model_name(final_model) or model_name
        _, output, check_ok, simulate_ok = _run_omc(
            final_model,
            final_model_name,
            stop_time=float(case.get("final_stop_time") or 0.05),
            intervals=int(case.get("final_intervals") or 5),
        )
        final_verdict = "PASS" if (check_ok and simulate_ok) else "FAILED"
        steps.append({"step": "final_eval", "check_ok": check_ok, "simulate_ok": simulate_ok, "omc_output": str(output or "")[:2000]})

    result = {
        "case_id": case_id,
        "model_name": model_name,
        "provider": provider,
        "run_mode": "tool_use",
        "tool_profile": tool_profile,
        "final_verdict": final_verdict,
        "submitted": submitted,
        "step_count": len(steps),
        "token_used": token_used,
        "provider_error": provider_error,
        "steps": steps,
        "final_model_text": final_model,
    }
    return result


def _fail_result(case_id: str, model_name: str, error: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "model_name": model_name,
        "provider": "",
        "run_mode": "tool_use",
        "final_verdict": "FAILED",
        "submitted": False,
        "step_count": 0,
        "token_used": 0,
        "provider_error": error,
        "steps": [],
        "final_model_text": "",
    }


def run_tool_use_baseline(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    cases: list[dict[str, Any]],
    limit: int = 1,
    max_steps: int = 10,
    max_token_budget: int = 32000,
    planner_backend: str = "auto",
    tool_profile: str = "structural",
) -> dict[str, Any]:
    selected = list(cases)[:max(0, int(limit))]
    results = [
        run_tool_use_case(
            case,
            max_steps=max_steps,
            max_token_budget=max_token_budget,
            planner_backend=planner_backend,
            tool_profile=tool_profile,
        )
        for case in selected
    ]
    total = len(results)
    pass_count = sum(1 for r in results if r.get("final_verdict") == "PASS")
    summary = {
        "version": "v0.28.0",
        "status": "PASS" if total else "REVIEW",
        "analysis_scope": "tool_use_harness_smoke",
        "run_mode": "tool_use",
        "tool_profile": tool_profile,
        "case_count": total,
        "pass_count": pass_count,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": "tool_use_harness_artifact_ready" if total else "tool_use_harness_needs_cases",
    }
    write_outputs(out_dir=out_dir, summary=summary, results=results)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
