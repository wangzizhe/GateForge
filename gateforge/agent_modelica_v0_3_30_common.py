from __future__ import annotations

import re
from pathlib import Path

from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0
from .agent_modelica_omc_workspace_v1 import run_omc_script_docker, temporary_workspace
from .agent_modelica_v0_3_19_common import DOCKER_IMAGE, error_signature_from_text
from .agent_modelica_v0_3_20_common import load_json, norm, write_json, write_text
from .agent_modelica_v0_3_21_common import now_utc


SCHEMA_PREFIX = "agent_modelica_v0_3_30"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_handoff_integrity_current"
DEFAULT_SURFACE_INDEX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_surface_index_current"
DEFAULT_FIRST_FIX_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_first_fix_results_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_first_fix_evidence_current"
DEFAULT_DISCOVERY_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_discovery_results_current"
DEFAULT_DISCOVERY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_discovery_evidence_current"
DEFAULT_DUAL_RECHECK_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_dual_recheck_results_current"
DEFAULT_DUAL_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_dual_recheck_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_30_closeout_current"

DEFAULT_V0329_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_29_closeout_current" / "summary.json"
DEFAULT_V0329_ENTRY_SPEC_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_29_entry_family_spec_current" / "summary.json"
DEFAULT_V0329_ENTRY_TASKSET_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_29_entry_taskset_current" / "taskset.json"
DEFAULT_V0329_PATCH_CONTRACT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_29_patch_contract_current" / "summary.json"

TARGET_STAGE = "check"
TARGET_SUBTYPE = "compile_failure_unknown"
TARGET_STAGE_SUBTYPE = "stage_2_structural_balance_reference"

MEDIUM_RANK_REASONS = {
    "local_cluster_exact_reuse": 500,
    "adjacent_component_package_reuse": 120,
    "canonical_package_path_exact": 80,
    "package_path_exact_or_suffix_match": 50,
    "package_parent_match": 20,
}

