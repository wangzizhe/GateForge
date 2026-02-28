from __future__ import annotations


def classify_admission_failure_stage(
    *,
    check_ok: bool,
    simulate_ok: bool,
    output: str,
) -> str:
    lowered = str(output or "").lower()
    if (
        "permission denied" in lowered and "docker" in lowered
        or "cannot connect to the docker" in lowered
        or "docker daemon" in lowered
    ):
        return "environment_blocked"
    if check_ok and simulate_ok:
        return "already_pass"
    if check_ok and not simulate_ok:
        return "simulate"
    if not check_ok:
        return "model_check"
    return "unknown"


def count_admission_failure_stages(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        stage = str(row.get("admission_failure_stage") or "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    return dict(sorted(counts.items()))
