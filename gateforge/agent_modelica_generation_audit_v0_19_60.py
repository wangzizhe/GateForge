from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

from .agent_modelica_generation_taxonomy_v0_19_59 import (
    DEFAULT_MAPPING_PATH,
    DEFAULT_NL_TASK_POOL_DIR,
    DEFAULT_OUT_PATH as DEFAULT_V059_SUMMARY_PATH,
    load_json,
    load_nl_tasks,
)
from .agent_modelica_l2_plan_replan_engine_v1 import send_with_budget
from .experiment_runner_shared import run_check_and_simulate_omc
from .llm_provider_adapter import resolve_provider_adapter
from .llm_response import extract_json_object


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "generation_audit_v0_19_60"

MODEL_BLOCK_RE = re.compile(
    r"(?P<body>\bmodel\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b.*?\bend\s+(?P=name)\s*;)",
    re.DOTALL,
)
MODEL_NAME_RE = re.compile(r"\bmodel\s+([A-Za-z_][A-Za-z0-9_]*)\b")
CODE_FENCE_RE = re.compile(r"```(?:modelica|mo|Modelica)?\s*(.*?)```", re.DOTALL)


def build_generation_prompt(task: dict[str, Any]) -> str:
    return (
        "You are generating a standalone Modelica model from a natural-language task.\n"
        "Return ONLY one JSON object with keys: model_text, rationale.\n"
        "Constraints:\n"
        "- The model must be standalone and include all declarations and equations needed to run.\n"
        "- Include an annotation(experiment(...)) when appropriate.\n"
        "- Do not include repair hints, taxonomy labels, or markdown.\n"
        "- Do not reference private GateForge benchmark internals.\n"
        f"- task_id: {str(task.get('task_id') or '').strip()}\n"
        f"- difficulty: {str(task.get('difficulty') or '').strip()}\n"
        f"- domain: {str(task.get('domain') or '').strip()}\n"
        f"- acceptance: {json.dumps(task.get('acceptance') or [], ensure_ascii=True)}\n"
        "Natural-language task:\n"
        f"{str(task.get('prompt') or '').strip()}\n"
    )


