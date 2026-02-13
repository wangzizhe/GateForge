from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .change_plan import validate_change_plan
from .change_apply import validate_change_set


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _infer_intent(goal: str, prefer_backend: str) -> str:
    text = goal.lower()
    if "medium" in text or "oscillator" in text:
        return "medium_openmodelica_pass"
    if "high risk" in text or "critical" in text:
        return "runtime_regress_high_risk"
    if "runtime" in text and "regress" in text:
        return "runtime_regress_low_risk"
    if "openmodelica" in text or "docker" in text:
        return "demo_openmodelica_pass"

    if prefer_backend == "openmodelica_docker":
        return "demo_openmodelica_pass"
    return "demo_mock_pass"


def _infer_overrides(goal: str) -> dict:
    text = goal.lower()
    overrides = {"change_summary": goal}
    if "high risk" in text:
        overrides["risk_level"] = "high"
    elif "medium risk" in text:
        overrides["risk_level"] = "medium"
    elif "low risk" in text:
        overrides["risk_level"] = "low"
    return overrides


def _merge_context_overrides(overrides: dict, context: dict) -> dict:
    merged = dict(overrides)
    if isinstance(context.get("risk_level"), str):
        merged["risk_level"] = context["risk_level"]
    if isinstance(context.get("change_summary"), str) and context["change_summary"].strip():
        merged["change_summary"] = context["change_summary"]
    if isinstance(context.get("checkers"), list):
        merged["checkers"] = context["checkers"]
    if isinstance(context.get("checker_config"), dict):
        merged["checker_config"] = context["checker_config"]
    return merged


def _read_goal(goal: str | None, goal_file: str | None) -> str:
    if bool(goal) == bool(goal_file):
        raise ValueError("Exactly one of --goal or --goal-file must be provided")
    if goal is not None:
        return goal
    text = Path(goal_file).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("goal file must contain non-empty text")
    return text


