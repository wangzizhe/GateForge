from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0

DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LIVE_LEDGER_SCHEMA_VERSION = "agent_modelica_live_request_ledger_v1"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


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


def _find_primary_model_name(text: str) -> str:
    m = re.search(r"(?im)^\s*(?:partial\s+)?model\s+([A-Za-z_]\w*)\b", text or "")
    if not m:
        return ""
    return str(m.group(1))


def _run_cmd(cmd: list[str], timeout_sec: int, cwd: str | None = None) -> tuple[int | None, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_sec)),
            check=False,
            cwd=cwd,
        )
        merged = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return int(proc.returncode), merged
    except subprocess.TimeoutExpired:
        return None, "TimeoutExpired"
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"{type(exc).__name__}:{exc}"


def _run_omc_script_local(script_text: str, timeout_sec: int, cwd: str) -> tuple[int | None, str]:
    script_path = Path(cwd) / "run.mos"
    script_path.write_text(script_text, encoding="utf-8")
    return _run_cmd(["omc", str(script_path.name)], timeout_sec=timeout_sec, cwd=cwd)


def _run_omc_script_docker(script_text: str, timeout_sec: int, cwd: str, image: str) -> tuple[int | None, str]:
    script_path = Path(cwd) / "run.mos"
    script_path.write_text(script_text, encoding="utf-8")
    cache_root_raw = str(os.getenv("GATEFORGE_OM_DOCKER_LIBRARY_CACHE") or "").strip()
    cache_root = Path(cache_root_raw) if cache_root_raw else (Path(cwd) / ".gf_omcache" / "libraries")
    cache_root.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{cwd}:/workspace",
        "-v",
        f"{str(cache_root)}:/root/.openmodelica/libraries",
        "-w",
        "/workspace",
        image,
        "omc",
        "run.mos",
    ]
    return _run_cmd(cmd, timeout_sec=timeout_sec)


def _extract_om_success_flags(output: str) -> tuple[bool, bool]:
    lower = str(output or "").lower()
    structural_mismatch = re.search(r"class\s+[a-z_][a-z0-9_]*\s+has\s+([0-9]+)\s+equation\(s\)\s+and\s+([0-9]+)\s+variable\(s\)", lower)
    structural_balance_ok = True
    if structural_mismatch:
        try:
            structural_balance_ok = int(structural_mismatch.group(1)) == int(structural_mismatch.group(2))
        except Exception:
            structural_balance_ok = True
    check_ok = "check of" in lower and "completed successfully" in lower and structural_balance_ok
    has_sim_result = "record simulationresult" in lower
    result_file_empty = 'resultfile = ""' in lower
    sim_error_markers = (
        "simulation execution failed" in lower
        or "error occurred while solving" in lower
        or "division by zero" in lower
        or "assertion" in lower
        or "integrator failed" in lower
    )
    simulate_ok = has_sim_result and not result_file_empty and not sim_error_markers
    return check_ok, simulate_ok


def _to_int_env(name: str, default: int) -> int:
    try:
        return max(0, int(str(os.getenv(name) or "").strip() or default))
    except Exception:
        return max(0, int(default))


def _to_float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(str(os.getenv(name) or "").strip() or default))
    except Exception:
        return max(0.0, float(default))


def _live_budget_config() -> dict:
    ledger_path = str(os.getenv("GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH") or "").strip()
    return {
        "ledger_path": ledger_path,
        "stage": str(os.getenv("GATEFORGE_AGENT_LIVE_REQUEST_STAGE") or "").strip(),
        "max_requests_per_run": _to_int_env("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", 80),
        "max_consecutive_429": max(1, _to_int_env("GATEFORGE_AGENT_LIVE_MAX_CONSECUTIVE_429", 3)),
        "base_backoff_sec": _to_float_env("GATEFORGE_AGENT_LIVE_BACKOFF_BASE_SEC", 5.0),
        "max_backoff_sec": _to_float_env("GATEFORGE_AGENT_LIVE_BACKOFF_MAX_SEC", 60.0),
    }


