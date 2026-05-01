from __future__ import annotations

import io
import json
import re
import tokenize
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "no_wrapper_repair_audit_v0_36_6"

PROHIBITED_PATTERNS = {
    "deterministic_repair_flag": re.compile(r"\bdeterministic_repair_added\s*=\s*True\b"),
    "hidden_routing_flag": re.compile(r"\bhidden_routing_added\s*=\s*True\b"),
    "candidate_selection_flag": re.compile(r"\bcandidate_selection_added\s*=\s*True\b"),
    "auto_submit_flag": re.compile(r"\bauto_submit\s*=\s*True\b"),
    "candidate_selected_flag": re.compile(r"\bcandidate_selected\s*=\s*True\b"),
    "deterministic_patch_function": re.compile(r"\bdef\s+(generate_patch|auto_repair|deterministic_repair)\b"),
    "hidden_router_function": re.compile(r"\bdef\s+(route_by_error|select_candidate|choose_repair)\b"),
}


def _code_without_strings_or_comments(text: str) -> str:
    output: list[str] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type in {tokenize.STRING, tokenize.COMMENT}:
                continue
            output.append(token.string)
    except tokenize.TokenError:
        return text
    return " ".join(output)


def audit_file_for_wrapper_repair(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    code = _code_without_strings_or_comments(text)
    hits: list[dict[str, str]] = []
    for rule, pattern in PROHIBITED_PATTERNS.items():
        match = pattern.search(code)
        if match:
            hits.append({"rule": rule, "snippet": code[max(0, match.start() - 40) : match.end() + 40]})
    return {
        "path": str(path),
        "status": "PASS" if not hits else "FAIL",
        "hit_count": len(hits),
        "hits": hits,
    }


def build_no_wrapper_repair_audit(
    paths: list[Path],
    *,
    version: str = "v0.36.6",
) -> dict[str, Any]:
    rows = [audit_file_for_wrapper_repair(path) for path in paths if path.exists()]
    failed = [row for row in rows if row["status"] != "PASS"]
    return {
        "version": version,
        "analysis_scope": "no_wrapper_repair_audit",
        "status": "PASS" if not failed else "FAIL",
        "wrapper_repair_detected": bool(failed),
        "file_count": len(rows),
        "failed_file_count": len(failed),
        "results": rows,
    }


def write_no_wrapper_repair_audit_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

