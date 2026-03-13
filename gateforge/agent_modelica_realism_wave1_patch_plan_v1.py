from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_repair_playbook_v1 import load_repair_playbook


SCHEMA_VERSION = "agent_modelica_realism_wave1_patch_plan_v1"
TASKS_SCHEMA_VERSION = "agent_modelica_realism_wave1_patch_tasks_v1"
FOCUSED_PLAYBOOK_SCHEMA_VERSION = "agent_modelica_realism_wave1_focused_playbook_v1"
PATCH_TEMPLATES = {
    ("initialization_infeasible", "stage_truncation"): {
        "patch_kind": "operator_rework",
        "patch_target": "initialization_realism:when_initial_assert",
        "title": "Move initialization realism failures from check to simulate/init",
        "recommended_patch_action": "replace premature check-stage initialization triggers with compile-clean init-time assertions or conflicts that surface during initialization",
        "rationale": "Current initialization mutants fail during checkModel, so realism evidence never exercises init-time repair behavior.",
        "code_targets": [
            "gateforge/agent_modelica_electrical_mutant_taskset_v0.py",
            "gateforge/agent_modelica_diagnostic_ir_v0.py",
        ],
        "planned_changes": [
            "replace initialization trigger edits with compile-clean init-time assertions or equivalent initialization conflicts",
            "preserve checkModel pass so the failure manifests during initialization/simulate",
            "emit stronger initialization markers so diagnostic mapping lands on simulate_error/init_failure",
        ],
        "acceptance_checks": [
            "initialization_truncated_by_check_count drops to zero",
            "majority of initialization_infeasible tasks fail during simulate/init",
            "initialization category remains distinct from topology_wiring in L5 breakdown",
        ],
        "playbook_actions": [
            "treat initialization realism failures as simulate/init repair targets, not compile-stage repairs",
            "avoid broad structural rewrites before resolving start/fixed or initial equation conflicts",
        ],
        "priority_boost": 25,
    },
    ("connector_mismatch", "subtype_signal_gap"): {
        "patch_kind": "operator_and_mapping_rework",
        "patch_target": "topology_realism:connector_port_typo",
        "title": "Strengthen connector mismatch signal and subtype mapping",
        "recommended_patch_action": "replace typo-only connector edits with explicit incompatible connector/type/causality mismatches and tighten subtype mapping",
        "rationale": "Connector tasks reach the right canonical type and stage, but the subtype collapses into compile_failure_unknown.",
        "code_targets": [
            "gateforge/agent_modelica_electrical_mutant_taskset_v0.py",
            "gateforge/agent_modelica_diagnostic_ir_v0.py",
        ],
        "planned_changes": [
            "prefer explicit incompatible connector type or causality mismatches over typo-only bad port names",
            "keep connector/wiring edits local so the intended topology failure remains obvious",
            "promote connector-specific diagnostic markers before generic compile_failure_unknown fallback",
        ],
        "acceptance_checks": [
            "majority of connector_mismatch tasks map to connector_mismatch or clear connectivity subtypes",
            "connector_subtype_match_rate_pct rises above zero",
            "topology_wiring category keeps nonzero sample coverage",
        ],
        "playbook_actions": [
            "inspect connector type/name/causality mismatches before generic compile symbol fixes",
            "rerun checkModel after each connect repair and preserve connector semantics",
        ],
        "priority_boost": 20,
    },
    ("underconstrained_system", "manifestation_signal_gap"): {
        "patch_kind": "operator_rework",
        "patch_target": "topology_realism:drop_connect_equation",
        "title": "Force underconstrained_system to manifest as a structural failure",
        "recommended_patch_action": "strengthen dropped-connect topology edits so the model surfaces an underconstrained structural failure before any repair attempt",
        "rationale": "Current underconstrained_system tasks can resolve without ever emitting the intended structural failure signal, so realism evidence never validates that failure mode.",
        "code_targets": [
            "gateforge/agent_modelica_electrical_mutant_taskset_v0.py",
            "gateforge/agent_modelica_diagnostic_ir_v0.py",
        ],
        "planned_changes": [
            "strengthen dropped-connect mutations so they break structural balance while still compiling into the expected check-stage failure",
            "avoid no-op or self-healing topology edits that leave the model directly solvable",
            "ensure diagnostic mapping prefers underconstrained structural hints before generic none/none outcomes",
        ],
        "acceptance_checks": [
            "underconstrained_system tasks emit a non-none structural failure signal before repair",
            "manifestation missing-signal count drops to zero for underconstrained_system",
            "topology_wiring category retains stable task coverage and diagnostic separation",
        ],
        "playbook_actions": [
            "treat structurally silent underconstrained tasks as realism generation defects before tuning repair policy",
            "verify dropped-connect edits produce observable balance/connectivity failures before evaluating repair success",
        ],
        "priority_boost": 22,
    },
    ("underconstrained_system", "manifestation_stage_shift"): {
        "patch_kind": "operator_and_mapping_rework",
        "patch_target": "topology_realism:drop_connect_equation",
        "title": "Pull underconstrained_system back to check/model_check",
        "recommended_patch_action": "tighten dropped-connect realism edits so structural underconstraint is detected during check/model-check instead of drifting into simulate",
        "rationale": "Current underconstrained_system tasks emit a failure signal, but it lands in the wrong canonical type or stage, so realism evidence validates the wrong manifestation path.",
        "code_targets": [
            "gateforge/agent_modelica_electrical_mutant_taskset_v0.py",
            "gateforge/agent_modelica_diagnostic_ir_v0.py",
        ],
        "planned_changes": [
            "use non-elidable structural probes so dropped-connect edits remain underdetermined during checkModel",
            "prefer structural underconstraint markers before generic simulate failure fallback when solver logs echo the same defect",
            "keep the topology defect local so the first surfaced signal stays on the intended check/model_check path",
        ],
        "acceptance_checks": [
            "underconstrained_system canonical_match_rate_pct rises above zero",
            "underconstrained_system stage_match_rate_pct rises above zero",
            "underconstrained_system no longer collapses into simulate_error/simulation_failure_unknown",
        ],
        "playbook_actions": [
            "treat check-to-simulate manifestation drift as a realism generation defect before tuning repair policy",
            "verify dropped-connect edits fail during checkModel before evaluating repair success on underconstrained tasks",
        ],
        "priority_boost": 21,
    },
    ("underconstrained_system", "repair_policy_gap"): {
        "patch_kind": "playbook_policy_update",
        "patch_target": "repair_playbook:underconstrained_system",
        "title": "Focus repair policy on restoring structural balance",
        "recommended_patch_action": "promote topology balance restore actions before broader rewrites for underconstrained_system tasks",
        "rationale": "The structural signal is correct, but the current repair policy still fails to recover these tasks.",
        "code_targets": [
            "gateforge/agent_modelica_repair_playbook_v1.py",
            "gateforge/agent_modelica_playbook_focus_update_v1.py",
        ],
        "planned_changes": [
            "promote topology balance restore strategies for underconstrained_system",
            "bias the playbook toward restoring dropped connects and conservation paths before equation rewrites",
            "keep operator family stable and fix policy sequencing instead of changing the mutation itself",
        ],
        "acceptance_checks": [
            "underconstrained_system repair success increases without weakening topology diagnosis quality",
            "repairs restore dangling conservation paths before broader rewrites",
        ],
        "playbook_actions": [
            "restore dangling conservation paths before any simulate attempt",
            "prefer minimal connection restoration over broad equation rewrites when the topology defect is already identified",
        ],
        "priority_boost": 15,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sorted_dict(payload: dict[str, object]) -> dict[str, object]:
    return {str(k): payload[k] for k in sorted(payload.keys())}


def _merge_actions(existing: list[str], extras: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for item in [*existing, *extras]:
        text = str(item).strip()
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _resolve_run_root(out_dir: str, run_id: str = "", run_root: str = "") -> Path:
    if run_root:
        return Path(run_root)
    if run_id:
        return Path(out_dir) / "runs" / run_id
    latest = _load_json(Path(out_dir) / "latest_run.json")
    latest_root = str(latest.get("run_root") or "")
    return Path(latest_root) if latest_root else Path(out_dir)


def _template_for(failure_type: str, priority_reason: str) -> dict:
    return dict(PATCH_TEMPLATES.get((failure_type, priority_reason)) or {})


def _dominant_operator(tasks: list[dict]) -> str:
    counts: dict[str, int] = {}
    for row in tasks:
        operator = str(row.get("mutation_operator") or "").strip()
        if not operator:
            continue
        counts[operator] = counts.get(operator, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ranked[0][0] if ranked else ""


def _focused_playbook(
    *,
    playbook_path: str,
    priorities: list[dict],
    out_path: Path,
) -> dict:
    playbook_payload = load_repair_playbook(playbook_path or None)
    entries = playbook_payload.get("playbook") if isinstance(playbook_payload.get("playbook"), list) else []
    entries = [dict(x) for x in entries if isinstance(x, dict)]
    by_failure_type = {str(row.get("failure_type") or ""): row for row in priorities if isinstance(row, dict)}

    promoted_entries = 0
    updated_entries: list[dict] = []
    playbook_updates: list[dict] = []
    for entry in entries:
        failure_type = str(entry.get("failure_type") or "")
        focus = by_failure_type.get(failure_type)
        updated = dict(entry)
        if focus:
            template = _template_for(failure_type, str(focus.get("priority_reason") or ""))
            boost = int(template.get("priority_boost") or 0)
            updated["priority"] = int(updated.get("priority", 0) or 0) + boost
            updated["actions"] = _merge_actions(
                [str(x) for x in (updated.get("actions") or []) if isinstance(x, str)],
                [str(x) for x in (template.get("playbook_actions") or []) if isinstance(x, str)],
            )
            updated["focus_tag"] = "realism_wave1_patch_plan"
            promoted_entries += 1
        updated_entries.append(updated)

    for index, row in enumerate(priorities, start=1):
        failure_type = str(row.get("failure_type") or "")
        template = _template_for(failure_type, str(row.get("priority_reason") or ""))
        playbook_updates.append(
            {
                "rank": index,
                "failure_type": failure_type,
                "priority_reason": str(row.get("priority_reason") or ""),
                "priority_boost": int(template.get("priority_boost") or 0),
                "recommended_focus_action": str(template.get("recommended_patch_action") or ""),
                "action_injections": [str(x) for x in (template.get("playbook_actions") or []) if isinstance(x, str)],
            }
        )

    payload = {
        "schema_version": FOCUSED_PLAYBOOK_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "status": "PASS",
        "focused_failure_count": len(priorities),
        "promoted_entries": promoted_entries,
        "source_playbook": playbook_payload.get("source") or "builtin_default",
        "playbook_updates": playbook_updates,
        "playbook": updated_entries,
    }
    _write_json(out_path, payload)
    _write_md(
        out_path.with_suffix(".md"),
        [
            "# Agent Modelica Realism Wave1 Focused Playbook",
            "",
            f"- status: `{payload.get('status')}`",
            f"- focused_failure_count: `{payload.get('focused_failure_count')}`",
            f"- promoted_entries: `{payload.get('promoted_entries')}`",
            f"- source_playbook: `{payload.get('source_playbook')}`",
        ],
    )
    return payload


def build_wave1_patch_plan_v1(
    *,
    run_root: str,
    playbook_path: str = "",
    update_final_summary: bool = True,
) -> dict:
    root = Path(run_root)
    final_summary_path = root / "final_run_summary.json"
    repair_queue_summary_path = root / "repair_queue_summary.json"
    repair_queue_tasks_path = root / "repair_queue_tasks.json"
    out_summary_path = root / "wave1_patch_plan_summary.json"
    out_tasks_path = root / "wave1_patch_plan_tasks.json"
    focused_playbook_path = root / "wave1_focused_playbook.json"

    final_summary = _load_json(final_summary_path)
    repair_queue = _load_json(repair_queue_summary_path)
    repair_queue_tasks = _load_json(repair_queue_tasks_path)

    reasons: list[str] = []
    status = "PASS"
    if not final_summary:
        status = "BLOCKED"
        reasons.append("final_run_summary_missing")
    if not repair_queue:
        status = "BLOCKED"
        reasons.append("repair_queue_missing")
    if not repair_queue_tasks:
        status = "BLOCKED"
        reasons.append("repair_queue_tasks_missing")
    if repair_queue and str(repair_queue.get("status") or "").upper() == "BLOCKED":
        status = "BLOCKED"
        reasons.append("repair_queue_blocked")

    priorities = repair_queue.get("priorities") if isinstance(repair_queue.get("priorities"), list) else []
    priorities = [row for row in priorities if isinstance(row, dict)]
    tasks = repair_queue_tasks.get("tasks") if isinstance(repair_queue_tasks.get("tasks"), list) else []
    tasks = [row for row in tasks if isinstance(row, dict)]

    operator_changes: list[dict] = []
    task_patch_queue: list[dict] = []
    playbook_updates: list[dict] = []
    focused_playbook_payload: dict = {}

    if status != "BLOCKED":
        for index, priority in enumerate(priorities, start=1):
            failure_type = str(priority.get("failure_type") or "")
            priority_reason = str(priority.get("priority_reason") or "")
            template = _template_for(failure_type, priority_reason)
            related_tasks = [row for row in tasks if str(row.get("failure_type") or "") == failure_type and str(row.get("priority_reason") or "") == priority_reason]
            dominant_operator = _dominant_operator(related_tasks)
            patch_target = str(template.get("patch_target") or f"{priority.get('mutation_operator_family') or 'unknown'}:{dominant_operator or 'unknown'}")
            operator_row = {
                "rank": index,
                "failure_type": failure_type,
                "category": str(priority.get("category") or ""),
                "mutation_operator_family": str(priority.get("mutation_operator_family") or ""),
                "mutation_operator": dominant_operator,
                "priority_reason": priority_reason,
                "patch_kind": str(template.get("patch_kind") or "generic_update"),
                "patch_target": patch_target,
                "title": str(template.get("title") or priority.get("recommended_action") or ""),
                "rationale": str(template.get("rationale") or ""),
                "recommended_patch_action": str(template.get("recommended_patch_action") or priority.get("recommended_action") or ""),
                "affected_task_count": int(priority.get("affected_task_count") or 0),
                "task_ids": [str(x) for x in (priority.get("task_ids") or []) if str(x)],
                "origin_task_ids": [str(x) for x in (priority.get("origin_task_ids") or []) if str(x)],
                "code_targets": [str(x) for x in (template.get("code_targets") or []) if isinstance(x, str)],
                "planned_changes": [str(x) for x in (template.get("planned_changes") or []) if isinstance(x, str)],
                "acceptance_checks": [str(x) for x in (template.get("acceptance_checks") or []) if isinstance(x, str)],
            }
            operator_changes.append(operator_row)
            playbook_updates.append(
                {
                    "rank": index,
                    "failure_type": failure_type,
                    "priority_reason": priority_reason,
                    "patch_target": patch_target,
                    "priority_boost": int(template.get("priority_boost") or 0),
                    "recommended_focus_action": str(template.get("recommended_patch_action") or ""),
                    "action_injections": [str(x) for x in (template.get("playbook_actions") or []) if isinstance(x, str)],
                }
            )

            for task in related_tasks:
                task_patch_queue.append(
                    {
                        "task_id": str(task.get("task_id") or ""),
                        "origin_task_id": str(task.get("origin_task_id") or ""),
                        "failure_type": failure_type,
                        "category": str(task.get("category") or ""),
                        "mutation_operator_family": str(task.get("mutation_operator_family") or ""),
                        "mutation_operator": str(task.get("mutation_operator") or ""),
                        "patch_target": patch_target,
                        "patch_kind": str(template.get("patch_kind") or "generic_update"),
                        "priority_reason": priority_reason,
                        "source_model_path": str(task.get("source_model_path") or ""),
                        "mutated_model_path": str(task.get("mutated_model_path") or ""),
                        "expected_stage": str(task.get("expected_stage") or ""),
                        "observed_stage": str(task.get("observed_stage") or ""),
                        "observed_subtype": str(task.get("observed_subtype") or ""),
                        "task_patch_focus": str(template.get("recommended_patch_action") or ""),
                        "mutated_objects": task.get("mutated_objects") if isinstance(task.get("mutated_objects"), list) else [],
                    }
                )

        focused_playbook_payload = _focused_playbook(
            playbook_path=playbook_path,
            priorities=priorities,
            out_path=focused_playbook_path,
        )

    top_change = operator_changes[0] if operator_changes else {}
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "status": status,
        "run_id": str(final_summary.get("run_id") or root.name),
        "run_root": str(root),
        "top_patch_target": str(top_change.get("patch_target") or ""),
        "top_patch_priority": str(repair_queue.get("top_repair_priority") or ""),
        "recommended_next_patch": str(top_change.get("recommended_patch_action") or ""),
        "operator_change_count": len(operator_changes),
        "playbook_update_count": len(playbook_updates),
        "task_patch_queue_count": len(task_patch_queue),
        "operator_changes": operator_changes,
        "playbook_updates": playbook_updates,
        "focused_playbook_status": str(focused_playbook_payload.get("status") or ("PASS" if status != "BLOCKED" else "")),
        "focused_playbook_path": str(focused_playbook_path if status != "BLOCKED" else ""),
        "reasons": sorted(set(reasons)),
        "inputs": {
            "final_run_summary": str(final_summary_path),
            "repair_queue_summary": str(repair_queue_summary_path),
            "repair_queue_tasks": str(repair_queue_tasks_path),
            "playbook": playbook_path or "builtin_default",
        },
    }
    tasks_payload = {
        "schema_version": TASKS_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "run_id": str(final_summary.get("run_id") or root.name),
        "run_root": str(root),
        "tasks": task_patch_queue,
    }
    _write_json(out_summary_path, summary)
    _write_json(out_tasks_path, tasks_payload)
    _write_md(
        out_summary_path.with_suffix(".md"),
        [
            "# Agent Modelica Realism Wave1 Patch Plan",
            "",
            f"- status: `{summary.get('status')}`",
            f"- top_patch_target: `{summary.get('top_patch_target')}`",
            f"- top_patch_priority: `{summary.get('top_patch_priority')}`",
            f"- recommended_next_patch: `{summary.get('recommended_next_patch')}`",
            f"- operator_change_count: `{summary.get('operator_change_count')}`",
            f"- playbook_update_count: `{summary.get('playbook_update_count')}`",
            f"- task_patch_queue_count: `{summary.get('task_patch_queue_count')}`",
            f"- reasons: `{summary.get('reasons')}`",
        ],
    )

    if update_final_summary and final_summary:
        final_summary["patch_plan_status"] = summary.get("status")
        final_summary["patch_plan_path"] = str(out_summary_path)
        final_summary["top_patch_target"] = str(summary.get("top_patch_target") or "")
        final_summary["focused_playbook_path"] = str(summary.get("focused_playbook_path") or "")
        paths = final_summary.get("paths") if isinstance(final_summary.get("paths"), dict) else {}
        paths["wave1_patch_plan_summary"] = str(out_summary_path)
        paths["wave1_patch_plan_tasks"] = str(out_tasks_path)
        if summary.get("focused_playbook_path"):
            paths["wave1_focused_playbook"] = str(focused_playbook_path)
        final_summary["paths"] = paths
        _write_json(final_summary_path, final_summary)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build wave1 patch plan from finalized realism evidence")
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_l4_realism_evidence_v1")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-root", default="")
    parser.add_argument("--playbook", default="")
    parser.add_argument("--update-final-summary", default="1")
    args = parser.parse_args()

    run_root = _resolve_run_root(args.out_dir, run_id=args.run_id, run_root=args.run_root)
    payload = build_wave1_patch_plan_v1(
        run_root=str(run_root),
        playbook_path=str(args.playbook or ""),
        update_final_summary=str(args.update_final_summary).strip() not in {"0", "false", "False"},
    )
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
