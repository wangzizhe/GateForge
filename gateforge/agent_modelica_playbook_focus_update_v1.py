from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

FOCUS_ACTIONS = {
    "model_check_error": [
        "enforce compile-first edit order and rerun checkModel after each patch",
        "prioritize undefined-symbol and connector mismatch fixes before structural rewrites",
    ],
    "simulate_error": [
        "apply initialization sanity constraints before changing solver-facing equations",
        "bound unstable parameters and reduce event-trigger oscillation hotspots",
    ],
    "semantic_regression": [
        "execute invariant-first repair and verify physics contract on every candidate",
        "block any patch that improves speed but worsens steady-state or overshoot bounds",
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
        "# GateForge Agent Modelica Playbook Focus Update v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- queue_kind: `{payload.get('queue_kind')}`",
        f"- focused_failure_count: `{payload.get('focused_failure_count')}`",
        f"- promoted_entries: `{payload.get('promoted_entries')}`",
        f"- template_action_injections: `{payload.get('template_action_injections')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


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


def _focus_rows(queue_payload: dict) -> tuple[list[dict], str]:
    queue = queue_payload.get("queue") if isinstance(queue_payload.get("queue"), list) else []
    if queue:
        return [x for x in queue if isinstance(x, dict)], "queue"
    targets = queue_payload.get("targets") if isinstance(queue_payload.get("targets"), list) else []
    if targets:
        return [x for x in targets if isinstance(x, dict)], "targets"
    templates = queue_payload.get("templates") if isinstance(queue_payload.get("templates"), list) else []
    if templates:
        return [x for x in templates if isinstance(x, dict)], "templates"
    return [], "none"


def _template_actions_by_failure(rows: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in rows:
        ftype = str(row.get("failure_type") or "").strip()
        if not ftype:
            continue
        actions = row.get("actions") if isinstance(row.get("actions"), list) else []
        action_text = [str(x) for x in actions if isinstance(x, str)]
        if not action_text:
            continue
        current = out.get(ftype, [])
        out[ftype] = _merge_actions(current, action_text)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply top-failure focus update to repair playbook")
    parser.add_argument("--playbook", required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--priority-boost", type=int, default=15)
    parser.add_argument("--out", default="artifacts/agent_modelica_playbook_focus_update_v1/focused_playbook.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    playbook_payload = _load_json(args.playbook)
    queue_payload = _load_json(args.queue)

    entries = playbook_payload.get("playbook") if isinstance(playbook_payload.get("playbook"), list) else []
    entries = [x for x in entries if isinstance(x, dict)]
    queue, queue_kind = _focus_rows(queue_payload)
    focused_failures = [str(x.get("failure_type") or "") for x in queue if str(x.get("failure_type") or "")]
    template_actions = _template_actions_by_failure(queue)

    boost = int(args.priority_boost)
    promoted = 0
    template_action_injections = 0
    updated_entries: list[dict] = []
    for entry in entries:
        ftype = str(entry.get("failure_type") or "")
        updated = dict(entry)
        if ftype in focused_failures:
            promoted += 1
            updated["priority"] = int(updated.get("priority", 0) or 0) + boost
            existing_actions = [str(x) for x in (updated.get("actions") or []) if isinstance(x, str)]
            injected = [str(x) for x in (template_actions.get(ftype) or []) if isinstance(x, str)]
            if injected:
                template_action_injections += 1
            updated["actions"] = _merge_actions(existing_actions, FOCUS_ACTIONS.get(ftype, []))
            updated["actions"] = _merge_actions(updated["actions"], injected)
            updated["focus_tag"] = "top_failure_focus"
        updated_entries.append(updated)

    payload = {
        "schema_version": "agent_modelica_repair_playbook_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "focused_failure_count": len(focused_failures),
        "promoted_entries": promoted,
        "queue_kind": queue_kind,
        "template_action_injections": template_action_injections,
        "playbook": updated_entries,
        "sources": {
            "playbook": args.playbook,
            "queue": args.queue,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "promoted_entries": payload.get("promoted_entries")}))


if __name__ == "__main__":
    main()
