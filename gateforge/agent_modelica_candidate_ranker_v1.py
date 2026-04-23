"""Candidate ranker for multi-candidate repair sampling (v0.19.51).

Pure ranking layer for the search-based repair pattern. Takes a list of LLM
repair candidates, runs an injected OMC checkModel callable on each, and ranks
them by structural residual signals.

Discipline:
  - This module performs NO repair logic, NO heuristic patching, NO LLM calls.
  - Ranking signals come exclusively from raw OMC output.
  - The OMC runner is injected (run_omc) so this module is testable without
    Docker / OpenModelica installed.
  - A failed OMC run (timeout, crash, parse failure) sinks the candidate to
    score = -inf rather than aborting the whole ranking pass.

Score ordering:
  1. check_pass (True > False)              — strongest signal
  2. -abs(deficit)                          — closer to well-determined wins
  3. -error_count                           — fewer reported errors wins

Intentional non-feature: ranker does NOT short-circuit on the first check_pass.
All N candidates are evaluated on every call so the runner can record
coverage@K (how many of the K samples reach check_pass / simulate_pass).
That signal is the whole point of the multi-candidate experiment; an
early-stop optimization would hide it. Do not add `early_stop=True` here.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class RankedCandidate:
    """A repair candidate annotated with OMC signal and ranking score."""
    candidate_id: int
    patched_text: str | None
    llm_error: str
    provider: str
    temperature_used: float | None
    check_pass: bool
    equation_count: int | None
    variable_count: int | None
    deficit: int | None
    error_count: int
    omc_output: str
    score: float

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "patched_text": self.patched_text,
            "llm_error": self.llm_error,
            "provider": self.provider,
            "temperature_used": self.temperature_used,
            "check_pass": self.check_pass,
            "equation_count": self.equation_count,
            "variable_count": self.variable_count,
            "deficit": self.deficit,
            "error_count": self.error_count,
            "score": self.score if math.isfinite(self.score) else None,
            "omc_output_length": len(self.omc_output or ""),
        }


def _extract_eq_var_counts(omc_output: str) -> tuple[int | None, int | None]:
    """Parse equation and variable counts from OMC checkModel output.

    Mirrors the regex used in v0.19.49 runner (_extract_eq_var_counts).
    """
    if not omc_output:
        return None, None
    m = re.search(r"has\s+(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)", omc_output)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _count_errors(omc_output: str) -> int:
    """Count distinct 'Error:' lines in OMC output.

    Crude but stable signal — does not classify by error type.
    """
    if not omc_output:
        return 0
    return sum(
        1 for line in omc_output.splitlines()
        if "Error:" in line
    )


def _compute_score(
    *,
    check_pass: bool,
    deficit: int | None,
    error_count: int,
) -> float:
    """Compute single-number score from structural OMC signals.

    Weighting:
      - check_pass dominates: +1000 if True
      - deficit penalty: -10 per unit of |deficit|
      - error penalty: -1 per error line
    """
    score = 1000.0 if check_pass else 0.0
    if deficit is not None:
        score -= 10.0 * abs(deficit)
    score -= float(error_count)
    return score


def evaluate_candidate(
    *,
    candidate_id: int,
    patched_text: str | None,
    llm_error: str,
    provider: str,
    temperature_used: float | None,
    run_omc: Callable[[str], tuple[bool, str]],
) -> RankedCandidate:
    """Run OMC on one candidate, parse signals, compute score.

    On any exception from run_omc, the candidate is recorded with
    score = -inf (sinks below all real candidates).

    Args:
        candidate_id: Integer index of this candidate within its sampling batch.
        patched_text: The LLM's proposed model text (None if LLM call failed).
        llm_error: Non-empty string if the LLM call itself failed.
        provider: Resolved provider name (gemini / openai / ...).
        temperature_used: Temperature value used for this LLM call (if known).
        run_omc: Callable taking model text, returning (check_pass, raw_output).

    Returns:
        RankedCandidate with all signals populated (or -inf score on failure).
    """
    if patched_text is None or not patched_text.strip():
        return RankedCandidate(
            candidate_id=candidate_id,
            patched_text=patched_text,
            llm_error=llm_error or "empty_patched_text",
            provider=provider,
            temperature_used=temperature_used,
            check_pass=False,
            equation_count=None,
            variable_count=None,
            deficit=None,
            error_count=0,
            omc_output="",
            score=float("-inf"),
        )
    try:
        check_pass, omc_output = run_omc(patched_text)
    except Exception as exc:
        return RankedCandidate(
            candidate_id=candidate_id,
            patched_text=patched_text,
            llm_error=llm_error,
            provider=provider,
            temperature_used=temperature_used,
            check_pass=False,
            equation_count=None,
            variable_count=None,
            deficit=None,
            error_count=0,
            omc_output=f"omc_runner_exception: {type(exc).__name__}: {exc}",
            score=float("-inf"),
        )
    eq, var = _extract_eq_var_counts(omc_output)
    deficit = (var - eq) if (eq is not None and var is not None) else None
    error_count = _count_errors(omc_output)
    score = _compute_score(
        check_pass=bool(check_pass),
        deficit=deficit,
        error_count=error_count,
    )
    return RankedCandidate(
        candidate_id=candidate_id,
        patched_text=patched_text,
        llm_error=llm_error,
        provider=provider,
        temperature_used=temperature_used,
        check_pass=bool(check_pass),
        equation_count=eq,
        variable_count=var,
        deficit=deficit,
        error_count=error_count,
        omc_output=str(omc_output or ""),
        score=score,
    )


def rank_candidates(
    candidates: list[dict],
    *,
    run_omc: Callable[[str], tuple[bool, str]],
) -> list[RankedCandidate]:
    """Evaluate all candidates and return them sorted by descending score.

    Args:
        candidates: List of dicts. Each must have keys:
            - patched_text: str | None
            - llm_error: str (empty if LLM call succeeded)
            - provider: str
            - temperature_used: float | None  (optional)
            Optional keys are tolerated.
        run_omc: Callable taking model text, returning (check_pass, raw_output).

    Returns:
        List of RankedCandidate sorted by score descending.
        Empty input → empty list.
    """
    if not candidates:
        return []
    evaluated: list[RankedCandidate] = []
    for idx, cand in enumerate(candidates):
        evaluated.append(
            evaluate_candidate(
                candidate_id=idx,
                patched_text=cand.get("patched_text"),
                llm_error=str(cand.get("llm_error") or ""),
                provider=str(cand.get("provider") or ""),
                temperature_used=cand.get("temperature_used"),
                run_omc=run_omc,
            )
        )
    evaluated.sort(key=lambda c: c.score, reverse=True)
    return evaluated
