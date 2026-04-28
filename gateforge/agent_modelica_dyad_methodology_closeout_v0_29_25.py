from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "dyad_methodology_closeout_v0_29_25"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_dyad_methodology_closeout(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    dyad_ab = _load_json(REPO_ROOT / "artifacts" / "dyad_ab_v0_29_11" / "summary" / "summary.json")
    semantic_repeat = _load_json(
        REPO_ROOT / "artifacts" / "dyad_semantic_rerun_v0_29_14" / "summary" / "summary.json"
    )
    context_probe = _load_json(
        REPO_ROOT / "artifacts" / "modelica_kb_context_probe_v0_29_17" / "summary" / "summary.json"
    )
    policy_probe = _load_json(
        REPO_ROOT / "artifacts" / "replaceable_policy_probe_v0_29_18" / "summary" / "summary.json"
    )
    multicandidate_repeat = _load_json(
        REPO_ROOT / "artifacts" / "multicandidate_repeatability_v0_29_20" / "summary" / "summary.json"
    )
    family_repeat = _load_json(
        REPO_ROOT / "artifacts" / "replaceable_family_repeatability_v0_29_22" / "summary" / "summary.json"
    )
    submit_probe = _load_json(
        REPO_ROOT / "artifacts" / "submit_discipline_probe_v0_29_23" / "summary" / "summary.json"
    )
    oracle_probe = _load_json(
        REPO_ROOT / "artifacts" / "oracle_boundary_probe_v0_29_24" / "summary" / "summary.json"
    )

    methods = [
        {
            "method": "tool_use_harness",
            "classification": "promote_as_default_architecture",
            "evidence": "LLM-controlled tool use replaced fixed-round repair as the active harness before v0.29.x.",
        },
        {
            "method": "broad_structural_diagnostics",
            "classification": "do_not_enable_globally",
            "evidence": "v0.29.11 showed structural profile regressions on the 21-case hard boundary set.",
        },
        {
            "method": "family_gated_narrow_diagnostics",
            "classification": "research_only_positive_but_unstable",
            "evidence": "semantic narrow profile produced positive signal, but repeatability failed in v0.29.14.",
        },
        {
            "method": "specialized_connector_or_replaceable_diagnostics",
            "classification": "diagnostic_asset_not_default_capability",
            "evidence": "tools are useful for attribution and trajectory inspection, but pass-rate gain is not stable.",
        },
        {
            "method": "knowledge_context_or_retrieval_block",
            "classification": "retain_as_asset_do_not_default",
            "evidence": f"v0.29.17 decision: {context_probe.get('decision', 'missing')}.",
        },
        {
            "method": "policy_warning_prompt",
            "classification": "not_sufficient",
            "evidence": f"v0.29.18 decision: {policy_probe.get('decision', 'missing')}.",
        },
        {
            "method": "transparent_multicandidate_prompt",
            "classification": "behavior_change_not_stable_capability",
            "evidence": f"v0.29.20 decision: {multicandidate_repeat.get('decision', 'missing')}.",
        },
        {
            "method": "submit_discipline_prompt",
            "classification": "partial_positive_signal",
            "evidence": f"v0.29.23 decision: {submit_probe.get('decision', 'missing')}.",
        },
        {
            "method": "oracle_boundary_prompt",
            "classification": "negative_result",
            "evidence": f"v0.29.24 decision: {oracle_probe.get('decision', 'missing')}.",
        },
    ]

    summary = {
        "version": "v0.29.25",
        "status": "PASS",
        "analysis_scope": "dyad_methodology_closeout",
        "artifact_inputs": {
            "dyad_ab_decision": dyad_ab.get("decision", ""),
            "semantic_repeat_decision": semantic_repeat.get("decision", ""),
            "context_probe_decision": context_probe.get("decision", ""),
            "policy_probe_decision": policy_probe.get("decision", ""),
            "multicandidate_repeat_decision": multicandidate_repeat.get("decision", ""),
            "family_repeat_decision": family_repeat.get("decision", ""),
            "submit_probe_decision": submit_probe.get("decision", ""),
            "oracle_probe_decision": oracle_probe.get("decision", ""),
        },
        "method_classifications": methods,
        "frontier_conclusion": (
            "Dyad-inspired observation and diagnostic methods are useful research instruments, but v0.29.x does not "
            "support promoting broad structural tools, retrieval blocks, policy warnings, or oracle-boundary prompts "
            "as default capabilities. The strongest substrate outcome is the replaceable/partial/flow-contract family, "
            "where the main frontier is candidate acceptance and submit discipline rather than raw tool availability."
        ),
        "next_stage": {
            "recommended": "transparent_verifier_or_candidate_critique",
            "blocked_actions": [
                "do_not_add_more_prompt_discipline_profiles",
                "do_not_default_retrieval_context",
                "do_not_default_broad_structural_tools",
                "do_not_auto_submit_or_hide_candidate_selection",
            ],
        },
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
