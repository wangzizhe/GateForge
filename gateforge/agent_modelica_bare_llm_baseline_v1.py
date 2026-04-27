"""Bare-LLM single-shot repair baseline for the GateForge Modelica benchmark.

Implements the *bare LLM* side of the Generalization-First Benchmark:

- One LLM call with the broken model text and raw OMC error.
- No guided search (L4), no stage-branch control (L3), no BC evaluation.
- Repair validated by OMC check + simulate — identical ground-truth oracle
  used by the GateForge agent.

Comparing GateForge (full agent) vs this baseline isolates the value added
by the agent framework above a plain "ask the LLM to fix it" approach.

Skill: Trajectory-Grounded Benchmark Pattern
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_l2_plan_replan_engine_v1 import send_with_budget
from .agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from .llm_provider_adapter import resolve_provider_adapter


# ---------------------------------------------------------------------------
# Pure helpers (testable without I/O)
# ---------------------------------------------------------------------------

_MODEL_KEYWORD_PATTERN = re.compile(
    r"^\s*(?:block|class|connector|function|model|package|record|type)\s+(\w+)",
    re.MULTILINE,
)


def extract_model_name(model_text: str) -> str:
    """Return the first model/block/class identifier found in *model_text*.

    Falls back to ``"UnknownModel"`` when no Modelica keyword is found.
    """
    m = _MODEL_KEYWORD_PATTERN.search(str(model_text or ""))
    return m.group(1) if m else "UnknownModel"


def build_bare_prompt(model_text: str, model_name: str, omc_error: str) -> str:
    """Build the single-shot repair prompt sent to the bare LLM.

    Intentionally minimal — no repair_actions, no stage hints, no guided
    search context.  The LLM only receives the broken model text and the raw
    OMC error output.
    """
    return (
        "You are a Modelica expert. Fix the broken Modelica model below.\n"
        "The model fails OMC compilation or simulation.\n"
        "Return ONLY a JSON object: {\"repaired_model_text\": \"<fixed code>\"}\n"
        "Rules: keep the model name unchanged; keep changes minimal.\n"
        f"Model name: {model_name}\n"
        "OMC error output:\n"
        f"{str(omc_error or '')[:2000]}\n"
        "Broken model:\n"
        "-----BEGIN_MODEL-----\n"
        f"{model_text}\n"
        "-----END_MODEL-----\n"
    )


def parse_bare_response(raw: str) -> str | None:
    """Extract ``repaired_model_text`` from a bare LLM JSON response.

    Tries strict JSON first; falls back to finding the first ``{...}`` block
    in the output.  Returns ``None`` if no valid payload is found.
    """
    text = str(raw or "").strip()
    # Strict JSON
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and isinstance(obj.get("repaired_model_text"), str):
            val = obj["repaired_model_text"].strip()
            return val or None
    except Exception:
        pass
    # Lenient: find first balanced {...} block
    brace = text.find("{")
    if brace >= 0:
        chunk = text[brace:]
        depth = 0
        for i, ch in enumerate(chunk):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(chunk[: i + 1])
                        if isinstance(obj, dict) and isinstance(
                            obj.get("repaired_model_text"), str
                        ):
                            val = obj["repaired_model_text"].strip()
                            return val or None
                    except Exception:
                        pass
                    break
    return None


def _make_result(
    *,
    success: bool,
    repaired_text: str,
    omc_error: str,
    error: str,
    provider: str,
    model_name: str,
    elapsed_sec: float,
) -> dict:
    return {
        "success": success,
        "repaired_text": repaired_text,
        "omc_error": omc_error[:4000] if omc_error else "",
        "error": error,
        "provider": provider,
        "model_name": model_name,
        "elapsed_sec": round(elapsed_sec, 2),
    }


# ---------------------------------------------------------------------------
# I/O: single-task bare repair
# ---------------------------------------------------------------------------

_DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"


def run_bare_repair(
    *,
    model_text: str,
    model_name: str = "",
    backend: str = "auto",
    docker_image: str = "",
    timeout_sec: int = 120,
    extra_model_loads: list[str] | None = None,
    source_library_path: str = "",
    source_package_name: str = "",
    source_library_model_path: str = "",
    source_qualified_model_name: str = "",
) -> dict:
    """Run one bare-LLM repair attempt and return a result dict.

    Steps:
    1. Write the broken model to an isolated temp workspace.
    2. Run OMC check+simulate to capture the error string.
    3. Call the LLM exactly once with the broken model + OMC error.
    4. Validate the LLM output with OMC check+simulate.
    5. Return ``{success, repaired_text, omc_error, error, provider,
       model_name, elapsed_sec}``.
    """
    import time

    t0 = time.monotonic()

    resolved_image = docker_image or os.getenv(
        "GATEFORGE_DOCKER_IMAGE", _DEFAULT_DOCKER_IMAGE
    )
    omc_backend = "omc" if not resolved_image else "docker"

    adapter, config = resolve_provider_adapter(backend)
    if config.provider_name == "rule" or not config.api_key:
        return _make_result(
            success=False,
            repaired_text="",
            omc_error="",
            error=f"no_llm_provider:{config.provider_name}",
            provider=config.provider_name,
            model_name=str(model_name or ""),
            elapsed_sec=time.monotonic() - t0,
        )

    model_text_str = str(model_text or "")
    model_name_str = str(model_name or "").strip() or extract_model_name(model_text_str)

    half = max(10, timeout_sec // 2)

    with temporary_workspace("gf_bare_repair_") as ws:
        ws_path = Path(ws)

        fallback_model = Path(f"{model_name_str}.mo")
        layout = prepare_workspace_model_layout(
            workspace=ws_path,
            fallback_model_path=fallback_model,
            primary_model_name=model_name_str,
            source_library_path=str(source_library_path or ""),
            source_package_name=str(source_package_name or ""),
            source_library_model_path=str(source_library_model_path or ""),
            source_qualified_model_name=str(source_qualified_model_name or ""),
        )
        layout.model_write_path.write_text(model_text_str, encoding="utf-8")

        # Step 1: get OMC error on broken model
        _rc, omc_out, _check_ok, _sim_ok = run_check_and_simulate(
            workspace=ws_path,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=half,
            backend=omc_backend,
            docker_image=resolved_image,
            stop_time=0.2,
            intervals=20,
            extra_model_loads=list(extra_model_loads or []),
        )

        # Step 2: single LLM call
        prompt = build_bare_prompt(model_text_str, model_name_str, omc_out)
        raw_response, llm_err = send_with_budget(adapter, prompt, config)
        if llm_err:
            return _make_result(
                success=False,
                repaired_text="",
                omc_error=omc_out,
                error=f"llm_error:{llm_err}",
                provider=config.provider_name,
                model_name=model_name_str,
                elapsed_sec=time.monotonic() - t0,
            )

        repaired_text = parse_bare_response(raw_response)
        if not repaired_text:
            return _make_result(
                success=False,
                repaired_text="",
                omc_error=omc_out,
                error="llm_parse_error",
                provider=config.provider_name,
                model_name=model_name_str,
                elapsed_sec=time.monotonic() - t0,
            )

        # Step 3: validate repair
        layout.model_write_path.write_text(repaired_text, encoding="utf-8")

        _rc2, _out2, check_ok, sim_ok = run_check_and_simulate(
            workspace=ws_path,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=half,
            backend=omc_backend,
            docker_image=resolved_image,
            stop_time=0.2,
            intervals=20,
            extra_model_loads=list(extra_model_loads or []),
        )

        success = bool(check_ok and sim_ok)
        return _make_result(
            success=success,
            repaired_text=repaired_text,
            omc_error=omc_out,
            error="" if success else "omc_validation_failed",
            provider=config.provider_name,
            model_name=model_name_str,
            elapsed_sec=time.monotonic() - t0,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bare-LLM single-shot Modelica repair baseline"
    )
    parser.add_argument("--model-text", default="", help="Inline Modelica source text")
    parser.add_argument("--model-file", default="", help="Path to a Modelica source file")
    parser.add_argument(
        "--model-name",
        default="",
        help="Modelica model identifier (auto-detected from text if omitted)",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "rule", "gemini", "openai", "anthropic", "qwen", "deepseek", "minimax", "kimi", "glm"],
        help="LLM backend",
    )
    parser.add_argument("--docker-image", default="")
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--out", default="", help="Write result JSON to this path")
    args = parser.parse_args()

    model_text = args.model_text
    if not model_text and args.model_file:
        model_text = Path(args.model_file).read_text(encoding="utf-8")
    if not model_text:
        parser.error("--model-text or --model-file is required")

    model_name = args.model_name or extract_model_name(model_text)

    result = run_bare_repair(
        model_text=model_text,
        model_name=model_name,
        backend=args.backend,
        docker_image=args.docker_image,
        timeout_sec=args.timeout_sec,
    )
    result["generated_at_utc"] = datetime.now(timezone.utc).isoformat()

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "success": result["success"],
                "provider": result["provider"],
                "elapsed_sec": result["elapsed_sec"],
            }
        )
    )


if __name__ == "__main__":
    main()
