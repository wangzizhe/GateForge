from __future__ import annotations


def prioritize_repair_actions_v0(actions: list[str], expected_stage: str) -> list[str]:
    stage = str(expected_stage or "").strip().lower()
    src = [str(x).strip() for x in (actions or []) if str(x).strip()]

    def score(action: str) -> tuple[int, str]:
        lower = action.lower()
        check_related = any(k in lower for k in ("checkmodel", "symbol", "connector", "declaration", "compile"))
        simulate_related = any(k in lower for k in ("simulate", "solver", "initial", "runtime"))
        if stage == "check":
            pri = 0 if check_related else 1
        elif stage == "simulate":
            if check_related:
                pri = 0
            elif simulate_related:
                pri = 1
            else:
                pri = 2
        else:
            pri = 1
        return pri, lower

    return sorted(src, key=score)


def detect_no_progress_v0(attempts: list[dict], *, window: int = 2) -> bool:
    if len(attempts) < max(2, int(window)):
        return False
    tail = attempts[-int(window) :]
    failure_types = [str(x.get("observed_failure_type") or "").strip().lower() for x in tail if isinstance(x, dict)]
    reasons = [str(x.get("reason") or "").strip().lower() for x in tail if isinstance(x, dict)]
    checks = [bool(x.get("check_model_pass")) for x in tail if isinstance(x, dict)]
    sims = [bool(x.get("simulate_pass")) for x in tail if isinstance(x, dict)]
    if len(failure_types) < int(window) or len(reasons) < int(window):
        return False
    if any(x in {"", "none"} for x in failure_types):
        return False
    if len(set(failure_types)) == 1 and len(set(reasons)) == 1 and len(set(checks)) == 1 and len(set(sims)) == 1:
        return True
    return False