def _empty_live_ledger(cfg: dict) -> dict:
    return {
        "schema_version": LIVE_LEDGER_SCHEMA_VERSION,
        "live_budget": {
            "max_requests_per_run": int(cfg.get("max_requests_per_run") or 0),
            "max_consecutive_429": int(cfg.get("max_consecutive_429") or 0),
            "base_backoff_sec": float(cfg.get("base_backoff_sec") or 0.0),
            "max_backoff_sec": float(cfg.get("max_backoff_sec") or 0.0),
        },
        "request_count": 0,
        "rate_limit_429_count": 0,
        "consecutive_429_count": 0,
        "backoff_count": 0,
        "last_backoff_sec": 0.0,
        "budget_stop_triggered": False,
        "last_stop_reason": "",
        "last_stage": str(cfg.get("stage") or ""),
    }


def _load_live_ledger(cfg: dict) -> dict:
    ledger_path = str(cfg.get("ledger_path") or "").strip()
    if not ledger_path:
        return _empty_live_ledger(cfg)
    payload = _load_json(Path(ledger_path))
    if not payload:
        return _empty_live_ledger(cfg)
    out = _empty_live_ledger(cfg)
    out.update(payload)
    if cfg.get("stage"):
        out["last_stage"] = str(cfg.get("stage") or "")
    return out


def _write_live_ledger(cfg: dict, payload: dict) -> None:
    ledger_path = str(cfg.get("ledger_path") or "").strip()
    if not ledger_path:
        return
    _write_json(Path(ledger_path), payload)


def _reserve_live_request(cfg: dict) -> tuple[bool, dict]:
    ledger = _load_live_ledger(cfg)
    max_requests = int(cfg.get("max_requests_per_run") or 0)
    if max_requests > 0 and int(ledger.get("request_count") or 0) >= max_requests:
        ledger["budget_stop_triggered"] = True
        ledger["last_stop_reason"] = "live_request_budget_exceeded"
        _write_live_ledger(cfg, ledger)
        return False, ledger
    ledger["request_count"] = int(ledger.get("request_count") or 0) + 1
    ledger["last_stage"] = str(cfg.get("stage") or ledger.get("last_stage") or "")
    _write_live_ledger(cfg, ledger)
    return True, ledger


def _record_live_request_success(cfg: dict) -> dict:
    ledger = _load_live_ledger(cfg)
    ledger["consecutive_429_count"] = 0
    _write_live_ledger(cfg, ledger)
    return ledger


def _record_live_request_429(cfg: dict) -> tuple[str, dict]:
    ledger = _load_live_ledger(cfg)
    ledger["rate_limit_429_count"] = int(ledger.get("rate_limit_429_count") or 0) + 1
    ledger["consecutive_429_count"] = int(ledger.get("consecutive_429_count") or 0) + 1
    threshold = max(1, int(cfg.get("max_consecutive_429") or 1))
    if int(ledger.get("consecutive_429_count") or 0) >= threshold:
        ledger["budget_stop_triggered"] = True
        ledger["last_stop_reason"] = "rate_limited"
        _write_live_ledger(cfg, ledger)
        return "rate_limited", ledger
    backoff = min(
        float(cfg.get("max_backoff_sec") or 0.0),
        float(cfg.get("base_backoff_sec") or 0.0) * (2 ** max(0, int(ledger.get("consecutive_429_count") or 1) - 1)),
    )
    ledger["backoff_count"] = int(ledger.get("backoff_count") or 0) + 1
    ledger["last_backoff_sec"] = float(backoff)
    _write_live_ledger(cfg, ledger)
    if backoff > 0:
        time.sleep(backoff)
    return "", ledger


def _classify_failure(output: str, check_ok: bool, simulate_ok: bool) -> tuple[str, str]:
    diag = build_diagnostic_ir_v0(
        output=output,
        check_model_pass=bool(check_ok),
        simulate_pass=bool(simulate_ok),
        expected_stage="",
        declared_failure_type="",
    )
    return str(diag.get("error_type") or "none"), str(diag.get("reason") or "")


def _extract_json_object(text: str) -> dict:
    stripped = str(text or "").strip()
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
            return {}
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _parse_env_assignment(line: str) -> tuple[str, str] | tuple[None, None]:
    text = str(line or "").strip()
    if not text or text.startswith("#"):
        return None, None
    if text.startswith("export "):
        text = text[len("export ") :].strip()
    if "=" not in text:
        return None, None
    key, raw_value = text.split("=", 1)
    key = key.strip()
    if not ENV_KEY_PATTERN.match(key):
        return None, None
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _load_env_file(path: Path, allowed_keys: set[str] | None = None) -> int:
    if not path.exists():
        return 0
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    loaded = 0
    for line in content.splitlines():
        key, value = _parse_env_assignment(line)
        if not key:
            continue
        if isinstance(allowed_keys, set) and key not in allowed_keys:
            continue
        if str(os.getenv(key) or "").strip():
            continue
        os.environ[key] = value
        loaded += 1
    return loaded


