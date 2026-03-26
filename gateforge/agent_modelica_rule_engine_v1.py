from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from .agent_modelica_behavioral_contract_evaluator_v1 import (
    apply_initialization_marker_repair,
)


class RuleTier(str, Enum):
    MUTATION_CONTRACT_RULE = "mutation_contract_rule"
    DOMAIN_GENERAL_RULE = "domain_general_rule"
    SOURCE_AWARE_ONLY = "source_aware_only"


@dataclass(frozen=True)
class RuleContext:
    current_text: str
    declared_failure_type: str
    output: str = ""
    source_model_text: str = ""
    observed_failure_type: str = ""
    current_round: int = 1
    failure_bucket_before: str = ""


@dataclass(frozen=True)
class RuleResult:
    new_text: str
    applied: bool
    rule_id: str
    action_key: str
    attempt_field: str
    rule_tier: RuleTier
    replay_eligible: bool
    audit_dict: dict
    failure_bucket_before: str = ""
    failure_bucket_after: str = ""


class RepairRule(Protocol):
    rule_id: str
    action_key: str
    attempt_field: str
    rule_tier: RuleTier
    replay_eligible: bool

    def matches(self, ctx: RuleContext) -> bool:
        ...

    def apply(self, ctx: RuleContext) -> RuleResult:
        ...


def _make_action_key(reason_tag: str, source: str = "rule_engine_v1") -> str:
    return f"repair|{reason_tag}|{source}"


def _enrich_audit(
    *,
    audit: dict,
    rule_id: str,
    action_key: str,
    attempt_field: str,
    rule_tier: RuleTier,
    replay_eligible: bool,
    failure_bucket_before: str,
    failure_bucket_after: str,
) -> dict:
    enriched = dict(audit)
    enriched.setdefault("applied", False)
    enriched["rule_id"] = rule_id
    enriched["action_key"] = action_key
    enriched["attempt_field"] = attempt_field
    enriched["rule_tier"] = str(rule_tier.value)
    enriched["replay_eligible"] = bool(replay_eligible)
    enriched["rounds_consumed"] = 1 if bool(enriched.get("applied")) else 0
    enriched["failure_bucket_before"] = str(failure_bucket_before or "")
    enriched["failure_bucket_after"] = str(failure_bucket_after or "")
    return enriched


def _build_result(
    *,
    ctx: RuleContext,
    rule: RepairRule,
    new_text: str,
    audit: dict,
) -> RuleResult:
    failure_bucket_after = "retry_pending" if bool(audit.get("applied")) else str(ctx.failure_bucket_before or "")
    enriched = _enrich_audit(
        audit=audit,
        rule_id=rule.rule_id,
        action_key=rule.action_key,
        attempt_field=rule.attempt_field,
        rule_tier=rule.rule_tier,
        replay_eligible=rule.replay_eligible,
        failure_bucket_before=str(ctx.failure_bucket_before or ""),
        failure_bucket_after=failure_bucket_after,
    )
    return RuleResult(
        new_text=new_text,
        applied=bool(enriched.get("applied")),
        rule_id=rule.rule_id,
        action_key=rule.action_key,
        attempt_field=rule.attempt_field,
        rule_tier=rule.rule_tier,
        replay_eligible=rule.replay_eligible,
        audit_dict=enriched,
        failure_bucket_before=str(ctx.failure_bucket_before or ""),
        failure_bucket_after=failure_bucket_after,
    )


def wave2_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_WAVE2_DETERMINISTIC_REPAIR") or "").strip() == "1"


def wave2_1_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR") or "").strip() == "1"


def wave2_2_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR") or "").strip() == "1"


def multi_round_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR") or "").strip() == "1"


def _remove_lines_with_marker(*, current_text: str, marker: str) -> tuple[str, dict]:
    lines = str(current_text or "").splitlines(keepends=True)
    remove_idx = {idx for idx, line in enumerate(lines) if marker in line.lower()}
    if not remove_idx:
        return current_text, {"applied": False, "reason": f"{marker}_not_detected"}
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), {"applied": True, "reason": f"removed_{marker}_line", "removed_line_count": len(remove_idx)}