def extract_modelica_model_text(response_text: str) -> str:
    text = str(response_text or "").strip()
    if not text:
        return ""
    payload = extract_json_object(text, strict=False)
    for key in ("model_text", "modelica_model_text", "code", "patched_model_text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            break
    fence_match = CODE_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()
    model_match = MODEL_BLOCK_RE.search(text)
    if model_match:
        return model_match.group("body").strip()
    return text if MODEL_NAME_RE.search(text) else ""


def extract_model_name(model_text: str) -> str:
    match = MODEL_NAME_RE.search(str(model_text or ""))
    return "" if not match else match.group(1)


def classify_generation_failure(
    *,
    llm_error: str = "",
    model_text: str = "",
    model_name: str = "",
    check_pass: bool = False,
    simulate_pass: bool = False,
    omc_output: str = "",
) -> dict[str, Any]:
    if check_pass and simulate_pass:
        return {
            "bucket_id": "PASS",
            "classification_source": "omc_check_and_simulate",
            "evidence_excerpt": "checkModel and simulate passed",
            "confidence": 1.0,
        }
    if str(llm_error or "").strip():
        return {
            "bucket_id": "ET01",
            "classification_source": "llm_request_error",
            "evidence_excerpt": str(llm_error)[:500],
            "confidence": 0.65,
        }
    if not str(model_text or "").strip():
        return {
            "bucket_id": "ET01",
            "classification_source": "model_text_extraction",
            "evidence_excerpt": "No standalone Modelica model text could be extracted from the LLM response.",
            "confidence": 0.7,
        }
    if not str(model_name or "").strip():
        return {
            "bucket_id": "ET01",
            "classification_source": "model_name_extraction",
            "evidence_excerpt": "Modelica model name could not be extracted.",
            "confidence": 0.7,
        }

    text = str(omc_output or "").lower()
    eq_var_match = re.search(r"has\s+(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)", text)
    if eq_var_match:
        equations = int(eq_var_match.group(1))
        variables = int(eq_var_match.group(2))
        if equations > variables:
            return {
                "bucket_id": "ET07",
                "classification_source": "omc_equation_variable_count",
                "evidence_excerpt": _first_matching_excerpt(omc_output, ("equation(s)",)),
                "confidence": 0.85,
            }
        if variables > equations:
            return {
                "bucket_id": "ET06",
                "classification_source": "omc_equation_variable_count",
                "evidence_excerpt": _first_matching_excerpt(omc_output, ("equation(s)",)),
                "confidence": 0.85,
            }
    rules: list[tuple[str, tuple[str, ...], float]] = [
        ("ET01", ("syntax error", "parser error", "parse error", "expected", "missing token"), 0.85),
        ("ET03", ("variable not found", "undeclared", "not declared", "unknown variable"), 0.8),
        ("ET02", ("class ", "not found in scope", "class not found", "component not found"), 0.8),
        ("ET04", ("invalid modifier", "modifier", "binding", "redeclare", "final parameter"), 0.75),
        ("ET05", ("no remaining equation", "does not have any remaining equation", "unmatched variable"), 0.85),
        ("ET06", ("too few equations", "underdetermined", "singular system", "structurally singular"), 0.8),
        ("ET07", ("too many equations", "overdetermined", "redundant equation"), 0.8),
        ("ET08", ("connect(", "connection", "short circuit", "connect equation"), 0.75),
        ("ET09", ("connector", "causality", "flow/non-flow", "input/output"), 0.75),
        ("ET10", ("array", "dimension", "subscript", "index out of bounds"), 0.75),
        ("ET11", ("type mismatch", "unit", "dimension mismatch"), 0.75),
        ("ET12", ("initialization", "initial equation", "start value", "fixed=false"), 0.75),
        ("ET13", ("when ", "discrete", "pre(", "sample(", "event"), 0.75),
        ("ET14", ("operator", "function", "der(", "homotopy", "noevent"), 0.7),
        ("ET16", ("simulation failed", "simulate", "division by zero", "nonlinear solver", "runtime"), 0.7),
    ]
    if re.search(r"error:\s*variable\s+.+?\s+not found in scope", text):
        return {
            "bucket_id": "ET03",
            "classification_source": "omc_output",
            "evidence_excerpt": _first_matching_excerpt(omc_output, ("not found in scope",)),
            "confidence": 0.85,
        }
    for bucket_id, needles, confidence in rules:
        if any(needle in text for needle in needles):
            return {
                "bucket_id": bucket_id,
                "classification_source": "omc_output",
                "evidence_excerpt": _first_matching_excerpt(omc_output, needles),
                "confidence": confidence,
            }
    return {
        "bucket_id": "UNCLASSIFIED",
        "classification_source": "omc_output",
        "evidence_excerpt": str(omc_output or "")[:500],
        "confidence": 0.2,
    }


def _first_matching_excerpt(text: str, needles: Iterable[str]) -> str:
    raw = str(text or "")
    lower = raw.lower()
    for needle in needles:
        idx = lower.find(str(needle).lower())
        if idx >= 0:
            start = max(0, idx - 160)
            end = min(len(raw), idx + 340)
            return raw[start:end]
    return raw[:500]


def request_generation_from_llm(
    *,
    task: dict[str, Any],
    planner_backend: str,
    temperature: float = 0.2,
) -> tuple[str, str, str]:
    adapter, config = resolve_provider_adapter(planner_backend)
    if config.provider_name == "rule":
        return "", "rule_backend_selected", "rule"
    config.temperature = float(temperature)
    prompt = build_generation_prompt(task)
    text, err = send_with_budget(adapter, prompt, config)
    return text, err, config.provider_name


def fixture_generation_response(task: dict[str, Any]) -> tuple[str, str, str]:
    task_id = str(task.get("task_id") or "")
    model_name = re.sub(r"[^A-Za-z0-9_]", "_", task_id)
    if task_id.endswith("thermal_lumped_wall"):
        return (
            json.dumps(
                {
                    "model_text": (
                        f"model {model_name}\n"
                        "  parameter Real C = 1000;\n"
                        "  parameter Real G = 10;\n"
                        "  parameter Real Tamb = 293.15;\n"
                        "  Real T(start = 300);\n"
                        "equation\n"
                        "  C * der(T) = G * (Tamb - T);\n"
                        "  annotation(experiment(StartTime=0, StopTime=1));\n"
                        f"end {model_name};"
                    ),
                    "rationale": "fixture pass model",
                }
            ),
            "",
            "fixture",
        )
    return (
        json.dumps(
            {
                "model_text": (
                    f"model {model_name}\n"
                    "  Real x;\n"
                    "equation\n"
                    "  der(x) = missingSymbol;\n"
                    "  annotation(experiment(StartTime=0, StopTime=1));\n"
                    f"end {model_name};"
                ),
                "rationale": "fixture failure model",
            }
        ),
        "",
        "fixture",
    )


def fixture_evaluate_model(model_text: str, model_name: str) -> tuple[bool, bool, str]:
    if "missingSymbol" in str(model_text or ""):
        return False, False, "Error: Variable missingSymbol not found in scope"
    return True, True, "Simulation succeeded"


def evaluate_model_with_omc(model_text: str, model_name: str) -> tuple[bool, bool, str]:
    return run_check_and_simulate_omc(model_text, model_name, workspace_prefix="gf_gen_audit_")


def run_generation_task(
    task: dict[str, Any],
    *,
    planner_backend: str,
    generation_fn: Callable[[dict[str, Any]], tuple[str, str, str]] | None = None,
    evaluator_fn: Callable[[str, str], tuple[bool, bool, str]] | None = None,
) -> dict[str, Any]:
    generation_fn = generation_fn or (
        lambda item: request_generation_from_llm(task=item, planner_backend=planner_backend)
    )
    evaluator_fn = evaluator_fn or evaluate_model_with_omc

    response_text, llm_error, provider = generation_fn(task)
    model_text = extract_modelica_model_text(response_text)
    model_name = extract_model_name(model_text)
    check_pass = False
    simulate_pass = False
    omc_output = ""
    if model_text and model_name and not llm_error:
        try:
            check_pass, simulate_pass, omc_output = evaluator_fn(model_text, model_name)
        except Exception as exc:  # pragma: no cover - defensive for live OMC failures
            omc_output = f"omc_evaluator_exception:{type(exc).__name__}:{exc}"
    classification = classify_generation_failure(
        llm_error=llm_error,
        model_text=model_text,
        model_name=model_name,
        check_pass=check_pass,
        simulate_pass=simulate_pass,
        omc_output=omc_output,
    )
    return {
        "task_id": str(task.get("task_id") or ""),
        "difficulty": str(task.get("difficulty") or ""),
        "domain": str(task.get("domain") or ""),
        "provider": provider,
        "llm_error": llm_error,
        "model_name": model_name,
        "model_text": model_text,
        "check_pass": bool(check_pass),
        "simulate_pass": bool(simulate_pass),
        "final_status": "pass" if classification["bucket_id"] == "PASS" else "fail",
        "classification": classification,
        "omc_output_excerpt": str(omc_output or "")[:2000],
    }


def distribution_from_buckets(bucket_ids: Iterable[str], *, exclude_pass: bool = True) -> dict[str, float]:
    counts = Counter(str(bucket_id) for bucket_id in bucket_ids if str(bucket_id))
    if exclude_pass:
        counts.pop("PASS", None)
    total = sum(counts.values())
    if total <= 0:
        return {}
    return {key: value / total for key, value in sorted(counts.items())}


def total_variation_distance(p_dist: dict[str, float], q_dist: dict[str, float]) -> float:
    keys = set(p_dist) | set(q_dist)
    return 0.5 * sum(abs(float(p_dist.get(key, 0.0)) - float(q_dist.get(key, 0.0))) for key in keys)


def load_mutation_distribution(summary_path: Path = DEFAULT_V059_SUMMARY_PATH) -> dict[str, float]:
    payload = load_json(summary_path)
    counts = payload.get("bucket_counts") or {}
    total = sum(int(v or 0) for v in counts.values())
    if total <= 0:
        return {}
    return {str(k): int(v or 0) / total for k, v in sorted(counts.items())}


def parse_mapping_statuses(path: Path = DEFAULT_MAPPING_PATH) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("| ET"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 3:
            match = re.match(r"(ET\d{2})\b", cells[0])
            if match:
                statuses[match.group(1)] = cells[2]
    return statuses


def build_gap_list(
    *,
    p_dist: dict[str, float],
    q_dist: dict[str, float],
    mapping_statuses: dict[str, str],
    high_delta_threshold: float = 0.15,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for bucket_id, p_value in sorted(p_dist.items()):
        q_value = float(q_dist.get(bucket_id, 0.0))
        mapping_status = str(mapping_statuses.get(bucket_id) or "")
        if p_value > 0 and q_value == 0:
            gaps.append(
                {
                    "bucket_id": bucket_id,
                    "gap_type": "generated_failure_not_in_mutation_distribution",
                    "p": round(p_value, 6),
                    "q": 0.0,
                }
            )
        if p_value > 0 and mapping_status == "gap":
            gaps.append(
                {
                    "bucket_id": bucket_id,
                    "gap_type": "taxonomy_mapping_gap",
                    "p": round(p_value, 6),
                    "q": round(q_value, 6),
                }
            )
        if p_value - q_value >= high_delta_threshold:
            gaps.append(
                {
                    "bucket_id": bucket_id,
                    "gap_type": "high_generation_low_mutation_mass",
                    "p": round(p_value, 6),
                    "q": round(q_value, 6),
                    "delta": round(p_value - q_value, 6),
                }
            )
    return gaps


def build_generation_audit_summary(
    *,
    task_results: list[dict[str, Any]],
    mutation_distribution: dict[str, float],
    mapping_statuses: dict[str, str],
    dry_run_fixture: bool,
    planner_backend: str,
) -> dict[str, Any]:
    bucket_ids = [str((result.get("classification") or {}).get("bucket_id") or "") for result in task_results]
    generation_distribution = distribution_from_buckets(bucket_ids)
    distance = total_variation_distance(generation_distribution, mutation_distribution)
    pass_count = sum(1 for result in task_results if result.get("final_status") == "pass")
    fail_count = len(task_results) - pass_count
    gaps = build_gap_list(
        p_dist=generation_distribution,
        q_dist=mutation_distribution,
        mapping_statuses=mapping_statuses,
    )
    return {
        "version": "v0.19.60",
        "status": "DRY_RUN" if dry_run_fixture else "PASS",
        "planner_backend": planner_backend,
        "dry_run_fixture": bool(dry_run_fixture),
        "task_count": len(task_results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "pass_rate": pass_count / len(task_results) if task_results else 0.0,
        "generation_failure_distribution_p": generation_distribution,
        "mutation_distribution_q": mutation_distribution,
        "d_pq_metric": "total_variation_distance",
        "d_pq_total_variation": round(distance, 6),
        "bucket_counts": dict(sorted(Counter(bucket_ids).items())),
        "mutation_coverage_gaps": gaps,
        "mutation_coverage_gap_count": len(gaps),
        "task_results": [
            {
                "task_id": result.get("task_id"),
                "final_status": result.get("final_status"),
                "bucket_id": (result.get("classification") or {}).get("bucket_id"),
                "domain": result.get("domain"),
                "difficulty": result.get("difficulty"),
                "provider": result.get("provider"),
            }
            for result in task_results
        ],
        "conclusion": (
            "dry_run_fixture_only_no_generation_claim"
            if dry_run_fixture
            else "generation_distribution_audit_complete"
        ),
    }


def write_generation_audit_outputs(
    *,
    out_dir: Path,
    task_results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir = out_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for result in task_results:
        task_id = str(result.get("task_id") or "unknown")
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id)
        (tasks_dir / f"{safe_id}.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        model_text = str(result.get("model_text") or "").strip()
        if model_text:
            (tasks_dir / f"{safe_id}.mo").write_text(model_text + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "REPORT.md").write_text(render_generation_audit_report(summary), encoding="utf-8")


def render_generation_audit_report(summary: dict[str, Any]) -> str:
    lines = [
        "# v0.19.60 Generation Audit",
        "",
        f"- status: `{summary.get('status')}`",
        f"- dry_run_fixture: `{summary.get('dry_run_fixture')}`",
        f"- task_count: `{summary.get('task_count')}`",
        f"- pass_count: `{summary.get('pass_count')}`",
        f"- fail_count: `{summary.get('fail_count')}`",
        f"- d_pq_total_variation: `{summary.get('d_pq_total_variation')}`",
        f"- mutation_coverage_gap_count: `{summary.get('mutation_coverage_gap_count')}`",
        "",
        "## Generation Failure Distribution P",
    ]
    for bucket_id, value in (summary.get("generation_failure_distribution_p") or {}).items():
        lines.append(f"- `{bucket_id}`: `{value:.6f}`")
    lines.extend(["", "## Mutation Distribution Q"])
    for bucket_id, value in (summary.get("mutation_distribution_q") or {}).items():
        lines.append(f"- `{bucket_id}`: `{value:.6f}`")
    lines.extend(["", "## Gaps"])
    gaps = summary.get("mutation_coverage_gaps") or []
    if not gaps:
        lines.append("- none")
    for gap in gaps:
        lines.append(
            f"- `{gap.get('bucket_id')}` `{gap.get('gap_type')}` "
            f"P=`{gap.get('p')}` Q=`{gap.get('q')}`"
        )
    return "\n".join(lines) + "\n"


def select_tasks(
    *,
    pool_dir: Path = DEFAULT_NL_TASK_POOL_DIR,
    task_id: str = "",
    max_tasks: int = 0,
) -> list[dict[str, Any]]:
    tasks = load_nl_tasks(pool_dir)
    if task_id:
        tasks = [task for task in tasks if str(task.get("task_id") or "") == task_id]
    if max_tasks and max_tasks > 0:
        tasks = tasks[: int(max_tasks)]
    return tasks


def run_generation_audit(
    *,
    planner_backend: str,
    out_dir: Path = DEFAULT_OUT_DIR,
    pool_dir: Path = DEFAULT_NL_TASK_POOL_DIR,
    task_id: str = "",
    max_tasks: int = 0,
    dry_run_fixture: bool = False,
    generation_fn: Callable[[dict[str, Any]], tuple[str, str, str]] | None = None,
    evaluator_fn: Callable[[str, str], tuple[bool, bool, str]] | None = None,
) -> dict[str, Any]:
    tasks = select_tasks(pool_dir=pool_dir, task_id=task_id, max_tasks=max_tasks)
    if dry_run_fixture:
        generation_fn = fixture_generation_response
        if evaluator_fn is None:
            evaluator_fn = fixture_evaluate_model
    task_results = [
        run_generation_task(
            task,
            planner_backend=planner_backend,
            generation_fn=generation_fn,
            evaluator_fn=evaluator_fn,
        )
        for task in tasks
    ]
    summary = build_generation_audit_summary(
        task_results=task_results,
        mutation_distribution=load_mutation_distribution(),
        mapping_statuses=parse_mapping_statuses(),
        dry_run_fixture=dry_run_fixture,
        planner_backend=planner_backend,
    )
    write_generation_audit_outputs(out_dir=out_dir, task_results=task_results, summary=summary)
    return summary