def _bootstrap_env_from_repo(allowed_keys: set[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [Path.cwd() / ".env", repo_root / ".env"]
    loaded = 0
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        loaded += _load_env_file(path, allowed_keys=allowed_keys)
    return loaded


def _gemini_repair_model_text(
    *,
    original_text: str,
    failure_type: str,
    expected_stage: str,
    error_excerpt: str,
    repair_actions: list[str],
    model_name: str,
) -> tuple[str | None, str]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        _bootstrap_env_from_repo(allowed_keys={"GOOGLE_API_KEY", "LLM_MODEL", "GATEFORGE_GEMINI_MODEL", "GEMINI_MODEL"})
        api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None, "GOOGLE_API_KEY missing"
    model = os.getenv("LLM_MODEL") or os.getenv("GATEFORGE_GEMINI_MODEL") or os.getenv("GEMINI_MODEL")
    if not model:
        return None, "LLM_MODEL or GATEFORGE_GEMINI_MODEL or GEMINI_MODEL missing"
    prompt = (
        "You are fixing a Modelica model.\n"
        "Return ONLY JSON object with keys: patched_model_text, rationale.\n"
        "Constraints:\n"
        "- Keep model name unchanged.\n"
        "- Keep edits minimal and compile-oriented.\n"
        "- Do not output markdown.\n"
        f"- model_name: {model_name}\n"
        f"- failure_type: {failure_type}\n"
        f"- expected_stage: {expected_stage}\n"
        f"- error_excerpt: {error_excerpt[:1200]}\n"
        f"- suggested_actions: {json.dumps(repair_actions, ensure_ascii=True)}\n"
        "Model text below:\n"
        "-----BEGIN_MODEL-----\n"
        f"{original_text}\n"
        "-----END_MODEL-----\n"
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
    cfg = _live_budget_config()
    while True:
        allowed, _ledger = _reserve_live_request(cfg)
        if not allowed:
            return None, "live_request_budget_exceeded"
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                response_payload = json.loads(resp.read().decode("utf-8"))
            _record_live_request_success(cfg)
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if int(exc.code) == 429:
                stop_reason, _ledger = _record_live_request_429(cfg)
                if stop_reason:
                    return None, stop_reason
                continue
            return None, f"gemini_http_error:{exc.code}:{body[:180]}"
        except urllib.error.URLError as exc:
            return None, f"gemini_url_error:{exc.reason}"
    candidates = response_payload.get("candidates", [])
    if not candidates:
        return None, "gemini_no_candidates"
    text = (
        candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    )
    payload = _extract_json_object(text)
    patched = payload.get("patched_model_text")
    if not isinstance(patched, str) or not patched.strip():
        return None, "gemini_missing_patched_model_text"
    return patched, ""


def _parse_repair_actions(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                return [str(x) for x in payload if isinstance(x, str)]
        except Exception:
            pass
    return [x.strip() for x in text.split("|") if x.strip()]


def _extract_state_tokens_from_output(output: str) -> list[str]:
    tokens = sorted(set(re.findall(r"__gf_state_\d+", str(output or ""))))
    return tokens


def _extract_undef_tokens_from_output(output: str) -> list[str]:
    tokens = sorted(set(re.findall(r"__gf_undef_\d+", str(output or ""))))
    return tokens


def _remove_gateforge_injected_symbol_block(model_text: str) -> tuple[str, int]:
    lines = str(model_text or "").splitlines(keepends=True)
    if not lines:
        return str(model_text or ""), 0
    remove_idx: set[int] = set()
    for i, line in enumerate(lines):
        if "__gf_" in line:
            remove_idx.add(i)
            # Remove nearby mutation comment/equation headers that usually wrap injected block.
            for j in (i - 2, i - 1, i + 1, i + 2):
                if j < 0 or j >= len(lines):
                    continue
                text = lines[j].strip()
                if "GateForge mutation" in text:
                    remove_idx.add(j)
                if text == "equation":
                    remove_idx.add(j)
    if not remove_idx:
        return str(model_text or ""), 0
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), len(remove_idx)


def _apply_parse_error_pre_repair(model_text: str, output: str, failure_type: str) -> tuple[str, dict]:
    failure = str(failure_type or "").strip().lower()
    lower = str(output or "").lower()

    tokens: list[str] = []
    reason_prefix = ""
    if failure == "script_parse_error":
        if "no viable alternative near token" not in lower:
            return model_text, {"applied": False, "reason": "parse_error_without_expected_marker"}
        tokens = _extract_state_tokens_from_output(output)
        reason_prefix = "injected_state_tokens"
        if not tokens:
            # Fallback for parse errors where OMC reports generic token (`parameter`, `equation`)
            # but injected mutant symbols still exist in model text.
            fallback_patched, removed = _remove_gateforge_injected_symbol_block(model_text)
            if removed > 0:
                return fallback_patched, {
                    "applied": True,
                    "reason": "removed_gateforge_injected_symbol_block",
                    "removed_line_count": int(removed),
                }
            return model_text, {"applied": False, "reason": "state_token_not_detected"}
    elif failure == "model_check_error":
        # Some OMC parser errors can be mapped to model_check_error by the
        # diagnostic classifier. Recover these the same way as parse errors.
        parse_markers = ("no viable alternative near token", "lexer failed to recognize")
        if any(marker in lower for marker in parse_markers):
            state_tokens = _extract_state_tokens_from_output(output)
            if not state_tokens and "__gf_state_" in str(model_text or ""):
                state_tokens = sorted(set(re.findall(r"__gf_state_\d+", str(model_text or ""))))
            if state_tokens:
                tokens = state_tokens
                reason_prefix = "injected_state_tokens"
            else:
                fallback_patched, removed = _remove_gateforge_injected_symbol_block(model_text)
                if removed > 0:
                    return fallback_patched, {
                        "applied": True,
                        "reason": "removed_gateforge_injected_symbol_block",
                        "removed_line_count": int(removed),
                    }
                return model_text, {"applied": False, "reason": "state_token_not_detected"}
        else:
        # Common mutant pattern: undefined synthetic symbol `__gf_undef_<id>`.
            tokens = _extract_undef_tokens_from_output(output)
            if not tokens and "__gf_undef_" in str(model_text or ""):
                tokens = sorted(set(re.findall(r"__gf_undef_\d+", str(model_text or ""))))
            reason_prefix = "injected_undef_tokens"
            if not tokens:
                return model_text, {"applied": False, "reason": "undef_token_not_detected"}
    else:
        return model_text, {"applied": False, "reason": "failure_type_not_supported_for_pre_repair"}

    patched = str(model_text or "")
    # Prefer dropping full lines carrying injected state token to avoid
    # leaving broken fragments like `der() = ...;` after direct token removal.
    lines = patched.splitlines(keepends=True)
    kept_lines: list[str] = []
    removed_line_count = 0
    for line in lines:
        if any(tok in line for tok in tokens):
            removed_line_count += 1
            continue
        kept_lines.append(line)
    if removed_line_count > 0:
        return "".join(kept_lines), {
            "applied": True,
            "reason": f"removed_lines_with_{reason_prefix}",
            "detected_tokens": tokens,
            "removed_line_count": int(removed_line_count),
        }

    removed_count = 0
    for token in tokens:
        patched, replaced = re.subn(rf"\b{re.escape(token)}\b", "", patched)
        removed_count += int(replaced)

    if removed_count <= 0:
        return model_text, {
            "applied": False,
            "reason": "detected_token_not_found_in_model_text",
            "detected_tokens": tokens,
        }

    return patched, {
        "applied": True,
        "reason": f"removed_{reason_prefix}_inline",
        "detected_tokens": tokens,
        "removed_count": int(removed_count),
    }


def _normalize_terminal_errors(executor_status: str, error_message: str, compile_error: str, simulate_error: str) -> tuple[str, str, str]:
    if str(executor_status or "").upper() == "PASS":
        return "", "", ""
    return str(error_message or ""), str(compile_error or ""), str(simulate_error or "")


def _run_check_and_simulate(
    *,
    workspace: Path,
    model_file_name: str,
    model_name: str,
    timeout_sec: int,
    backend: str,
    docker_image: str,
    stop_time: float,
    intervals: int,
) -> tuple[int | None, str, bool, bool]:
    bootstrap = "loadModel(Modelica);\n"
    if backend != "omc":
        bootstrap = "installPackage(Modelica);\nloadModel(Modelica);\n"
    script = (
        bootstrap
        + f'loadFile("{model_file_name}");\n'
        + f"checkModel({model_name});\n"
        + f"simulate({model_name}, stopTime={float(stop_time)}, numberOfIntervals={int(intervals)});\n"
        + "getErrorString();\n"
    )
    if backend == "omc":
        rc, output = _run_omc_script_local(script, timeout_sec=timeout_sec, cwd=str(workspace))
    else:
        rc, output = _run_omc_script_docker(script, timeout_sec=timeout_sec, cwd=str(workspace), image=docker_image)
    check_ok, simulate_ok = _extract_om_success_flags(output)
    return rc, output, check_ok, simulate_ok


@contextmanager
def _temporary_workspace(prefix: str):
    # Docker may write root-owned files into the mounted workspace/cache, and
    # TemporaryDirectory cleanup can raise PermissionError on CI. Use mkdtemp
    # with best-effort cleanup that never propagates teardown failures.
    td = tempfile.mkdtemp(prefix=prefix)
    try:
        yield td
    finally:
        _cleanup_workspace_best_effort(td)


def _cleanup_workspace_best_effort(path: str) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Modelica executor with Gemini patching loop and OMC validation")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--failure-type", default="unknown")
    parser.add_argument("--expected-stage", default="unknown")
    parser.add_argument("--source-model-path", default="")
    parser.add_argument("--mutated-model-path", default="")
    parser.add_argument("--repair-actions", default="")
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--simulate-stop-time", type=float, default=0.2)
    parser.add_argument("--simulate-intervals", type=int, default=20)
    parser.add_argument("--backend", choices=["auto", "omc", "openmodelica_docker"], default="auto")
    parser.add_argument("--docker-image", default=os.getenv("GATEFORGE_OM_IMAGE", DEFAULT_DOCKER_IMAGE))
    parser.add_argument("--planner-backend", choices=["gemini", "rule"], default="gemini")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    started = time.monotonic()
    model_path = Path(str(args.mutated_model_path or "").strip() or str(args.source_model_path or "").strip())
    if not model_path.exists():
        payload = {
            "task_id": args.task_id,
            "check_model_pass": False,
            "simulate_pass": False,
            "physics_contract_pass": False,
            "regression_pass": False,
            "elapsed_sec": round(time.monotonic() - started, 4),
            "error_message": "model_path_missing",
            "compile_error": "model_path_missing",
            "simulate_error_message": "",
            "stderr_snippet": str(model_path),
        }
        if str(args.out).strip():
            Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload))
        return

    backend = str(args.backend).strip().lower()
    if backend == "auto":
        backend = "omc" if shutil.which("omc") else "openmodelica_docker"

    original_text = _read_text(model_path)
    model_name = _find_primary_model_name(original_text)
    if not model_name:
        payload = {
            "task_id": args.task_id,
            "check_model_pass": False,
            "simulate_pass": False,
            "physics_contract_pass": False,
            "regression_pass": False,
            "elapsed_sec": round(time.monotonic() - started, 4),
            "error_message": "model_name_not_found",
            "compile_error": "model_name_not_found",
            "simulate_error_message": "",
            "stderr_snippet": "",
        }
        if str(args.out).strip():
            Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload))
        return

    repair_actions = _parse_repair_actions(args.repair_actions)
    attempts: list[dict] = []
    current_text = original_text
    final_check_ok = False
    final_simulate_ok = False
    final_error = ""
    final_compile_error = ""
    final_sim_error = ""
    final_stderr = ""
    executor_status = "FAILED"
    budget_cfg = _live_budget_config()

    with _temporary_workspace(prefix="gf_live_exec_") as td:
        workspace = Path(td)
        model_file = workspace / model_path.name
        for round_idx in range(1, max(1, int(args.max_rounds)) + 1):
            model_file.write_text(current_text, encoding="utf-8")
            rc, output, check_ok, simulate_ok = _run_check_and_simulate(
                workspace=workspace,
                model_file_name=model_file.name,
                model_name=model_name,
                timeout_sec=max(1, int(args.timeout_sec)),
                backend=backend,
                docker_image=str(args.docker_image),
                stop_time=float(args.simulate_stop_time),
                intervals=max(1, int(args.simulate_intervals)),
            )
            diagnostic = build_diagnostic_ir_v0(
                output=output,
                check_model_pass=bool(check_ok),
                simulate_pass=bool(simulate_ok),
                expected_stage=str(args.expected_stage or ""),
                declared_failure_type=str(args.failure_type or ""),
            )
            ftype = str(diagnostic.get("error_type") or "none")
            reason = str(diagnostic.get("reason") or "")
            attempts.append(
                {
                    "round": round_idx,
                    "return_code": rc,
                    "check_model_pass": check_ok,
                    "simulate_pass": simulate_ok,
                    "observed_failure_type": ftype,
                    "reason": reason,
                    "diagnostic_ir": diagnostic,
                    "log_excerpt": str(output or "")[:1200],
                }
            )
            if check_ok and simulate_ok:
                final_check_ok = True
                final_simulate_ok = True
                executor_status = "PASS"
                final_stderr = str(output or "")[-1200:]
                break

            final_error = reason or "repair_round_failed"
            if not check_ok:
                final_compile_error = reason or "compile_failed"
            if check_ok and not simulate_ok:
                final_sim_error = reason or "simulate_failed"
            final_stderr = str(output or "")[-1200:]

            if round_idx >= max(1, int(args.max_rounds)):
                break

            pre_repaired_text, pre_repair = _apply_parse_error_pre_repair(
                model_text=current_text,
                output=str(output or ""),
                failure_type=ftype,
            )
            attempts[-1]["pre_repair"] = pre_repair
            if bool(pre_repair.get("applied")):
                current_text = pre_repaired_text
                final_error = "pre_repair_applied_retry_pending"
                continue

            if str(args.planner_backend) == "gemini":
                patched, gemini_err = _gemini_repair_model_text(
                    original_text=current_text,
                    failure_type=str(args.failure_type),
                    expected_stage=str(args.expected_stage),
                    error_excerpt=str(output or "")[-1800:],
                    repair_actions=repair_actions,
                    model_name=model_name,
                )
                if isinstance(patched, str) and patched.strip():
                    current_text = patched
                else:
                    final_error = gemini_err or "gemini_patch_generation_failed"
                    break
            else:
                # rule backend does not mutate model text; useful for dry harness checks.
                break

    elapsed = round(time.monotonic() - started, 4)
    final_error, final_compile_error, final_sim_error = _normalize_terminal_errors(
        executor_status=executor_status,
        error_message=final_error,
        compile_error=final_compile_error,
        simulate_error=final_sim_error,
    )
    payload = {
        "task_id": str(args.task_id),
        "failure_type": str(args.failure_type),
        "executor_status": executor_status,
        "planner_backend": str(args.planner_backend),
        "backend_used": backend,
        "check_model_pass": bool(final_check_ok),
        "simulate_pass": bool(final_simulate_ok),
        "physics_contract_pass": bool(final_check_ok and final_simulate_ok),
        "regression_pass": bool(final_check_ok and final_simulate_ok),
        "elapsed_sec": elapsed,
        "error_message": final_error,
        "compile_error": final_compile_error,
        "simulate_error_message": final_sim_error,
        "stderr_snippet": final_stderr,
        "attempts": attempts,
        "live_budget": {
            "max_requests_per_run": int(budget_cfg.get("max_requests_per_run") or 0),
            "max_consecutive_429": int(budget_cfg.get("max_consecutive_429") or 0),
            "base_backoff_sec": float(budget_cfg.get("base_backoff_sec") or 0.0),
            "max_backoff_sec": float(budget_cfg.get("max_backoff_sec") or 0.0),
        },
    }
    ledger = _load_live_ledger(budget_cfg)
    payload["live_request_count"] = int(ledger.get("request_count") or 0)
    payload["rate_limit_429_count"] = int(ledger.get("rate_limit_429_count") or 0)
    payload["budget_stop_triggered"] = bool(ledger.get("budget_stop_triggered"))
    payload["live_budget_stop_reason"] = str(ledger.get("last_stop_reason") or "")
    if str(args.out).strip():
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
