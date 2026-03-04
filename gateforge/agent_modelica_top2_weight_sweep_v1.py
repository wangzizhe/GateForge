from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
        "# GateForge Agent Modelica Top2 Weight Sweep v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- run_count: `{payload.get('run_count')}`",
        f"- best_run_id: `{payload.get('best_run_id')}`",
        "",
        "## Best Config",
        "",
    ]
    best = payload.get("best_config", {})
    if isinstance(best, dict) and best:
        for key in ("outcome_weight", "strategy_weight", "strategy_target_score"):
            lines.append(f"- {key}: `{best.get(key)}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _run_module(module_name: str, argv: list[str]) -> None:
    proc = subprocess.run([sys.executable, "-m", module_name, *argv], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout)


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _score(before: dict, after: dict) -> tuple[float, dict]:
    b_delta = before.get("delta") if isinstance(before.get("delta"), dict) else {}
    a_delta = after.get("delta") if isinstance(after.get("delta"), dict) else {}
    safety_ok = _to_float(a_delta.get("physics_fail_count")) <= 0.0 and _to_float(a_delta.get("regression_count")) <= 0.0

    # Prefer higher pass-rate delta, then lower time/rounds deltas.
    metric_score = (
        (_to_float(a_delta.get("success_at_k_pct")) - _to_float(b_delta.get("success_at_k_pct"))) * 2.0
        + (_to_float(b_delta.get("median_time_to_pass_sec")) - _to_float(a_delta.get("median_time_to_pass_sec"))) * 0.2
        + (_to_float(b_delta.get("median_repair_rounds")) - _to_float(a_delta.get("median_repair_rounds"))) * 0.5
    )
    if not safety_ok:
        metric_score -= 1000.0
    return round(metric_score, 4), {"safety_ok": safety_ok}


def _parse_weight_triples(raw: str) -> list[tuple[float, float, float]]:
    triples: list[tuple[float, float, float]] = []
    for token in [x.strip() for x in raw.split(";") if x.strip()]:
        parts = [x.strip() for x in token.split(",") if x.strip()]
        if len(parts) != 3:
            continue
        triples.append((float(parts[0]), float(parts[1]), float(parts[2])))
    return triples


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep top2 queue weights and pick best config")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--base-playbook", required=True)
    parser.add_argument("--weight-triples", default="0.8,0.2,0.8;0.7,0.3,0.8;0.6,0.4,0.8")
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_top2_weight_sweep_v1")
    parser.add_argument("--out", default="artifacts/agent_modelica_top2_weight_sweep_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    triples = _parse_weight_triples(str(args.weight_triples))
    if not triples:
        raise SystemExit("no valid --weight-triples provided")

    runs: list[dict] = []
    for idx, (ow, sw, ts) in enumerate(triples, start=1):
        run_id = f"run_{idx}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        _run_module(
            "gateforge.agent_modelica_strategy_ab_test_v1",
            [
                "--taskset",
                args.taskset,
                "--treatment-playbook",
                args.base_playbook,
                "--mode",
                "evidence",
                "--out-dir",
                str(run_dir / "before"),
                "--out",
                str(run_dir / "ab_before.json"),
            ],
        )
        _run_module(
            "gateforge.agent_modelica_top_failure_queue_v1",
            [
                "--ab-summary",
                str(run_dir / "ab_before.json"),
                "--top-k",
                str(max(1, int(args.top_k))),
                "--outcome-weight",
                str(ow),
                "--strategy-weight",
                str(sw),
                "--strategy-target-score",
                str(ts),
                "--out",
                str(run_dir / "top2_queue.json"),
            ],
        )
        _run_module(
            "gateforge.agent_modelica_playbook_focus_update_v1",
            [
                "--playbook",
                args.base_playbook,
                "--queue",
                str(run_dir / "top2_queue.json"),
                "--out",
                str(run_dir / "focused_playbook.json"),
            ],
        )
        _run_module(
            "gateforge.agent_modelica_strategy_ab_test_v1",
            [
                "--taskset",
                args.taskset,
                "--treatment-playbook",
                str(run_dir / "focused_playbook.json"),
                "--mode",
                "evidence",
                "--out-dir",
                str(run_dir / "after"),
                "--out",
                str(run_dir / "ab_after.json"),
            ],
        )

        before = _load_json(str(run_dir / "ab_before.json"))
        after = _load_json(str(run_dir / "ab_after.json"))
        queue = _load_json(str(run_dir / "top2_queue.json"))
        score, score_meta = _score(before=before, after=after)
        runs.append(
            {
                "run_id": run_id,
                "config": {
                    "outcome_weight": ow,
                    "strategy_weight": sw,
                    "strategy_target_score": ts,
                },
                "score": score,
                "score_meta": score_meta,
                "before_decision": before.get("decision"),
                "after_decision": after.get("decision"),
                "queue": queue.get("queue", []),
                "paths": {
                    "ab_before": str(run_dir / "ab_before.json"),
                    "ab_after": str(run_dir / "ab_after.json"),
                    "top2_queue": str(run_dir / "top2_queue.json"),
                },
            }
        )

    ranked = sorted(runs, key=lambda x: (-float(x.get("score", 0.0)), str(x.get("run_id") or "")))
    best = ranked[0] if ranked else {}
    payload = {
        "schema_version": "agent_modelica_top2_weight_sweep_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "run_count": len(runs),
        "best_run_id": best.get("run_id"),
        "best_config": best.get("config", {}),
        "runs": ranked,
        "sources": {
            "taskset": args.taskset,
            "base_playbook": args.base_playbook,
            "weight_triples": str(args.weight_triples),
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "best_run_id": payload.get("best_run_id")}))


if __name__ == "__main__":
    main()
