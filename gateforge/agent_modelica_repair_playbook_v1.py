from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STRATEGIES = {
    "model_check_error": [
        {
            "strategy_id": "mc_undefined_symbol_guard",
            "name": "Compile Symbol Guard",
            "actions": [
                "scan undefined symbols and broken references",
                "align parameter/variable declarations with equations",
                "rerun checkModel before any simulate attempt",
            ],
            "priority": 100,
        },
        {
            "strategy_id": "mc_connection_consistency",
            "name": "Connection Consistency Fix",
            "actions": [
                "repair connector cardinality and causality",
                "verify each connect pair has matching connector type",
            ],
            "priority": 90,
        },
    ],
    "simulate_error": [
        {
            "strategy_id": "sim_init_stability",
            "name": "Initialization Stability",
            "actions": [
                "stabilize start values and initial equations",
                "reduce discontinuity and hard switching at t=0",
                "rerun short-horizon simulation for sanity",
            ],
            "priority": 100,
        },
        {
            "strategy_id": "sim_solver_envelope",
            "name": "Solver Envelope Tune",
            "actions": [
                "check stiff dynamics and event density",
                "tighten physically invalid parameter ranges",
            ],
            "priority": 85,
        },
    ],
    "semantic_regression": [
        {
            "strategy_id": "sem_invariant_first",
            "name": "Invariant First Repair",
            "actions": [
                "repair sign/unit/constraint violations first",
                "ensure physics contract metrics return within expected bounds",
                "verify no-regression against baseline evidence",
            ],
            "priority": 100,
        },
        {
            "strategy_id": "sem_control_behavior_repair",
            "name": "Control Behavior Repair",
            "actions": [
                "inspect overshoot/settling-time/steady-state deltas",
                "restore controller gains and limit logic consistency",
            ],
            "priority": 88,
        },
    ],
}


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
        "# GateForge Agent Modelica Repair Playbook v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- strategy_count: `{payload.get('strategy_count')}`",
        "",
        "## Coverage",
        "",
    ]
    coverage = payload.get("coverage", {})
    if isinstance(coverage, dict) and coverage:
        for key in sorted(coverage.keys()):
            lines.append(f"- {key}: `{coverage.get(key)}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def build_repair_playbook_from_corpus(corpus: dict) -> dict:
    rows = corpus.get("rows") if isinstance(corpus.get("rows"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]
    by_failure: dict[str, Counter[str]] = {}
    for row in rows:
        ftype = str(row.get("failure_type") or "unknown").strip().lower()
        stage = str(row.get("expected_stage") or "unknown").strip().lower()
        bucket = by_failure.setdefault(ftype, Counter())
        bucket[stage] += 1

    playbook_entries: list[dict] = []
    coverage: dict[str, dict] = {}
    for ftype, strategies in DEFAULT_STRATEGIES.items():
        stage_counter = by_failure.get(ftype, Counter())
        top_stage = stage_counter.most_common(1)[0][0] if stage_counter else "unknown"
        coverage[ftype] = {
            "rows": int(sum(stage_counter.values())),
            "top_stage": top_stage,
        }
        for strategy in strategies:
            playbook_entries.append(
                {
                    "failure_type": ftype,
                    "strategy_id": strategy["strategy_id"],
                    "name": strategy["name"],
                    "priority": int(strategy.get("priority", 50)),
                    "actions": [str(x) for x in strategy.get("actions", []) if isinstance(x, str)],
                    "preferred_stage": top_stage,
                }
            )

    return {
        "schema_version": "agent_modelica_repair_playbook_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "strategy_count": len(playbook_entries),
        "coverage": coverage,
        "playbook": playbook_entries,
    }


def load_repair_playbook(path: str | None) -> dict:
    if not isinstance(path, str) or not path.strip():
        return {
            "schema_version": "agent_modelica_repair_playbook_v1",
            "status": "PASS",
            "playbook": [
                {
                    "failure_type": ftype,
                    "strategy_id": strategy["strategy_id"],
                    "name": strategy["name"],
                    "priority": int(strategy.get("priority", 50)),
                    "actions": [str(x) for x in strategy.get("actions", []) if isinstance(x, str)],
                    "preferred_stage": "unknown",
                }
                for ftype, strategies in DEFAULT_STRATEGIES.items()
                for strategy in strategies
            ],
            "source": "builtin_default",
        }
    payload = _load_json(path)
    playbook = payload.get("playbook") if isinstance(payload.get("playbook"), list) else []
    if not playbook:
        raise ValueError(f"repair playbook has no entries: {path}")
    payload["source"] = path
    return payload


def recommend_repair_strategy(playbook_payload: dict, failure_type: str, expected_stage: str | None = None) -> dict:
    entries = playbook_payload.get("playbook") if isinstance(playbook_payload.get("playbook"), list) else []
    entries = [x for x in entries if isinstance(x, dict)]
    ftype = str(failure_type or "unknown").strip().lower()
    stage = str(expected_stage or "unknown").strip().lower()

    candidates = [x for x in entries if str(x.get("failure_type") or "").strip().lower() == ftype]
    if not candidates:
        return {
            "strategy_id": "generic_repair_fallback",
            "name": "Generic Repair Fallback",
            "priority": 0,
            "confidence": 0.2,
            "reason": "no_failure_type_match",
            "actions": [
                "classify compiler/runtime/semantic signal",
                "apply minimal deterministic fix and rerun hard gates",
            ],
        }

    ranked = sorted(
        candidates,
        key=lambda x: (
            0 if str(x.get("preferred_stage") or "unknown").strip().lower() == stage else 1,
            -int(x.get("priority", 0) or 0),
            str(x.get("strategy_id") or ""),
        ),
    )
    top = ranked[0]
    stage_match = str(top.get("preferred_stage") or "unknown").strip().lower() == stage
    return {
        "strategy_id": str(top.get("strategy_id") or "generic_repair_fallback"),
        "name": str(top.get("name") or "Generic Repair"),
        "priority": int(top.get("priority", 0) or 0),
        "confidence": 0.85 if stage_match else 0.7,
        "reason": "stage_matched" if stage_match else "failure_type_matched",
        "actions": [str(x) for x in (top.get("actions") or []) if isinstance(x, str)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build modelica repair playbook from failure-repair corpus")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_repair_playbook_v1/playbook.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    corpus = _load_json(args.corpus)
    payload = build_repair_playbook_from_corpus(corpus)
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "strategy_count": payload.get("strategy_count")}))


if __name__ == "__main__":
    main()
