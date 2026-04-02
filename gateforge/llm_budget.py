"""LLM request budget tracking and rate-limit backoff.

Manages per-run request caps, 429-rate-limit exponential backoff,
and ledger persistence (in-memory or file-based). Provider-agnostic.

Extracted from agent_modelica_live_executor_v1.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path


LIVE_LEDGER_SCHEMA_VERSION = "agent_modelica_live_request_ledger_v1"

_IN_MEMORY_LIVE_LEDGER: dict[str, dict] = {}


# ---- env helpers ----

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


# ---- json helpers ----

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


# ---- budget configuration ----

def _llm_request_timeout_sec() -> float:
    return max(1.0, _to_float_env("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", 120.0))


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


# ---- ledger operations ----

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


def _live_ledger_key(cfg: dict) -> str:
    ledger_path = str(cfg.get("ledger_path") or "").strip()
    if ledger_path:
        return str(Path(ledger_path).resolve())
    return "__process__"


def _load_live_ledger(cfg: dict) -> dict:
    ledger_path = str(cfg.get("ledger_path") or "").strip()
    if not ledger_path:
        payload = _IN_MEMORY_LIVE_LEDGER.get(_live_ledger_key(cfg))
        if not payload:
            return _empty_live_ledger(cfg)
        out = _empty_live_ledger(cfg)
        out.update(payload)
        if cfg.get("stage"):
            out["last_stage"] = str(cfg.get("stage") or "")
        return out
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
        _IN_MEMORY_LIVE_LEDGER[_live_ledger_key(cfg)] = dict(payload)
        return
    _write_json(Path(ledger_path), payload)


# ---- budget gate operations ----

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