SURFACE_INDEX_FIXTURE = {
    "status": "PASS",
    "source_mode": "fixture_local_medium_surface",
    "surface_export_success_rate_pct": 100.0,
    "task_rows": [
        {
            "task_id": "fixture_medium_missing_ambient",
            "canonical_rhs_symbol": "Medium",
            "canonical_package_path": "Modelica.Media.Water.ConstantPropertyLiquidWater",
            "candidate_rhs_symbols": [
                "Medium",
                "Modelica.Media.Water.ConstantPropertyLiquidWater",
                "Modelica.Media.Water.StandardWater",
            ],
        }
    ],
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for item in items:
        value = norm(item)
        if not value or value in seen:
            continue
        seen.add(value)
        rows.append(value)
    return rows


def parse_medium_alias_bindings(model_text: str) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for match in re.finditer(
        r"(?:replaceable|replaceable\s+package|package)\s+package\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_\.]*)\s*;",
        norm(model_text),
    ):
        bindings[norm(match.group(1))] = norm(match.group(2))
    return bindings


def parse_redeclare_clause_rhs_values(model_text: str) -> list[str]:
    values: list[str] = []
    for match in re.finditer(
        r"redeclare\s+package\s+Medium\s*=\s*([A-Za-z_][A-Za-z0-9_\.]*)",
        norm(model_text),
    ):
        values.append(norm(match.group(1)))
    return _dedupe(values)


def parse_canonical_rhs_from_repair_step(step: dict) -> str:
    replacement = norm(step.get("replacement_text"))
    match = re.search(r"redeclare\s+package\s+Medium\s*=\s*([A-Za-z_][A-Za-z0-9_\.]*)", replacement)
    return norm(match.group(1)) if match else ""


def extract_component_name_from_step(step: dict) -> str:
    match_text = norm(step.get("match_text"))
    match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", match_text)
    if not match:
        return ""
    prefix = match_text[: match.start(1)].strip()
    prefix_tokens = prefix.split()
    if len(prefix_tokens) < 2:
        return ""
    return norm(match.group(1))


def _parent_package(path: str) -> str:
    value = norm(path)
    if "." not in value:
        return ""
    return value.rsplit(".", 1)[0]


def _leaf_name(path: str) -> str:
    value = norm(path)
    if "." not in value:
        return value
    return value.rsplit(".", 1)[-1]


def _omc_eval(expr: str, timeout_sec: int = 120) -> str:
    script = "\n".join(
        [
            "loadModel(Modelica);",
            f"{expr};",
            "getErrorString();",
            "",
        ]
    )
    with temporary_workspace("v0330_surface_") as td:
        rc, output = run_omc_script_docker(
            script_text=script,
            timeout_sec=timeout_sec,
            cwd=td,
            image=DOCKER_IMAGE,
        )
    if rc != 0:
        return ""
    lines = [line.strip() for line in str(output or "").splitlines() if line.strip()]
    if len(lines) >= 3:
        return "\n".join(lines[1:-1])
    if len(lines) >= 2:
        return lines[1]
    return ""


def _unwrap_braces(text: str) -> str:
    value = norm(text)
    if value.startswith("{") and value.endswith("}"):
        return value[1:-1]
    return value


def _split_top_level(text: str) -> list[str]:
    rows: list[str] = []
    buf: list[str] = []
    depth = 0
    in_string = False
    escape = False
    for ch in str(text or ""):
        if in_string:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            buf.append(ch)
            continue
        if ch == "{":
            depth += 1
            buf.append(ch)
            continue
        if ch == "}":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue
        if ch == "," and depth == 0:
            token = "".join(buf).strip()
            if token:
                rows.append(token)
            buf = []
            continue
        buf.append(ch)
    token = "".join(buf).strip()
    if token:
        rows.append(token)
    return rows


def _parse_class_names(payload_text: str) -> list[str]:
    inner = _unwrap_braces(payload_text)
    items = _split_top_level(inner)
    rows: list[str] = []
    for item in items:
        value = norm(item).strip('"')
        if value:
            rows.append(value)
    return rows


def _query_package_children(parent_package: str) -> list[str]:
    payload = _omc_eval(f"getClassNames({parent_package})")
    names = _parse_class_names(payload)
    return [f"{parent_package}.{name}" for name in names if norm(name)]


def build_medium_candidate_rhs_symbols(
    *,
    source_model_text: str,
    canonical_rhs_symbol: str,
    use_fixture_only: bool = False,
) -> dict:
    alias_bindings = parse_medium_alias_bindings(source_model_text)
    local_rhs_values = parse_redeclare_clause_rhs_values(source_model_text)
    canonical_package_path = alias_bindings.get(canonical_rhs_symbol, canonical_rhs_symbol if "." in canonical_rhs_symbol else "")
    rhs_candidates: list[str] = []
    rhs_candidates.extend(local_rhs_values)
    if canonical_package_path:
        rhs_candidates.append(canonical_package_path)
        if use_fixture_only:
            sibling_paths = [
                canonical_package_path,
                "Modelica.Media.Water.StandardWater",
                "Modelica.Media.Water.WaterIF97OnePhase_ph",
            ]
        else:
            sibling_paths = _query_package_children(_parent_package(canonical_package_path))
        rhs_candidates.extend(sibling_paths)
    rhs_candidates = _dedupe(rhs_candidates)
    return {
        "canonical_rhs_symbol": canonical_rhs_symbol,
        "canonical_package_path": canonical_package_path,
        "candidate_rhs_symbols": rhs_candidates,
        "alias_bindings": alias_bindings,
        "local_cluster_rhs_values": local_rhs_values,
        "adjacent_component_package_paths": [canonical_package_path] if canonical_package_path else [],
    }


def rank_medium_rhs_candidates(
    *,
    candidate_rhs_symbols: list[str],
    canonical_rhs_symbol: str,
    canonical_package_path: str,
    local_cluster_rhs_values: list[str],
    adjacent_component_package_paths: list[str] | None = None,
) -> list[dict]:
    rows: list[dict] = []
    canonical_leaf = _leaf_name(canonical_package_path)
    canonical_parent = _parent_package(canonical_package_path)
    adjacent_paths = {norm(x) for x in (adjacent_component_package_paths or []) if norm(x)}
    for idx, candidate in enumerate(candidate_rhs_symbols):
        value = norm(candidate)
        score = 0
        reasons: list[str] = []
        if value == canonical_rhs_symbol and value in local_cluster_rhs_values:
            score += MEDIUM_RANK_REASONS["local_cluster_exact_reuse"]
            reasons.append("local_cluster_exact_reuse")
        if value in adjacent_paths:
            score += MEDIUM_RANK_REASONS["adjacent_component_package_reuse"]
            reasons.append("adjacent_component_package_reuse")
        if canonical_package_path and value == canonical_package_path:
            score += MEDIUM_RANK_REASONS["canonical_package_path_exact"]
            reasons.append("canonical_package_path_exact")
        if canonical_package_path and _leaf_name(value) == canonical_leaf:
            score += MEDIUM_RANK_REASONS["package_path_exact_or_suffix_match"]
            reasons.append("package_path_exact_or_suffix_match")
        if canonical_parent and _parent_package(value) == canonical_parent:
            score += MEDIUM_RANK_REASONS["package_parent_match"]
            reasons.append("package_parent_match")
        rows.append(
            {
                "candidate_rhs_symbol": value,
                "score": score,
                "rank_reasons": reasons,
                "input_order": idx,
            }
        )
    rows.sort(key=lambda row: (-int(row.get("score") or 0), int(row.get("input_order") or 0), norm(row.get("candidate_rhs_symbol"))))
    return rows


def synthesize_redeclare_replacement(*, match_text: str, selected_rhs_symbol: str) -> str:
    base = norm(match_text)
    rhs = norm(selected_rhs_symbol)
    if not base or not rhs or "(" not in base:
        return base
    return base.replace("(", f"(redeclare package Medium = {rhs}, ", 1)


def apply_medium_redeclare_discovery_patch(*, current_text: str, step: dict, selected_rhs_symbol: str) -> tuple[str, dict]:
    current = norm(current_text)
    match_text = norm(step.get("match_text"))
    canonical_rhs_symbol = parse_canonical_rhs_from_repair_step(step)
    if not match_text:
        return current, {"applied": False, "reason": "missing_match_text", "selected_rhs_symbol": norm(selected_rhs_symbol), "canonical_rhs_symbol": canonical_rhs_symbol}
    if match_text not in current:
        return current, {"applied": False, "reason": "match_text_not_found", "selected_rhs_symbol": norm(selected_rhs_symbol), "canonical_rhs_symbol": canonical_rhs_symbol}
    replacement_text = synthesize_redeclare_replacement(match_text=match_text, selected_rhs_symbol=selected_rhs_symbol)
    updated = current.replace(match_text, replacement_text, 1)
    return updated, {
        "applied": updated != current,
        "reason": "applied_discovery_patch" if updated != current else "text_unchanged_after_patch",
        "selected_rhs_symbol": norm(selected_rhs_symbol),
        "canonical_rhs_symbol": canonical_rhs_symbol,
        "replacement_text": replacement_text,
    }


def apply_exact_repair_step(model_text: str, step: dict) -> tuple[str, dict]:
    current = norm(model_text)
    match_text = norm(step.get("match_text"))
    replacement_text = norm(step.get("replacement_text"))
    if not match_text:
        return current, {"applied": False, "reason": "missing_match_text"}
    if match_text not in current:
        return current, {"applied": False, "reason": "match_text_not_found"}
    updated = current.replace(match_text, replacement_text, 1)
    return updated, {
        "applied": updated != current,
        "reason": "applied" if updated != current else "unchanged",
        "patch_type": norm(step.get("patch_type")),
    }


def run_dry_run(model_name: str, model_text: str, *, timeout_sec: int = 120) -> dict:
    script = "\n".join(
        [
            "loadModel(Modelica);",
            'loadFile("model.mo");',
            f"checkModel({model_name});",
            "getErrorString();",
            "",
        ]
    )
    with temporary_workspace("v0330_dry_run_") as td:
        target = Path(td) / "model.mo"
        target.write_text(norm(model_text), encoding="utf-8")
        rc, output = run_omc_script_docker(
            script_text=script,
            timeout_sec=timeout_sec,
            cwd=td,
            image=DOCKER_IMAGE,
        )
    check_model_pass = "completed successfully" in str(output or "") and "Error:" not in str(output or "")
    diagnostic = build_diagnostic_ir_v0(
        output=str(output or ""),
        check_model_pass=bool(check_model_pass),
        simulate_pass=True,
        expected_stage="check",
        declared_failure_type="simulate_error",
        declared_context_hints={},
    )
    return {
        "return_code": int(rc),
        "check_model_pass": bool(check_model_pass),
        "output_excerpt": norm(output)[:1200],
        "error_type": norm(diagnostic.get("error_type")),
        "error_subtype": norm(diagnostic.get("error_subtype")),
        "stage": norm(diagnostic.get("stage")),
        "observed_phase": norm(diagnostic.get("observed_phase")),
        "reason": norm(diagnostic.get("reason")),
        "error_signature": error_signature_from_text(norm(output)),
    }


def medium_redeclare_target_hit(result: dict) -> bool:
    output_excerpt = norm(result.get("output_excerpt")).lower()
    return (
        norm(result.get("error_type")) == "model_check_error"
        and norm(result.get("stage")) == TARGET_STAGE
        and norm(result.get("error_subtype")) == TARGET_SUBTYPE
        and any(
            token in output_excerpt
            for token in (
                "medium.single",
                "medium.thermostates",
                "partial class medium",
                "redeclare",
            )
        )
    )


def fixture_dry_run_result(*, phase: str = "target_hit") -> dict:
    if phase == "resolved":
        return {
            "return_code": 0,
            "check_model_pass": True,
            "output_excerpt": "Check of model passed.",
            "error_type": "none",
            "error_subtype": "none",
            "stage": "none",
            "observed_phase": "check",
            "reason": "",
            "error_signature": "",
        }
    return {
        "return_code": 1,
        "check_model_pass": False,
        "output_excerpt": "Fixture Medium.singleState compile_failure_unknown result.",
        "error_type": "model_check_error",
        "error_subtype": "compile_failure_unknown",
        "stage": "check",
        "observed_phase": "check",
        "reason": "model check failed",
        "error_signature": "Error: Fixture Medium.singleState compile_failure_unknown result.",
    }


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DISCOVERY_OUT_DIR",
    "DEFAULT_DISCOVERY_RESULTS_DIR",
    "DEFAULT_FIRST_FIX_OUT_DIR",
    "DEFAULT_FIRST_FIX_RESULTS_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_SURFACE_INDEX_OUT_DIR",
    "DEFAULT_DUAL_RECHECK_OUT_DIR",
    "DEFAULT_DUAL_RECHECK_RESULTS_DIR",
    "DEFAULT_V0329_CLOSEOUT_PATH",
    "DEFAULT_V0329_ENTRY_SPEC_PATH",
    "DEFAULT_V0329_ENTRY_TASKSET_PATH",
    "DEFAULT_V0329_PATCH_CONTRACT_PATH",
    "DOCKER_IMAGE",
    "SCHEMA_PREFIX",
    "SURFACE_INDEX_FIXTURE",
    "TARGET_STAGE",
    "TARGET_STAGE_SUBTYPE",
    "TARGET_SUBTYPE",
    "apply_exact_repair_step",
    "apply_medium_redeclare_discovery_patch",
    "build_medium_candidate_rhs_symbols",
    "error_signature_from_text",
    "extract_component_name_from_step",
    "fixture_dry_run_result",
    "load_json",
    "medium_redeclare_target_hit",
    "norm",
    "now_utc",
    "parse_canonical_rhs_from_repair_step",
    "parse_medium_alias_bindings",
    "parse_redeclare_clause_rhs_values",
    "rank_medium_rhs_candidates",
    "run_dry_run",
    "synthesize_redeclare_replacement",
    "write_json",
    "write_text",
]
