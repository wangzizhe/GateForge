"""Build failure taxonomy for structural underdetermined experiments (v0.19.42)."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "artifacts" / "failure_taxonomy_v0_19_42"
ABLATION_RESULTS = REPO_ROOT / "artifacts" / "context_ablation_experiment_v0_19_42" / "experiment_results.jsonl"
V37_RESULTS = REPO_ROOT / "artifacts" / "phantom_multiturn_experiment_v0_19_37" / "experiment_results.jsonl"
ADMITTED_V34 = REPO_ROOT / "artifacts" / "structural_mutation_experiment_v0_19_34" / "admitted_cases.jsonl"
ADMITTED_V38 = REPO_ROOT / "artifacts" / "compound_underdetermined_experiment_v0_19_38" / "admitted_cases.jsonl"
ABLATION_PATCHED = REPO_ROOT / "artifacts" / "context_ablation_experiment_v0_19_42" / "patched_models"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _load_cases() -> dict[str, dict]:
    rows = {}
    for path in (ADMITTED_V34, ADMITTED_V38):
        for row in _read_jsonl(path):
            rows[row["candidate_id"]] = row
    return rows


def _mentions_target_change(broken: str, patched: str, targets: list[str]) -> bool:
    broken_lines = broken.splitlines()
    patched_lines = patched.splitlines()
    changed = set(broken_lines) ^ set(patched_lines)
    return any(any(t in line for t in targets) for line in changed)


def _phantom_fixed(patched: str, target: str) -> bool:
    decl_re = re.compile(rf"^\s*Real\s+{re.escape(target)}\b", re.MULTILINE)
    token_count = len(re.findall(rf"\b{re.escape(target)}\b", patched))
    base = target[:-8] if target.endswith("_phantom") else target
    return not decl_re.search(patched) and token_count == 0 and re.search(rf"\b{re.escape(base)}\b", patched) is not None


def _parameter_fixed(patched: str, target: str) -> bool:
    if re.search(rf"^\s*parameter\s+Real\s+{re.escape(target)}\b.*=", patched, re.MULTILINE):
        return True
    if re.search(rf"^\s*Real\s+{re.escape(target)}\b.*=", patched, re.MULTILINE):
        return True
    if re.search(rf"^\s*{re.escape(target)}\s*=", patched, re.MULTILINE):
        return True
    return False


def _taxonomy_for_failure(case: dict, condition_name: str, result: dict, patched_text: str | None, broken_text: str) -> str:
    if result.get("fix_pass"):
        return "SUCCESS"
    error_class = result.get("error_class") or ""
    llm_error = (result.get("llm_error") or "").lower()
    if error_class == "service_error":
        return "STOCHASTIC_FAIL"
    if error_class == "format_err" or any(x in llm_error for x in ("missing_patched_model_text", "no_output", "json")):
        return "FORMAT_ERR"
    if patched_text is None:
        return "FORMAT_ERR" if error_class else "OTHER"
    if patched_text == broken_text:
        return "NO_OP_AMBIGUITY"

    family = case.get("mutation_type") or case.get("mutation_family")
    if family == "phantom_variable":
        target = case["target_name"]
        if not _phantom_fixed(patched_text, target):
            return "EXECUTION_INCOMPLETE"
    elif family == "parameter_promotion":
        target = case["target_name"]
        if not _parameter_fixed(patched_text, target):
            if not _mentions_target_change(broken_text, patched_text, [target]):
                return "LOCALIZATION_FAIL"
            return "EXECUTION_INCOMPLETE"
    else:
        pp = case["pp_target"]
        pv = case["pv_target"]
        pp_fixed = _parameter_fixed(patched_text, pp)
        pv_fixed = _phantom_fixed(patched_text, pv)
        if not pp_fixed and not pv_fixed:
            if not _mentions_target_change(broken_text, patched_text, [pp, pv]):
                return "NO_OP_AMBIGUITY"
            return "LOCALIZATION_FAIL"
        if pp_fixed ^ pv_fixed:
            return "EXECUTION_INCOMPLETE"
    omc_excerpt = (result.get("omc_output_snippet") or "").lower()
    if any(x in omc_excerpt for x in ("parse", "syntax", "token")):
        return "SYNTAX_BROKEN"
    return "OTHER"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = _load_cases()
    rows = []
    for row in _read_jsonl(ABLATION_RESULTS):
        cid = row["candidate_id"]
        case = cases[cid]
        broken_text = Path(case["mutated_model_path"]).read_text(encoding="utf-8")
        for condition_key, suffix in {
            "condition_a": None,
            "condition_c1": "C1",
            "condition_c2": "C2",
            "condition_c3": "C3",
        }.items():
            result = row[condition_key]
            patched_text = None
            if suffix is not None:
                p = ABLATION_PATCHED / f"{cid}_{suffix}.mo"
                if p.exists():
                    patched_text = p.read_text(encoding="utf-8")
            taxonomy = _taxonomy_for_failure(case, condition_key, result, patched_text, broken_text)
            rows.append({
                "candidate_id": cid,
                "family": row["family"],
                "condition": condition_key,
                "fix_pass": bool(result.get("fix_pass")),
                "taxonomy": taxonomy,
            })

    # add v0.19.37 turn2 results as an extra view for phantom self-healing
    for row in _read_jsonl(V37_RESULTS):
        if not row.get("turn2_attempted"):
            continue
        taxonomy = "SUCCESS" if row.get("turn2_pass") else ("STOCHASTIC_FAIL" if row.get("turn2_error_class") == "service_error" else "OTHER")
        rows.append({
            "candidate_id": row["candidate_id"],
            "family": "phantom_variable",
            "condition": "turn2_raw_followup",
            "fix_pass": bool(row.get("turn2_pass")),
            "taxonomy": taxonomy,
        })

    (OUT_DIR / "taxonomy_rows.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )

    summary: dict[str, dict] = {"version": "v0.19.42", "by_family_condition": {}}
    for family in sorted({r["family"] for r in rows}):
        family_rows = [r for r in rows if r["family"] == family]
        summary["by_family_condition"][family] = {}
        for condition in sorted({r["condition"] for r in family_rows}):
            cond_rows = [r for r in family_rows if r["condition"] == condition]
            counts: dict[str, int] = {}
            for r in cond_rows:
                counts[r["taxonomy"]] = counts.get(r["taxonomy"], 0) + 1
            summary["by_family_condition"][family][condition] = counts
    (OUT_DIR / "taxonomy_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