def _restore_parameter_binding_from_source(*, current_text: str, source_model_text: str) -> tuple[str, dict]:
    current_lines = str(current_text or "").splitlines(keepends=True)
    source_lines = str(source_model_text or "").splitlines(keepends=True)
    if not current_lines or not source_lines:
        return current_text, {"applied": False, "reason": "source_or_current_text_missing"}
    updated = list(current_lines)
    replaced = 0
    for idx, line in enumerate(current_lines):
        lower = line.lower()
        if "gateforge_parameter_binding_error" not in lower:
            continue
        match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        instance_name = str(match.group(1) or "").strip() if match else ""
        replacement = ""
        if instance_name:
            for source_line in source_lines:
                if "gateforge_parameter_binding_error" in source_line.lower():
                    continue
                if f"{instance_name}(" in source_line:
                    replacement = source_line
                    break
        if not replacement:
            continue
        updated[idx] = replacement
        replaced += 1
    if replaced <= 0:
        return current_text, {"applied": False, "reason": "parameter_binding_source_line_not_found"}
    return "".join(updated), {"applied": True, "reason": "restored_parameter_binding_from_source", "replaced_line_count": replaced}


def extract_state_tokens_from_output(output: str) -> list[str]:
    return sorted(set(re.findall(r"__gf_state_\d+", str(output or ""))))


def extract_undef_tokens_from_output(output: str) -> list[str]:
    return sorted(set(
        re.findall(r"__gf_undef_\d+", str(output or ""))
        + re.findall(r"__gf_undeclared_\d+", str(output or ""))
    ))


def remove_gateforge_injected_symbol_block(model_text: str) -> tuple[str, int]:
    lines = str(model_text or "").splitlines(keepends=True)
    if not lines:
        return str(model_text or ""), 0
    remove_idx: set[int] = set()
    for i, line in enumerate(lines):
        if "__gf_" in line:
            remove_idx.add(i)
            for j in (i - 2, i - 1, i + 1, i + 2):
                if j < 0 or j >= len(lines):
                    continue
                text = lines[j].strip()
                if "GateForge mutation" in text:
                    remove_idx.add(j)
                if text == "equation":
                    remove_idx.add(j)
    if not remove_idx:
        return str(model_text or ""), 0
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), len(remove_idx)


def apply_generic_parse_error_repair(model_text: str, output: str, failure_type: str) -> tuple[str, dict]:
    failure = str(failure_type or "").strip().lower()
    lower = str(output or "").lower()

    tokens: list[str] = []
    reason_prefix = ""
    if failure == "script_parse_error":
        if "no viable alternative near token" not in lower:
            return model_text, {"applied": False, "reason": "parse_error_without_expected_marker"}
        tokens = extract_state_tokens_from_output(output)
        reason_prefix = "injected_state_tokens"
        if not tokens:
            return model_text, {"applied": False, "reason": "state_token_not_detected"}
    elif failure == "model_check_error":
        parse_markers = ("no viable alternative near token", "lexer failed to recognize")
        if any(marker in lower for marker in parse_markers):
            state_tokens = extract_state_tokens_from_output(output)
            if not state_tokens and "__gf_state_" in str(model_text or ""):
                state_tokens = sorted(set(re.findall(r"__gf_state_\d+", str(model_text or ""))))
            if state_tokens:
                tokens = state_tokens
                reason_prefix = "injected_state_tokens"
            else:
                return model_text, {"applied": False, "reason": "state_token_not_detected"}
        else:
            tokens = extract_undef_tokens_from_output(output)
            if not tokens and any(p in str(model_text or "") for p in ("__gf_undef_", "__gf_undeclared_")):
                tokens = sorted(set(
                    re.findall(r"__gf_undef_\d+", str(model_text or ""))
                    + re.findall(r"__gf_undeclared_\d+", str(model_text or ""))
                ))
            reason_prefix = "injected_undef_tokens"
            if not tokens:
                return model_text, {"applied": False, "reason": "undef_token_not_detected"}
    else:
        return model_text, {"applied": False, "reason": "failure_type_not_supported_for_pre_repair"}

    patched = str(model_text or "")
    lines = patched.splitlines(keepends=True)
    kept_lines: list[str] = []
    removed_line_count = 0
    for line in lines:
        if any(tok in line for tok in tokens):
            removed_line_count += 1
            continue
        kept_lines.append(line)
    if removed_line_count > 0:
        return "".join(kept_lines), {
            "applied": True,
            "reason": f"removed_lines_with_{reason_prefix}",
            "detected_tokens": tokens,
            "removed_line_count": int(removed_line_count),
        }

    removed_count = 0
    for token in tokens:
        patched, replaced = re.subn(rf"\b{re.escape(token)}\b", "", patched)
        removed_count += int(replaced)

    if removed_count <= 0:
        return model_text, {
            "applied": False,
            "reason": "detected_token_not_found_in_model_text",
            "detected_tokens": tokens,
        }

    return patched, {
        "applied": True,
        "reason": f"removed_{reason_prefix}_inline",
        "detected_tokens": tokens,
        "removed_count": int(removed_count),
    }


