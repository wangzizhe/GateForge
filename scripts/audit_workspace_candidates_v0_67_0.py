from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_workspace_style_probe_v0_67_0 import (
    _extract_model_name,
    _safe_candidate_id,
)
from gateforge.agent_modelica_hard_core_training_substrate_v0_43_0 import load_json, load_jsonl


DEFAULT_WORKSPACES_DIR = REPO_ROOT / "artifacts" / "workspace_style_probe_v0_67_0" / "workspaces"


ZERO_FLOW_PATTERN = re.compile(r"(\w+(?:\[\d+(?:,\s*\d+)*\])?)\s*\.\s*i\s*=\s*0\s*;", re.MULTILINE)


def zero_flow_targets(text: str) -> list[str]:
    targets: list[str] = []
    for match in ZERO_FLOW_PATTERN.finditer(text):
        tgt = match.group(1).strip()
        if tgt not in targets:
            targets.append(tgt)
    return sorted(targets)


def _count_modelica_declarations(text: str, keyword: str) -> int:
    return len(
        re.findall(
            rf"\b{keyword}\b\s+[\w']
            (?![\s]*=)(?![\s]*\()(?![\s]*model\s)(?![\s]*end\s)"
            r"[\w.,\[\]\s']*;",
            text,
        )
    )


def _equation_count(text: str) -> int:
    eq_section = re.search(r"\bequation\b\s*(.*?)\bend\b\s*\w*\s*;", text, re.DOTALL)
    if not eq_section:
        return 0
    body = eq_section.group(1)
    raw = re.findall(r"[^;]+;", body)
    return sum(1 for line in raw if line.strip() and not line.strip().startswith("//"))


def _variable_count(text: str) -> int:
    return _count_modelica_declarations(text, "Real") + _count_modelica_declarations(text, "Integer")


def audit_candidate_file(
    candidate_path: Path,
    *,
    reference_text: str,
) -> dict[str, Any]:
    text = candidate_path.read_text(encoding="utf-8")
    ref_model_name = _extract_model_name(reference_text)
    model_name = _extract_model_name(text)
    ref_vars = _variable_count(reference_text)
    ref_eqs = _equation_count(reference_text)
    cand_vars = _variable_count(text)
    cand_eqs = _equation_count(text)
    return {
        "candidate_id": _safe_candidate_id(candidate_path.stem),
        "path": str(candidate_path),
        "model_name": model_name,
        "zero_flow_targets": zero_flow_targets(text),
        "variable_count": cand_vars,
        "equation_count": cand_eqs,
        "variable_delta": cand_vars - ref_vars,
        "equation_delta": cand_eqs - ref_eqs,
        "equation_variable_balance": (cand_eqs - cand_vars),
        "byte_count": candidate_path.stat().st_size,
    }


def audit_workspace(
    workspace_dir: Path,
    *,
    results_jsonl: Path | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    initial_path = workspace_dir / "initial.mo"
    reference_text = initial_path.read_text(encoding="utf-8") if initial_path.exists() else ""
    case_id = workspace_dir.name

    candidate_results: dict[str, dict[str, Any]] = {}
    if results_jsonl and results_jsonl.exists():
        for row in load_jsonl(results_jsonl):
            if str(row.get("case_id") or "") == case_id:
                for cf in row.get("candidate_files") or []:
                    cid = str(cf.get("candidate_id") or "")
                    candidate_results[cid] = {
                        "write_check_ok": bool(cf.get("write_check_ok")),
                        "last_simulated": bool(cf.get("last_simulated")),
                    }
                if row.get("submitted"):
                    candidate_results.setdefault(
                        str(row.get("submitted_candidate_id") or ""), {}
                    )["was_submitted"] = True

    candidates: list[dict[str, Any]] = []
    for path in sorted(workspace_dir.glob("*.mo")):
        if path.name == "initial.mo":
            continue
        audit = audit_candidate_file(path, reference_text=reference_text)
        outcome = candidate_results.get(audit["candidate_id"], {})
        audit["write_check_ok"] = outcome.get("write_check_ok")
        audit["last_simulated"] = outcome.get("last_simulated")
        audit["was_submitted"] = outcome.get("was_submitted", False)
        candidates.append(audit)

    return {
        "case_id": case_id,
        "workspace_dir": str(workspace_dir),
        "candidate_count": len(candidates),
        "submitted_count": sum(1 for c in candidates if c.get("was_submitted")),
        "checked_count": sum(1 for c in candidates if c.get("write_check_ok") is not None),
        "check_pass_count": sum(1 for c in candidates if c.get("write_check_ok") is True),
        "simulated_count": sum(1 for c in candidates if c.get("last_simulated")),
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline audit of workspace-style candidate .mo files."
    )
    parser.add_argument("--workspaces-dir", type=Path, default=DEFAULT_WORKSPACES_DIR)
    parser.add_argument("--results-jsonl", type=Path, default=None)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--out-path", type=Path, default=None)
    args = parser.parse_args()

    workspaces_dir = args.workspaces_dir
    if not workspaces_dir.exists():
        print(json.dumps({"error": "workspaces_dir not found", "path": str(workspaces_dir)}))
        return 1

    wanted = set(args.case_id or [])
    results: list[dict[str, Any]] = []
    for workspace_dir in sorted(workspaces_dir.iterdir()):
        if not workspace_dir.is_dir():
            continue
        if wanted and workspace_dir.name not in wanted:
            continue
        result = audit_workspace(
            workspace_dir,
            results_jsonl=args.results_jsonl,
        )
        results.append(result)

    summary = {
        "total_cases": len(results),
        "total_candidates": sum(r["candidate_count"] for r in results),
        "total_submitted": sum(r["submitted_count"] for r in results),
        "total_checked": sum(r["checked_count"] for r in results),
        "total_check_pass": sum(r["check_pass_count"] for r in results),
        "total_simulated": sum(r["simulated_count"] for r in results),
        "per_case": results,
    }

    output = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.out_path:
        args.out_path.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