def _load_context(context_json: str | None) -> dict:
    if not context_json:
        return {}
    payload = json.loads(Path(context_json).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("context-json must be a JSON object")
    return payload


def _plan_with_rule_backend(
    *,
    goal_text: str,
    context: dict,
    prefer_backend: str,
    proposal_id: str | None,
    context_json_path: str | None,
    emit_change_set_draft: bool,
) -> dict:
    context_prefer_backend = context.get("prefer_backend")
    if context_prefer_backend in {"auto", "mock", "openmodelica_docker"}:
        effective_prefer_backend = context_prefer_backend
    else:
        effective_prefer_backend = prefer_backend

    intent = _infer_intent(goal=goal_text, prefer_backend=effective_prefer_backend)
    overrides = _merge_context_overrides(_infer_overrides(goal_text), context)

    payload = {
        "intent": intent,
        "proposal_id": proposal_id,
        "overrides": overrides,
        "planner": "rule_v0",
        "planner_inputs": {
            "goal": goal_text,
            "prefer_backend": effective_prefer_backend,
            "context_path": context_json_path,
            "planner_backend": "rule",
            "emit_change_set_draft": emit_change_set_draft,
        },
        "context": context,
    }
    if emit_change_set_draft:
        payload["change_plan"] = {
            "schema_version": "0.1.0",
            "operations": [
                {
                    "kind": "replace_text",
                    "file": "examples/openmodelica/MinimalProbe.mo",
                    "old": "der(x) = -x;",
                    "new": "der(x) = -2*x;",
                    "reason": "Increase decay rate for deterministic stability demo",
                    "confidence": 0.9,
                    "risk_tag": "low",
                }
            ],
        }
        payload["change_set_draft"] = {
            "schema_version": "0.1.0",
            "changes": [
                {
                    "op": "replace_text",
                    "file": "examples/openmodelica/MinimalProbe.mo",
                    "old": "der(x) = -x;",
                    "new": "der(x) = -2*x;",
                }
            ],
        }
    return payload


def _plan_with_openai_backend_placeholder(
    *,
    goal_text: str,
    context: dict,
    prefer_backend: str,
    proposal_id: str | None,
    context_json_path: str | None,
    emit_change_set_draft: bool,
) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("planner-backend=openai requires OPENAI_API_KEY to be set")
    raise ValueError(
        "planner-backend=openai is not implemented yet; keep using --planner-backend rule for now"
    )


def _extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise ValueError("gemini planner response does not contain a JSON object")
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("gemini planner response JSON must be an object")
    return payload


def _plan_with_gemini_backend(
    *,
    goal_text: str,
    context: dict,
    prefer_backend: str,
    proposal_id: str | None,
    context_json_path: str | None,
    emit_change_set_draft: bool,
) -> dict:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("planner-backend=gemini requires GOOGLE_API_KEY to be set")

    model = os.getenv("GATEFORGE_GEMINI_MODEL", "gemini-2.5-flash-lite")
    prompt = (
        "You are a planning backend for GateForge.\n"
        "Return ONLY JSON object with keys: intent, proposal_id, overrides.\n"
        "Allowed intent values: demo_mock_pass, demo_openmodelica_pass, medium_openmodelica_pass, "
        "runtime_regress_low_risk, runtime_regress_high_risk.\n"
        "proposal_id should be null if unknown.\n"
        "overrides must be an object and may include risk_level, change_summary, checkers, checker_config.\n"
        "You may include optional change_plan with schema_version='0.1.0' and operations list.\n"
        "Each change_plan operation must include: kind,file,old,new,reason,confidence (0..1).\n"
        "If emit_change_set_draft is true, optionally add key change_set_draft with valid GateForge change_set JSON.\n"
        f"goal: {goal_text}\n"
        f"prefer_backend: {prefer_backend}\n"
        f"context_json: {json.dumps(context)}\n"
        f"user_proposal_id: {proposal_id}\n"
        f"emit_change_set_draft: {emit_change_set_draft}\n"
    )
    req_payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }
    req_data = json.dumps(req_payload).encode("utf-8")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={urllib.parse.quote(api_key)}"
    )
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(f"gemini API error {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"gemini API connection error: {exc.reason}") from exc

    candidates = response_payload.get("candidates", [])
    if not candidates:
        raise ValueError("gemini response has no candidates")
    text = (
        candidates[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    parsed = _extract_json_object(text)
    intent = parsed.get("intent")
    allowed_intents = {
        "demo_mock_pass",
        "demo_openmodelica_pass",
        "medium_openmodelica_pass",
        "runtime_regress_low_risk",
        "runtime_regress_high_risk",
    }
    if intent not in allowed_intents:
        raise ValueError(f"gemini planner returned unsupported intent: {intent}")
    overrides = parsed.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("gemini planner overrides must be an object")
    if "change_summary" not in overrides:
        overrides["change_summary"] = goal_text
    resolved_proposal_id = proposal_id if proposal_id is not None else parsed.get("proposal_id")
    payload = {
        "intent": intent,
        "proposal_id": resolved_proposal_id,
        "overrides": overrides,
        "planner": "gemini_v0",
        "planner_inputs": {
            "goal": goal_text,
            "prefer_backend": prefer_backend,
            "context_path": context_json_path,
            "planner_backend": "gemini",
            "model": model,
            "emit_change_set_draft": emit_change_set_draft,
        },
        "context": context,
        "raw_response": {
            "modelVersion": response_payload.get("modelVersion"),
            "responseId": response_payload.get("responseId"),
            "usageMetadata": response_payload.get("usageMetadata", {}),
        },
    }
    draft = parsed.get("change_set_draft")
    if draft is not None:
        validate_change_set(draft)
        payload["change_set_draft"] = draft
    change_plan = parsed.get("change_plan")
    if change_plan is not None:
        validate_change_plan(change_plan)
        payload["change_plan"] = change_plan
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Rule-based planner that emits GateForge intent-file JSON")
    parser.add_argument("--goal", default=None, help="Natural-language planner goal")
    parser.add_argument("--goal-file", default=None, help="Path to file containing goal text")
    parser.add_argument(
        "--planner-backend",
        default="rule",
        choices=["rule", "openai", "gemini"],
        help="Planner backend: rule (implemented), openai (placeholder), gemini (implemented)",
    )
    parser.add_argument(
        "--prefer-backend",
        default="auto",
        choices=["auto", "mock", "openmodelica_docker"],
        help="Optional backend preference for intent selection",
    )
    parser.add_argument(
        "--context-json",
        default=None,
        help="Optional context JSON path (can provide prefer_backend/risk_level/change_summary)",
    )
    parser.add_argument(
        "--emit-change-set-draft",
        action="store_true",
        help="Ask planner to include a change_set_draft in output",
    )
    parser.add_argument("--proposal-id", default=None, help="Optional explicit proposal_id")
    parser.add_argument(
        "--out",
        default="artifacts/agent/intent_request.json",
        help="Where to write intent-file JSON",
    )
    args = parser.parse_args()

    try:
        goal_text = _read_goal(goal=args.goal, goal_file=args.goal_file)
        context = _load_context(args.context_json)
        if args.planner_backend == "rule":
            payload = _plan_with_rule_backend(
                goal_text=goal_text,
                context=context,
                prefer_backend=args.prefer_backend,
                proposal_id=args.proposal_id,
                context_json_path=args.context_json,
                emit_change_set_draft=args.emit_change_set_draft,
            )
        elif args.planner_backend == "gemini":
            payload = _plan_with_gemini_backend(
                goal_text=goal_text,
                context=context,
                prefer_backend=args.prefer_backend,
                proposal_id=args.proposal_id,
                context_json_path=args.context_json,
                emit_change_set_draft=args.emit_change_set_draft,
            )
        else:
            payload = _plan_with_openai_backend_placeholder(
                goal_text=goal_text,
                context=context,
                prefer_backend=args.prefer_backend,
                proposal_id=args.proposal_id,
                context_json_path=args.context_json,
                emit_change_set_draft=args.emit_change_set_draft,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    _write_json(args.out, payload)
    print(json.dumps({"intent": payload["intent"], "out": args.out, "planner_backend": args.planner_backend}))


if __name__ == "__main__":
    main()