def apply_gf_injected_symbol_cleanup_repair(model_text: str, output: str, failure_type: str) -> tuple[str, dict]:
    failure = str(failure_type or "").strip().lower()
    lower = str(output or "").lower()
    if failure not in {"script_parse_error", "model_check_error"}:
        return model_text, {"applied": False, "reason": "failure_type_not_supported_for_gf_cleanup"}

    parse_markers = ("no viable alternative near token", "lexer failed to recognize")
    if failure == "script_parse_error" and "no viable alternative near token" not in lower:
        return model_text, {"applied": False, "reason": "gf_cleanup_without_parse_marker"}
    if failure == "model_check_error" and not any(marker in lower for marker in parse_markers) and not (
        "__gf_undef_" in str(model_text or "") or "__gf_undeclared_" in str(model_text or "")
    ):
        return model_text, {"applied": False, "reason": "gf_cleanup_without_supported_marker"}

    fallback_patched, removed = remove_gateforge_injected_symbol_block(model_text)
    if removed > 0:
        reason = "removed_gateforge_injected_symbol_block"
        if failure == "model_check_error" and not any(marker in lower for marker in parse_markers):
            reason = "removed_gateforge_injected_symbol_block_fallback"
        return fallback_patched, {
            "applied": True,
            "reason": reason,
            "removed_line_count": int(removed),
        }
    return model_text, {"applied": False, "reason": "gateforge_injected_symbol_block_not_detected"}


def apply_parse_error_pre_repair(model_text: str, output: str, failure_type: str) -> tuple[str, dict]:
    generic_patched, generic_audit = apply_generic_parse_error_repair(model_text, output, failure_type)
    if bool(generic_audit.get("applied")):
        return generic_patched, generic_audit
    cleanup_patched, cleanup_audit = apply_gf_injected_symbol_cleanup_repair(model_text, output, failure_type)
    if bool(cleanup_audit.get("applied")):
        return cleanup_patched, cleanup_audit
    return model_text, generic_audit


def apply_wave2_marker_repair(*, current_text: str, declared_failure_type: str) -> tuple[str, dict]:
    if not wave2_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_deterministic_repair_disabled"}
    declared = str(declared_failure_type or "").strip().lower()
    marker_map = {
        "overconstrained_system": "gateforge_overconstrained_system",
        "array_dimension_mismatch": "gateforge_array_dimension_mismatch",
    }
    marker = marker_map.get(declared, "")
    if not marker:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    return _remove_lines_with_marker(current_text=current_text, marker=marker)


def apply_wave2_1_marker_repair(*, current_text: str, declared_failure_type: str) -> tuple[str, dict]:
    if not wave2_1_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_1_deterministic_repair_disabled"}
    declared = str(declared_failure_type or "").strip().lower()
    marker_map = {
        "solver_sensitive_simulate_failure": "gateforge_solver_sensitive_simulate_failure",
        "event_logic_error": "gateforge_event_logic_error",
        "semantic_drift_after_compile_pass": "gateforge_semantic_drift_after_compile_pass",
    }
    marker = marker_map.get(declared, "")
    if not marker:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    return _remove_lines_with_marker(current_text=current_text, marker=marker)


