from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from .checkers import run_checkers

PHYSICS_CONTRACT_SCHEMA_VERSION = "physics_contract_v0"
DEFAULT_PHYSICS_CONTRACT_PATH = "policies/physics_contract_v0.json"
SUPPORTED_INVARIANT_TYPES = {"range", "monotonic", "bounded_delta"}

_DEFAULT_CONTRACT = {
    "schema_version": PHYSICS_CONTRACT_SCHEMA_VERSION,
    "name": "gateforge_physics_contract_v0",
    "checker": "invariant_guard",
    "checker_config": {
        "invariant_guard": {
            "invariants": [],
        }
    },
    "physical_invariants": [],
    "profiles_by_scale": {},
}


def default_physics_contract_v0() -> dict:
    return deepcopy(_DEFAULT_CONTRACT)


def _validate_invariant(inv: dict, idx: int) -> None:
    inv_type = inv.get("type")
    metric = inv.get("metric")
    if not isinstance(inv_type, str) or not inv_type:
        raise ValueError(f"physical_invariants[{idx}].type must be a non-empty string")
    if inv_type not in SUPPORTED_INVARIANT_TYPES:
        raise ValueError(f"physical_invariants[{idx}].type unsupported: {inv_type}")
    if not isinstance(metric, str) or not metric:
        raise ValueError(f"physical_invariants[{idx}].metric must be a non-empty string")

    if inv_type == "range":
        min_v = inv.get("min")
        max_v = inv.get("max")
        if min_v is not None and not isinstance(min_v, (int, float)):
            raise ValueError(f"physical_invariants[{idx}].min must be numeric when provided")
        if max_v is not None and not isinstance(max_v, (int, float)):
            raise ValueError(f"physical_invariants[{idx}].max must be numeric when provided")
        if isinstance(min_v, (int, float)) and isinstance(max_v, (int, float)) and float(min_v) > float(max_v):
            raise ValueError(f"physical_invariants[{idx}] requires min <= max")
        return

    if inv_type == "monotonic":
        direction = inv.get("direction")
        if direction not in {"non_increasing", "non_decreasing"}:
            raise ValueError(f"physical_invariants[{idx}].direction must be non_increasing/non_decreasing")
        return

    max_abs_delta = inv.get("max_abs_delta")
    if not isinstance(max_abs_delta, (int, float)) or float(max_abs_delta) <= 0:
        raise ValueError(f"physical_invariants[{idx}].max_abs_delta must be > 0")


def _validate_invariants(invariants: list[dict]) -> None:
    for idx, inv in enumerate(invariants):
        if not isinstance(inv, dict):
            raise ValueError(f"physical_invariants[{idx}] must be an object")
        _validate_invariant(inv, idx)


def validate_physics_contract_v0(contract: dict) -> dict:
    if not isinstance(contract, dict):
        raise ValueError("physics contract must be a JSON object")
    if contract.get("schema_version") != PHYSICS_CONTRACT_SCHEMA_VERSION:
        raise ValueError(f"physics contract schema_version must be {PHYSICS_CONTRACT_SCHEMA_VERSION}")

    checker = contract.get("checker")
    if checker != "invariant_guard":
        raise ValueError("physics contract checker must be invariant_guard")

    checker_config = contract.get("checker_config")
    if checker_config is not None and not isinstance(checker_config, dict):
        raise ValueError("physics contract checker_config must be an object")

    physical_invariants = contract.get("physical_invariants")
    if physical_invariants is not None:
        if not isinstance(physical_invariants, list):
            raise ValueError("physics contract physical_invariants must be a list")
        _validate_invariants(physical_invariants)

    profiles_by_scale = contract.get("profiles_by_scale")
    if profiles_by_scale is not None:
        if not isinstance(profiles_by_scale, dict):
            raise ValueError("physics contract profiles_by_scale must be an object")
        for scale, cfg in profiles_by_scale.items():
            if scale not in {"small", "medium", "large"}:
                raise ValueError(f"physics contract profiles_by_scale has unsupported scale: {scale}")
            if not isinstance(cfg, dict):
                raise ValueError(f"physics contract profiles_by_scale[{scale}] must be an object")
            invs = cfg.get("invariants", [])
            if invs is not None:
                if not isinstance(invs, list):
                    raise ValueError(f"physics contract profiles_by_scale[{scale}].invariants must be a list")
                _validate_invariants(invs)

    guard_cfg = (checker_config or {}).get("invariant_guard", {})
    if guard_cfg is not None and not isinstance(guard_cfg, dict):
        raise ValueError("physics contract checker_config.invariant_guard must be an object")
    guard_invariants = guard_cfg.get("invariants", []) if isinstance(guard_cfg, dict) else []
    if guard_invariants is not None:
        if not isinstance(guard_invariants, list):
            raise ValueError("physics contract checker_config.invariant_guard.invariants must be a list")
        _validate_invariants(guard_invariants)

    merged = default_physics_contract_v0()
    merged.update({k: v for k, v in contract.items() if k in merged or k in {"name"}})
    merged_checker_cfg = deepcopy(merged.get("checker_config", {}))
    user_cfg = contract.get("checker_config") if isinstance(contract.get("checker_config"), dict) else {}
    if user_cfg:
        merged_checker_cfg.update(user_cfg)
    merged["checker_config"] = merged_checker_cfg
    return merged


