from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Repair Capability Learner v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- success_row_count: `{payload.get('success_row_count')}`",
        f"- learned_failure_type_count: `{payload.get('learned_failure_type_count')}`",
        "",
    ]
    coverage = payload.get("learned_failure_types") if isinstance(payload.get("learned_failure_types"), list) else []
    lines.append("## Learned Failure Types")
    lines.append("")
    if coverage:
        lines.extend([f"- `{x}`" for x in coverage])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _success_rows(memory_payload: dict) -> list[dict]:
    rows = memory_payload.get("rows") if isinstance(memory_payload.get("rows"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]
    out: list[dict] = []
    for row in rows:
        if bool(row.get("success")) or str(row.get("status") or "").strip().upper() == "PASS":
            out.append(row)
    return out


def learn_capability_assets(
    memory_payload: dict,
    *,
    min_success_count_per_failure_type: int = 3,
    top_actions_per_failure_type: int = 4,
    top_strategies_per_failure_type: int = 2,
) -> dict:
    rows = _success_rows(memory_payload)
    by_failure: dict[str, list[dict]] = {}
    for row in rows:
        ftype = str(row.get("failure_type") or "").strip().lower()
        if not ftype:
            continue
        by_failure.setdefault(ftype, []).append(row)

    patch_adaptations: dict[str, dict] = {}
    retrieval_policy = {
        "schema_version": "agent_modelica_retrieval_policy_v1",
        "top_k_by_failure_type": {},
        "strategy_id_bonus_by_failure_type": {},
        "failure_match_bonus": 2.0,
        "model_overlap_weight": 1.0,
    }
    learned_failure_types: list[str] = []
    skipped: list[str] = []

    for ftype, frows in sorted(by_failure.items()):
        if len(frows) < max(1, int(min_success_count_per_failure_type)):
            skipped.append(ftype)
            continue
        learned_failure_types.append(ftype)
        action_counter: Counter[str] = Counter()
        strategy_counter: Counter[str] = Counter()
        for row in frows:
            actions = row.get("action_trace") if isinstance(row.get("action_trace"), list) else []
            for action in actions:
                if isinstance(action, str) and action.strip():
                    action_counter[action.strip()] += 1
            strategy = str(row.get("used_strategy") or row.get("strategy_id") or "").strip()
            if strategy:
                strategy_counter[strategy] += 1

        top_actions = [x for x, _ in action_counter.most_common(max(1, int(top_actions_per_failure_type)))]
        top_strategies = strategy_counter.most_common(max(1, int(top_strategies_per_failure_type)))
        top_action_frequency = {
            action: int(count)
            for action, count in action_counter.most_common(max(1, int(top_actions_per_failure_type)))
        }
        patch_adaptations[ftype] = {
            "actions": top_actions,
            "action_frequency": top_action_frequency,
            "min_success_count_applied": int(min_success_count_per_failure_type),
        }
        retrieval_policy["top_k_by_failure_type"][ftype] = min(5, 2 + max(0, len(frows) // 10))
        retrieval_policy["strategy_id_bonus_by_failure_type"][ftype] = {
            strategy_id: round(min(2.0, float(count) / float(max(1, len(frows)))), 4)
            for strategy_id, count in top_strategies
        }

    return {
        "success_row_count": len(rows),
        "learned_failure_type_count": len(learned_failure_types),
        "learned_failure_types": learned_failure_types,
        "skipped_failure_types": skipped,
        "patch_template_adaptations": patch_adaptations,
        "retrieval_policy": retrieval_policy,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Learn patch-template and retrieval policy assets from private repair memory")
    parser.add_argument("--repair-memory", required=True)
    parser.add_argument("--min-success-count-per-failure-type", type=int, default=3)
    parser.add_argument("--top-actions-per-failure-type", type=int, default=4)
    parser.add_argument("--top-strategies-per-failure-type", type=int, default=2)
    parser.add_argument(
        "--out-patch-template-adaptations",
        default="data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json",
    )
    parser.add_argument(
        "--out-retrieval-policy",
        default="data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json",
    )
    parser.add_argument("--out", default="artifacts/agent_modelica_repair_capability_learner_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    memory = _load_json(args.repair_memory)
    learned = learn_capability_assets(
        memory_payload=memory,
        min_success_count_per_failure_type=max(1, int(args.min_success_count_per_failure_type)),
        top_actions_per_failure_type=max(1, int(args.top_actions_per_failure_type)),
        top_strategies_per_failure_type=max(1, int(args.top_strategies_per_failure_type)),
    )

    patch_adaptations = {
        "schema_version": "agent_modelica_patch_template_adaptations_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "failure_types": learned.get("patch_template_adaptations"),
        "sources": {"repair_memory": args.repair_memory},
    }
    retrieval_policy = dict(learned.get("retrieval_policy") or {})
    retrieval_policy["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    retrieval_policy["sources"] = {"repair_memory": args.repair_memory}

    _write_json(args.out_patch_template_adaptations, patch_adaptations)
    _write_json(args.out_retrieval_policy, retrieval_policy)

    summary = {
        "schema_version": "agent_modelica_repair_capability_learner_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if int(learned.get("learned_failure_type_count", 0)) > 0 else "NEEDS_REVIEW",
        **learned,
        "out_patch_template_adaptations": args.out_patch_template_adaptations,
        "out_retrieval_policy": args.out_retrieval_policy,
        "sources": {"repair_memory": args.repair_memory},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "learned_failure_type_count": summary.get("learned_failure_type_count")}))


if __name__ == "__main__":
    main()