def apply_wave2_2_marker_repair(*, current_text: str, declared_failure_type: str) -> tuple[str, dict]:
    if not wave2_2_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_2_deterministic_repair_disabled"}
    declared = str(declared_failure_type or "").strip().lower()
    marker_map = {
        "cross_component_parameter_coupling_error": "gateforge_cross_component_parameter_coupling_error",
        "control_loop_sign_semantic_drift": "gateforge_control_loop_sign_semantic_drift",
        "mode_switch_guard_logic_error": "gateforge_mode_switch_guard_logic_error",
    }
    marker = marker_map.get(declared, "")
    if not marker:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    return _remove_lines_with_marker(current_text=current_text, marker=marker)


def apply_simulate_error_injection_repair(
    *, current_text: str, declared_failure_type: str
) -> tuple[str, dict]:
    declared = str(declared_failure_type or "").strip().lower()
    if declared != "simulate_error":
        return current_text, {"applied": False, "reason": "declared_failure_type_not_simulate_error"}
    text = str(current_text or "")
    lines = text.splitlines(keepends=True)
    gf_var_names: set[str] = set()
    for line in lines:
        m = re.search(r"\b(__gf_(?:state|tau)_\d+)\b", line)
        if m:
            gf_var_names.add(m.group(1))
    if not gf_var_names:
        return current_text, {"applied": False, "reason": "no_gf_injection_detected"}
    gf_pat = re.compile(r"\b(" + "|".join(re.escape(v) for v in sorted(gf_var_names)) + r")\b")
    mutation_comment_pat = re.compile(
        r"//\s*GateForge mutation:\s*(simulation instability|zero time constant)",
        re.IGNORECASE,
    )
    kept: list[str] = []
    removed_count = 0
    for line in lines:
        strip = line.strip()
        if mutation_comment_pat.search(strip) or gf_pat.search(strip):
            removed_count += 1
        else:
            kept.append(line)
    if not removed_count:
        return current_text, {"applied": False, "reason": "no_lines_removed"}
    return "".join(kept), {
        "applied": True,
        "reason": "removed_gf_simulate_injection",
        "removed_line_count": removed_count,
        "gf_var_names": sorted(gf_var_names),
    }


