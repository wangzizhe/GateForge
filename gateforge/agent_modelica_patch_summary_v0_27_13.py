from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "patch_summary_v0_27_13"

_VAR_DECL_RE = re.compile(
    r"^\s*(?:(?:input|output|protected|public|discrete|flow|stream)\s+)*"
    r"(Real|Integer|Boolean|String|parameter|constant)"
    r"(?:\s*\[[^\]]*\])?"
    r"\s+(\w+)",
    re.MULTILINE,
)

_COMPONENT_RE = re.compile(r"^\s*(\w+)\s+(\w+)\s*\(", re.MULTILINE)

_EQUATION_KW_RE = re.compile(r"^\s*((?:initial\s+)?equation)\s*$", re.MULTILINE)

_CONNECT_RE = re.compile(r"^\s*connect\s*\(.*\)\s*;", re.MULTILINE)

_FORBIDDEN_SUMMARY_TERMS = (
    "root_cause",
    "root cause",
    "repair_hint",
    "expected_fix",
    "target_patch",
    "deterministic_diagnosis",
    "routing_decision",
    "you should",
    "try fixing",
    "suggest",
    "recommend",
)


def _extract_model_name(text: str) -> str:
    m = re.search(r"^\s*model\s+(\w+)", text, re.MULTILINE)
    if m:
        return m.group(1)
    m = re.search(r"^\s*block\s+(\w+)", text, re.MULTILINE)
    if m:
        return m.group(1)
    return "model"


def _extract_structural_signature(text: str) -> dict[str, set[str]]:
    sig: dict[str, set[str]] = {
        "variables": set(),
        "components": set(),
        "equations": set(),
    }
    text_stripped = _strip_comments(text)
    for m in _VAR_DECL_RE.finditer(text_stripped):
        sig["variables"].add(f"{m.group(1)} {m.group(2)}")
    for m in _COMPONENT_RE.finditer(text_stripped):
        sig["components"].add(f"{m.group(1)} {m.group(2)}")
    pos = 0
    while pos < len(text_stripped):
        m_eq = _EQUATION_KW_RE.search(text_stripped, pos)
        if not m_eq:
            break
        eq_start = m_eq.end()
        eq_body = _extract_equation_body(text_stripped, eq_start)
        sig["equations"].add(eq_body.strip())
        pos = eq_start + len(eq_body)
    return sig


def _strip_comments(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_block_comment = False
    for line in lines:
        stripped = line.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue
        if stripped.startswith("//"):
            continue
        clean = re.sub(r"//.*$", "", line)
        out.append(clean)
    return "\n".join(out)


def _extract_equation_body(text: str, start: int) -> str:
    lines = text[start:].splitlines()
    body_lines: list[str] = []
    depth = 0
    for line in lines:
        stripped = line.strip()
        if not stripped and not body_lines:
            continue
        if re.match(r"^\s*(?:end\s+\w+\s*;|(?:(?:initial\s+)?equation)\s*$|algorithm\s*$|end\s+\w+\s*;)", line):
            break
        body_lines.append(stripped)
    return "; ".join(body_lines)


def generate_patch_summary(old_text: str, new_text: str) -> str:
    if old_text.strip() == new_text.strip():
        return "No structural changes detected."
    old_sig = _extract_structural_signature(old_text)
    new_sig = _extract_structural_signature(new_text)
    model_name = _extract_model_name(new_text) or "model"
    added_vars = new_sig["variables"] - old_sig["variables"]
    removed_vars = old_sig["variables"] - new_sig["variables"]
    added_comps = new_sig["components"] - old_sig["components"]
    removed_comps = old_sig["components"] - new_sig["components"]
    added_eqs = new_sig["equations"] - old_sig["equations"]
    removed_eqs = old_sig["equations"] - new_sig["equations"]
    changed = bool(added_vars or removed_vars or added_comps or removed_comps or added_eqs or removed_eqs)
    if not changed:
        return "No structural changes detected (text differs but signature unchanged)."
    lines = [f"Changed model: {model_name}"]
    for label, items in [
        ("Added variable", sorted(added_vars)),
        ("Removed variable", sorted(removed_vars)),
        ("Added component", sorted(added_comps)),
        ("Removed component", sorted(removed_comps)),
    ]:
        for item in items[:6]:
            lines.append(f"- {label}: {item}")
        if len(items) > 6:
            lines.append(f"- {label}: ... and {len(items) - 6} more")
    eq_labels = [
        ("Added equation", sorted(added_eqs)),
        ("Removed equation", sorted(removed_eqs)),
    ]
    for label, items in eq_labels:
        if items:
            count = len(items)
            if count <= 3:
                for item in items:
                    truncated = (item[:100] + "...") if len(item) > 100 else item
                    lines.append(f"- {label}: {truncated}")
            else:
                lines.append(f"- {label}: {count}")
    return "\n".join(lines)


def validate_patch_summary(summary: str) -> list[str]:
    errors: list[str] = []
    lowered = summary.lower()
    for term in _FORBIDDEN_SUMMARY_TERMS:
        if term.lower() in lowered:
            errors.append(f"forbidden:{term}")
    return errors


def build_patch_summary_contract_summary(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    old_text = "model Demo\n  Real x;\nequation\n  x = 0;\nend Demo;"
    new_text = "model Demo\n  Real x;\n  Real y;\nequation\n  x = y;\n  y = 0;\nend Demo;"
    summary_text = generate_patch_summary(old_text, new_text)
    no_change_text = generate_patch_summary(old_text, old_text)
    validation_errors = validate_patch_summary(summary_text)
    summary = {
        "version": "v0.27.13",
        "status": "PASS" if not validation_errors else "REVIEW",
        "analysis_scope": "patch_summary_contract",
        "contract_scope": "descriptive_structural_diff_only",
        "validation_errors": validation_errors,
        "canonical_summary": summary_text,
        "no_change_summary": no_change_text,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "hint_terms_found": len(validation_errors) > 0,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "patch_summary_contract_ready"
            if not validation_errors
            else "patch_summary_contract_needs_review"
        ),
        "next_focus": "integrate_into_harness_repair_history_and_observation",
    }
    write_outputs(out_dir=out_dir, summary=summary, canonical_summary=summary_text)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], canonical_summary: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "canonical_summary.txt").write_text(canonical_summary + "\n", encoding="utf-8")
