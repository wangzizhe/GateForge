from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _norm_text(value: object) -> str:
    return str(value or "").strip().lower()


def _token_overlap(a: str, b: str) -> int:
    sa = {x for x in a.replace("/", " ").replace("_", " ").split() if x}
    sb = {x for x in b.replace("/", " ").replace("_", " ").split() if x}
    return len(sa & sb)


def _success_state(row: dict) -> str:
    for key in ("passed", "pass", "success", "is_success", "success_flag"):
        if key in row:
            value = row.get(key)
            if isinstance(value, bool):
                return "success" if value else "fail"
            if isinstance(value, (int, float)):
                return "success" if float(value) > 0 else "fail"
            text = str(value or "").strip().lower()
            if text in {"pass", "passed", "success", "ok", "true", "1"}:
                return "success"
            if text in {"fail", "failed", "error", "timeout", "false", "0"}:
                return "fail"
    for key in ("decision", "result", "outcome", "gate", "status"):
        if key not in row:
            continue
        text = str(row.get(key) or "").strip().lower()
        if text in {"pass", "passed", "success", "ok"}:
            return "success"
        if text in {"fail", "failed", "error", "timeout"}:
            return "fail"
    return "unknown"


def retrieve_repair_examples(
    history_payload: dict,
    failure_type: str,
    model_hint: str = "",
    top_k: int = 2,
) -> dict:
    rows = history_payload.get("rows") if isinstance(history_payload.get("rows"), list) else []
    if not rows:
        rows = history_payload.get("records") if isinstance(history_payload.get("records"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]

    ftype = _norm_text(failure_type)
    hint = _norm_text(model_hint)

    prepared_rows: list[dict] = []
    for row in rows:
        row_ftype = _norm_text(row.get("failure_type"))
        row_model = _norm_text(row.get("model_id") or row.get("source_model_path") or row.get("target_model_id"))
        strategy_id = str(row.get("used_strategy") or row.get("strategy_id") or "")
        actions = row.get("action_trace") if isinstance(row.get("action_trace"), list) else row.get("actions")
        actions = [str(x) for x in (actions or []) if isinstance(x, str)]
        prepared_rows.append(
            {
                "failure_type": row_ftype,
                "model": row_model,
                "strategy_id": strategy_id,
                "actions": actions,
                "success_state": _success_state(row),
            }
        )

    # If we have same failure type history, only retrieve from that slice.
    candidates = prepared_rows
    if ftype and any(x.get("failure_type") == ftype for x in prepared_rows):
        candidates = [x for x in prepared_rows if x.get("failure_type") == ftype]

    # If success labels exist in candidate set, prefer successful repairs only.
    has_success_signal = any(x.get("success_state") in {"success", "fail"} for x in candidates)
    if has_success_signal:
        candidates = [x for x in candidates if x.get("success_state") == "success"]

    ranked: list[dict] = []
    for row in candidates:
        row_ftype = str(row.get("failure_type") or "")
        row_model = str(row.get("model") or "")
        strategy_id = str(row.get("strategy_id") or "")
        actions = [str(x) for x in (row.get("actions") or []) if isinstance(x, str)]
        score = 0
        if row_ftype and row_ftype == ftype:
            score += 2
        score += min(2, _token_overlap(hint, row_model))
        if strategy_id:
            score += 1
        if score <= 0:
            continue
        ranked.append(
            {
                "score": score,
                "failure_type": row_ftype,
                "model": row_model,
                "strategy_id": strategy_id,
                "actions": actions,
                "success_state": str(row.get("success_state") or "unknown"),
            }
        )

    ranked = sorted(ranked, key=lambda x: (-int(x.get("score", 0)), x.get("strategy_id", ""), x.get("model", "")))
    selected = ranked[: max(0, int(top_k))]
    suggested_actions: list[str] = []
    seen: set[str] = set()
    for row in selected:
        for action in row.get("actions", []):
            item = str(action).strip()
            if item and item not in seen:
                suggested_actions.append(item)
                seen.add(item)

    return {
        "retrieved_count": len(selected),
        "examples": selected,
        "suggested_actions": suggested_actions,
    }


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
        "# GateForge Agent Modelica Retrieval Augmented Repair v1",
        "",
        f"- retrieved_count: `{payload.get('retrieved_count')}`",
        "",
        "## Suggested Actions",
        "",
    ]
    actions = payload.get("suggested_actions") if isinstance(payload.get("suggested_actions"), list) else []
    if actions:
        lines.extend([f"- {x}" for x in actions])
    else:
        lines.append("- none")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve similar successful repair traces for current task")
    parser.add_argument("--history", required=True)
    parser.add_argument("--failure-type", required=True)
    parser.add_argument("--model-hint", default="")
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--out", default="artifacts/agent_modelica_retrieval_augmented_repair_v1/retrieval.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    history = _load_json(args.history)
    payload = retrieve_repair_examples(
        history_payload=history,
        failure_type=args.failure_type,
        model_hint=args.model_hint,
        top_k=max(0, int(args.top_k)),
    )
    payload["schema_version"] = "agent_modelica_retrieval_augmented_repair_v1"
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["sources"] = {"history": args.history}
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"retrieved_count": payload.get("retrieved_count")}))


if __name__ == "__main__":
    main()