def apply_multi_round_layered_repair(
    *,
    current_text: str,
    source_model_text: str,
    declared_failure_type: str,
    current_round: int,
) -> tuple[str, dict]:
    if not multi_round_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "multi_round_deterministic_repair_disabled"}
    try:
        round_idx = max(1, int(current_round))
    except Exception:
        round_idx = 1
    if round_idx < 2:
        return current_text, {"applied": False, "reason": "multi_round_layered_repair_deferred_until_round_2"}
    declared = str(declared_failure_type or "").strip().lower()
    lower = str(current_text or "").lower()
    if declared == "cascading_structural_failure":
        if "gateforge_overconstrained_system" in lower:
            patched, audit = _remove_lines_with_marker(
                current_text=current_text,
                marker="gateforge_overconstrained_system",
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_removed_overconstrained_layer"
                return patched, audit
        if "gateforge_solver_sensitive_simulate_failure" in lower:
            patched, audit = _remove_lines_with_marker(
                current_text=current_text,
                marker="gateforge_solver_sensitive_simulate_failure",
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_removed_solver_sensitive_layer"
                return patched, audit
        return current_text, {"applied": False, "reason": "multi_round_cascade_no_supported_layer_detected"}
    if declared == "coupled_conflict_failure":
        if "gateforge_parameter_binding_error" in lower:
            patched, audit = _restore_parameter_binding_from_source(
                current_text=current_text,
                source_model_text=source_model_text,
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_restored_parameter_binding_layer"
                return patched, audit
        if "gateforge_control_loop_sign_semantic_drift" in lower:
            patched, audit = _remove_lines_with_marker(
                current_text=current_text,
                marker="gateforge_control_loop_sign_semantic_drift",
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_removed_control_loop_layer"
                return patched, audit
        if "gateforge_cross_component_parameter_coupling_error" in lower:
            patched, audit = _remove_lines_with_marker(
                current_text=current_text,
                marker="gateforge_cross_component_parameter_coupling_error",
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_removed_cross_component_layer"
                return patched, audit
        return current_text, {"applied": False, "reason": "multi_round_conflict_no_supported_layer_detected"}
    return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}


@dataclass(frozen=True)
class BaseRepairRule:
    rule_id: str
    action_key: str
    attempt_field: str
    rule_tier: RuleTier
    replay_eligible: bool

    def matches(self, ctx: RuleContext) -> bool:
        return True


@dataclass(frozen=True)
class ParseErrorPreRepairRule(BaseRepairRule):
    def apply(self, ctx: RuleContext) -> RuleResult:
        new_text, audit = apply_generic_parse_error_repair(
            ctx.current_text,
            ctx.output,
            ctx.declared_failure_type,
        )
        return _build_result(ctx=ctx, rule=self, new_text=new_text, audit=audit)


@dataclass(frozen=True)
class InitializationMarkerRepairRule(BaseRepairRule):
    def apply(self, ctx: RuleContext) -> RuleResult:
        new_text, audit = apply_initialization_marker_repair(
            current_text=ctx.current_text,
            declared_failure_type=ctx.declared_failure_type,
        )
        return _build_result(ctx=ctx, rule=self, new_text=new_text, audit=audit)


@dataclass(frozen=True)
class GFInjectedSymbolCleanupRepairRule(BaseRepairRule):
    def apply(self, ctx: RuleContext) -> RuleResult:
        new_text, audit = apply_gf_injected_symbol_cleanup_repair(
            ctx.current_text,
            ctx.output,
            ctx.declared_failure_type,
        )
        return _build_result(ctx=ctx, rule=self, new_text=new_text, audit=audit)


@dataclass(frozen=True)
class Wave2MarkerRepairRule(BaseRepairRule):
    def apply(self, ctx: RuleContext) -> RuleResult:
        new_text, audit = apply_wave2_marker_repair(
            current_text=ctx.current_text,
            declared_failure_type=ctx.declared_failure_type,
        )
        return _build_result(ctx=ctx, rule=self, new_text=new_text, audit=audit)


@dataclass(frozen=True)
class Wave21MarkerRepairRule(BaseRepairRule):
    def apply(self, ctx: RuleContext) -> RuleResult:
        new_text, audit = apply_wave2_1_marker_repair(
            current_text=ctx.current_text,
            declared_failure_type=ctx.declared_failure_type,
        )
        return _build_result(ctx=ctx, rule=self, new_text=new_text, audit=audit)


@dataclass(frozen=True)
class Wave22MarkerRepairRule(BaseRepairRule):
    def apply(self, ctx: RuleContext) -> RuleResult:
        new_text, audit = apply_wave2_2_marker_repair(
            current_text=ctx.current_text,
            declared_failure_type=ctx.declared_failure_type,
        )
        return _build_result(ctx=ctx, rule=self, new_text=new_text, audit=audit)


@dataclass(frozen=True)
class SimulateErrorInjectionRepairRule(BaseRepairRule):
    def apply(self, ctx: RuleContext) -> RuleResult:
        new_text, audit = apply_simulate_error_injection_repair(
            current_text=ctx.current_text,
            declared_failure_type=ctx.declared_failure_type,
        )
        return _build_result(ctx=ctx, rule=self, new_text=new_text, audit=audit)


@dataclass(frozen=True)
class MultiRoundLayeredRepairRule(BaseRepairRule):
    def apply(self, ctx: RuleContext) -> RuleResult:
        new_text, audit = apply_multi_round_layered_repair(
            current_text=ctx.current_text,
            source_model_text=ctx.source_model_text,
            declared_failure_type=ctx.declared_failure_type,
            current_round=ctx.current_round,
        )
        return _build_result(ctx=ctx, rule=self, new_text=new_text, audit=audit)


@dataclass
class RepairRuleRegistry:
    rules: list[RepairRule] = field(default_factory=list)

    def resolve_rule_order(self, priority_context: dict | None = None) -> list[RepairRule]:
        order = priority_context.get("recommended_rule_order") if isinstance(priority_context, dict) else []
        recommended_rule_order = [str(rule_id or "").strip() for rule_id in order if str(rule_id or "").strip()]
        base_rules = list(self.rules)
        if not recommended_rule_order:
            return base_rules
        order_index = {rule_id: idx for idx, rule_id in enumerate(recommended_rule_order)}
        original_index = {id(rule): idx for idx, rule in enumerate(base_rules)}
        return sorted(
            base_rules,
            key=lambda rule: (
                0 if str(rule.rule_id or "") in order_index else 1,
                order_index.get(str(rule.rule_id or ""), 0),
                original_index.get(id(rule), 0),
            ),
        )

    def try_repairs(self, ctx: RuleContext, *, priority_context: dict | None = None) -> list[RuleResult]:
        results: list[RuleResult] = []
        for rule in self.resolve_rule_order(priority_context):
            if not rule.matches(ctx):
                continue
            result = rule.apply(ctx)
            results.append(result)
            if result.applied:
                break
        return results


def build_default_rule_registry() -> RepairRuleRegistry:
    return RepairRuleRegistry(
        rules=[
            ParseErrorPreRepairRule(
                rule_id="rule_parse_error_pre_repair",
                action_key=_make_action_key("parse_error_pre_repair"),
                attempt_field="pre_repair",
                rule_tier=RuleTier.DOMAIN_GENERAL_RULE,
                replay_eligible=True,
            ),
            GFInjectedSymbolCleanupRepairRule(
                rule_id="rule_gf_injected_symbol_cleanup_repair",
                action_key=_make_action_key("gf_injected_symbol_cleanup_repair"),
                attempt_field="gf_injected_symbol_cleanup_repair",
                rule_tier=RuleTier.MUTATION_CONTRACT_RULE,
                replay_eligible=False,
            ),
            InitializationMarkerRepairRule(
                rule_id="rule_initialization_marker_repair",
                action_key=_make_action_key("initialization_marker_repair"),
                attempt_field="initialization_marker_repair",
                rule_tier=RuleTier.MUTATION_CONTRACT_RULE,
                replay_eligible=False,
            ),
            Wave2MarkerRepairRule(
                rule_id="rule_wave2_marker_repair",
                action_key=_make_action_key("wave2_marker_repair"),
                attempt_field="wave2_marker_repair",
                rule_tier=RuleTier.MUTATION_CONTRACT_RULE,
                replay_eligible=False,
            ),
            Wave21MarkerRepairRule(
                rule_id="rule_wave2_1_marker_repair",
                action_key=_make_action_key("wave2_1_marker_repair"),
                attempt_field="wave2_1_marker_repair",
                rule_tier=RuleTier.MUTATION_CONTRACT_RULE,
                replay_eligible=False,
            ),
            Wave22MarkerRepairRule(
                rule_id="rule_wave2_2_marker_repair",
                action_key=_make_action_key("wave2_2_marker_repair"),
                attempt_field="wave2_2_marker_repair",
                rule_tier=RuleTier.MUTATION_CONTRACT_RULE,
                replay_eligible=False,
            ),
            SimulateErrorInjectionRepairRule(
                rule_id="rule_simulate_error_injection_repair",
                action_key=_make_action_key("simulate_error_injection_repair"),
                attempt_field="simulate_error_injection_repair",
                rule_tier=RuleTier.MUTATION_CONTRACT_RULE,
                replay_eligible=False,
            ),
            MultiRoundLayeredRepairRule(
                rule_id="rule_multi_round_layered_repair",
                action_key=_make_action_key("multi_round_layered_repair"),
                attempt_field="multi_round_layered_repair",
                rule_tier=RuleTier.DOMAIN_GENERAL_RULE,
                replay_eligible=True,
            ),
        ]
    )