def load_physics_contract_v0(path: str | None = None) -> tuple[dict, str]:
    resolved = path or DEFAULT_PHYSICS_CONTRACT_PATH
    p = Path(resolved)
    if p.exists():
        payload = json.loads(p.read_text(encoding="utf-8"))
        return validate_physics_contract_v0(payload), str(p)
    if path and path != DEFAULT_PHYSICS_CONTRACT_PATH:
        raise FileNotFoundError(f"Physics contract not found: {resolved}")
    return default_physics_contract_v0(), "builtin_default"


def _resolve_invariants(contract: dict, task_invariants: list[dict] | None) -> list[dict]:
    from_contract = contract.get("physical_invariants") if isinstance(contract.get("physical_invariants"), list) else []
    from_checker_cfg = []
    checker_cfg = contract.get("checker_config") if isinstance(contract.get("checker_config"), dict) else {}
    guard_cfg = checker_cfg.get("invariant_guard") if isinstance(checker_cfg.get("invariant_guard"), dict) else {}
    if isinstance(guard_cfg.get("invariants"), list):
        from_checker_cfg = guard_cfg.get("invariants")

    supplied = task_invariants if isinstance(task_invariants, list) else []
    merged = [x for x in [*from_contract, *from_checker_cfg, *supplied] if isinstance(x, dict)]
    _validate_invariants(merged)
    return merged


def _resolve_profile_invariants(contract: dict, scale: str | None) -> list[dict]:
    if not isinstance(scale, str) or not scale.strip():
        return []
    key = scale.strip().lower()
    profiles = contract.get("profiles_by_scale") if isinstance(contract.get("profiles_by_scale"), dict) else {}
    profile = profiles.get(key) if isinstance(profiles.get(key), dict) else {}
    invs = profile.get("invariants") if isinstance(profile.get("invariants"), list) else []
    _validate_invariants(invs)
    return invs


def evaluate_physics_contract_v0(
    contract: dict,
    task_invariants: list[dict] | None,
    baseline_metrics: dict | None,
    candidate_metrics: dict | None,
    scale: str | None = None,
) -> dict:
    invariants = [*_resolve_invariants(contract, task_invariants), *_resolve_profile_invariants(contract, scale)]
    if not invariants:
        return {
            "pass": True,
            "schema_version": PHYSICS_CONTRACT_SCHEMA_VERSION,
            "checker": "invariant_guard",
            "invariant_count": 0,
            "reasons": [],
            "findings": [],
        }

    checker_config = deepcopy(contract.get("checker_config") if isinstance(contract.get("checker_config"), dict) else {})
    guard_cfg = checker_config.get("invariant_guard") if isinstance(checker_config.get("invariant_guard"), dict) else {}
    guard_cfg = deepcopy(guard_cfg)
    guard_cfg["invariants"] = invariants
    checker_config["invariant_guard"] = guard_cfg

    baseline = {"metrics": baseline_metrics if isinstance(baseline_metrics, dict) else {}}
    candidate = {"metrics": candidate_metrics if isinstance(candidate_metrics, dict) else {}}
    findings, reasons = run_checkers(
        baseline=baseline,
        candidate=candidate,
        checker_names=["invariant_guard"],
        checker_config=checker_config,
    )

    return {
        "pass": len(reasons) == 0,
        "schema_version": PHYSICS_CONTRACT_SCHEMA_VERSION,
        "checker": "invariant_guard",
        "invariant_count": len(invariants),
        "reasons": reasons,
        "findings": findings,
    }
