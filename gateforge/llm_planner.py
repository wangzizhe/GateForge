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

from .change_plan import DEFAULT_ALLOWED_ROOTS, DEFAULT_ALLOWED_SUFFIXES, summarize_change_plan, validate_change_plan
from .change_apply import validate_change_set

ALLOWED_GEMINI_TOP_LEVEL_KEYS = {
    "intent",
    "proposal_id",
    "overrides",
    "change_plan",
    "change_set_draft",
}
ALLOWED_OVERRIDE_KEYS = {
    "risk_level",
    "change_summary",
    "checkers",
    "checker_config",
}


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_guardrail_report(path: str | None, payload: dict) -> None:
    if not path:
        return
    _write_json(path, payload)


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


def _resolve_plan_confidence(context: dict, default: float = 0.9) -> float:
    value = context.get("change_plan_confidence")
    if isinstance(value, (int, float)):
        v = float(value)
        if 0.0 <= v <= 1.0:
            return v
    return default


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
        plan_confidence = _resolve_plan_confidence(context=context)
        payload["change_plan"] = {
            "schema_version": "0.1.0",
            "operations": [
                {
                    "kind": "replace_text",
                    "file": "examples/openmodelica/MinimalProbe.mo",
                    "old": "der(x) = -x;",
                    "new": "der(x) = -2*x;",
                    "reason": "Increase decay rate for deterministic stability demo",
                    "confidence": plan_confidence,
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


def _validate_overrides(overrides: dict) -> None:
    unknown = sorted(k for k in overrides if k not in ALLOWED_OVERRIDE_KEYS)
    if unknown:
        raise ValueError(f"planner overrides contain unsupported keys: {unknown}")


def _validate_change_set_files(
    change_set: dict,
    *,
    allowed_roots: tuple[str, ...],
    allowed_suffixes: tuple[str, ...],
    allowed_files: tuple[str, ...] | None,
) -> None:
    changes = change_set.get("changes", [])
    for idx, change in enumerate(changes):
        file_path = change.get("file")
        if not isinstance(file_path, str) or not file_path:
            continue
        if Path(file_path).is_absolute():
            raise ValueError(f"change_set_draft changes[{idx}].file must be relative")
        if not any(file_path == root or file_path.startswith(root + "/") for root in allowed_roots):
            raise ValueError(f"change_set_draft changes[{idx}].file outside allowed roots: {file_path}")
        if not file_path.endswith(allowed_suffixes):
            raise ValueError(
                f"change_set_draft changes[{idx}].file must end with one of {sorted(allowed_suffixes)}"
            )
        if allowed_files and file_path not in allowed_files:
            raise ValueError(f"change_set_draft changes[{idx}].file is not in allowed_files whitelist: {file_path}")


def _apply_llm_guardrails(
    payload: dict,
    *,
    allowed_roots: tuple[str, ...],
    allowed_suffixes: tuple[str, ...],
    allowed_files: tuple[str, ...] | None,
    confidence_min: float,
    confidence_max: float,
) -> dict:
    overrides = payload.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("planner overrides must be an object")
    _validate_overrides(overrides)

    change_plan = payload.get("change_plan")
    guardrails = {
        "allowed_roots": list(allowed_roots),
        "allowed_suffixes": list(allowed_suffixes),
        "allowed_files_count": 0 if not allowed_files else len(allowed_files),
        "confidence_min": confidence_min,
        "confidence_max": confidence_max,
    }
    if change_plan is not None:
        validate_change_plan(
            change_plan,
            allowed_roots=allowed_roots,
            allowed_suffixes=allowed_suffixes,
            allowed_files=allowed_files,
        )
        stats = summarize_change_plan(change_plan)
        conf_min = stats["plan_confidence_min"]
        conf_max = stats["plan_confidence_max"]
        if conf_min < confidence_min:
            raise ValueError(
                f"change_plan confidence_min={conf_min:.3f} is below guardrail {confidence_min:.3f}"
            )
        if conf_max > confidence_max:
            raise ValueError(
                f"change_plan confidence_max={conf_max:.3f} is above guardrail {confidence_max:.3f}"
            )
        guardrails.update(stats)

    draft = payload.get("change_set_draft")
    if draft is not None:
        validate_change_set(draft)
        _validate_change_set_files(
            draft,
            allowed_roots=allowed_roots,
            allowed_suffixes=allowed_suffixes,
            allowed_files=allowed_files,
        )
    return guardrails


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
    unknown_top_level = sorted(k for k in parsed.keys() if k not in ALLOWED_GEMINI_TOP_LEVEL_KEYS)
    if unknown_top_level:
        raise ValueError(f"gemini planner returned unsupported top-level keys: {unknown_top_level}")
    overrides = parsed.get("overrides", {})
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
        payload["change_set_draft"] = draft
    change_plan = parsed.get("change_plan")
    if change_plan is not None:
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
    parser.add_argument(
        "--change-plan-allowed-root",
        action="append",
        default=None,
        help="Allowed root prefix for planner-produced change_plan/change_set files (repeatable)",
    )
    parser.add_argument(
        "--change-plan-allowed-suffix",
        action="append",
        default=None,
        help="Allowed file suffix for planner-produced change_plan/change_set files (repeatable)",
    )
    parser.add_argument(
        "--change-plan-allowed-file",
        action="append",
        default=None,
        help="Allowed file whitelist for planner-produced change_plan/change_set files (repeatable)",
    )
    parser.add_argument(
        "--change-plan-confidence-min",
        type=float,
        default=0.0,
        help="Reject planner change_plan if min operation confidence is below this value",
    )
    parser.add_argument(
        "--change-plan-confidence-max",
        type=float,
        default=1.0,
        help="Reject planner change_plan if max operation confidence is above this value",
    )
    parser.add_argument(
        "--guardrail-report-out",
        default=None,
        help="Optional path to write planner guardrail report JSON",
    )
    parser.add_argument("--proposal-id", default=None, help="Optional explicit proposal_id")
    parser.add_argument(
        "--out",
        default="artifacts/agent/intent_request.json",
        help="Where to write intent-file JSON",
    )
    args = parser.parse_args()

    try:
        if not (0.0 <= args.change_plan_confidence_min <= 1.0):
            raise ValueError("--change-plan-confidence-min must be in [0.0, 1.0]")
        if not (0.0 <= args.change_plan_confidence_max <= 1.0):
            raise ValueError("--change-plan-confidence-max must be in [0.0, 1.0]")
        if args.change_plan_confidence_min > args.change_plan_confidence_max:
            raise ValueError("--change-plan-confidence-min must be <= --change-plan-confidence-max")

        goal_text = _read_goal(goal=args.goal, goal_file=args.goal_file)
        context = _load_context(args.context_json)
        allowed_roots = tuple(args.change_plan_allowed_root or DEFAULT_ALLOWED_ROOTS)
        allowed_suffixes = tuple(args.change_plan_allowed_suffix or DEFAULT_ALLOWED_SUFFIXES)
        allowed_files = tuple(args.change_plan_allowed_file) if args.change_plan_allowed_file else None
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
        guardrails = _apply_llm_guardrails(
            payload,
            allowed_roots=allowed_roots,
            allowed_suffixes=allowed_suffixes,
            allowed_files=allowed_files,
            confidence_min=args.change_plan_confidence_min,
            confidence_max=args.change_plan_confidence_max,
        )
        _write_guardrail_report(
            args.guardrail_report_out,
            {
                "decision": "PASS",
                "violations": [],
                "guardrails": guardrails,
                "planner_backend": args.planner_backend,
            },
        )
        planner_inputs = payload.get("planner_inputs", {})
        if isinstance(planner_inputs, dict):
            planner_inputs["change_plan_guardrails"] = guardrails
        else:
            payload["planner_inputs"] = {"change_plan_guardrails": guardrails}
    except ValueError as exc:
        _write_guardrail_report(
            args.guardrail_report_out,
            {
                "decision": "FAIL",
                "violations": [str(exc)],
                "planner_backend": args.planner_backend,
            },
        )
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    _write_json(args.out, payload)
    print(json.dumps({"intent": payload["intent"], "out": args.out, "planner_backend": args.planner_backend}))


if __name__ == "__main__":
    main()
