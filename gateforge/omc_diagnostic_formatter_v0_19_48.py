"""OMC diagnostic output formatter for v0.19.48.

Reformats raw OpenModelica compiler output into a structured, noise-reduced
summary that is easier for an LLM to consume. This is purely a presentation-layer
adapter — no semantic inference, no root-cause analysis, no system-side hints.

Input: raw OMC checkModel + simulate output text
Output: structured diagnostic excerpt
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class UndersolvedVariable:
    """A variable that OMC reports as having no remaining equation."""
    name: str
    line_info: str = ""          # e.g. "6:3-6:40" or "line 6"
    equations: list[str] = field(default_factory=list)


def _extract_eq_var_counts(omc_text: str) -> tuple[int | None, int | None]:
    """Parse equation and variable counts from OMC checkModel output."""
    m = re.search(r"has\s+(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)", omc_text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _extract_trivial_eq_count(omc_text: str) -> int | None:
    """Parse 'N of these are trivial equation(s)'."""
    m = re.search(r"(\d+)\s+of\s+these\s+are\s+trivial\s+equation\(s\)", omc_text)
    if m:
        return int(m.group(1))
    return None


def _strip_file_path(path_line: str) -> str:
    """Convert '/workspace/Model.mo:6:3-6:40:writable' to 'line 6'."""
    # Extract the line number after the last '/' and before first ':'
    m = re.search(r":(\d+):\d+-\d+:\d+:writable", path_line)
    if m:
        return f"line {m.group(1)}"
    # Fallback: just extract first number after final slash
    m = re.search(r"/([^/]+):(\d+)", path_line)
    if m:
        return f"line {m.group(2)}"
    return ""


def _extract_undersolved_variables(omc_text: str) -> list[UndersolvedVariable]:
    """Parse all 'Variable X does not have any remaining equation' warnings."""
    variables: list[UndersolvedVariable] = []

    # Match the path prefix before the warning, then the warning block.
    # Each block starts with: [/workspace/...:writable] Warning: Variable X ...
    warning_pattern = re.compile(
        r"(\[/workspace/[^\]]+:\w+\])\s+Warning:\s+Variable\s+(\w+)\s+does\s+not\s+have\s+any\s+remaining\s+equation\s+to\s+be\s+solved\s+in\.\n"
        r"\s+The\s+original\s+equations\s+were:\n"
        r"((?:\s+Equation\s+\d+:[^\n]*\n)+)",
        re.MULTILINE,
    )

    for m in warning_pattern.finditer(omc_text):
        path_line = m.group(1)
        var_name = m.group(2)
        eq_block = m.group(3)

        line_info = _strip_file_path(path_line)

        # Parse equation lines
        equations = []
        for eq_m in re.finditer(r"Equation\s+\d+:\s+(.+?)(?:,\s+which needs to solve for\s+\w+)?\s*$", eq_block, re.MULTILINE):
            eq_text = eq_m.group(1).strip()
            equations.append(eq_text)

        variables.append(UndersolvedVariable(
            name=var_name,
            line_info=line_info,
            equations=equations,
        ))

    return variables


def _extract_main_error(omc_text: str) -> str:
    """Extract the primary error message (e.g. 'Too few equations')."""
    # Look for Error: at the start of a line (OMC typically outputs this way)
    m = re.search(r'^Error:\s+(.+?)$', omc_text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # Fallback: look anywhere
    m = re.search(r"Error:\s+(.+?)(?:\n|$)", omc_text)
    if m:
        return m.group(1).strip()
    return ""


def format_omc_error_excerpt(omc_text: str) -> str:
    """Reformat raw OMC output into a structured, noise-reduced diagnostic summary.

    This function performs ONLY structural reformatting:
    - Extracts and surfaces key numeric facts (eq count, var count, deficit)
    - Groups warnings by variable
    - Removes file paths and other LLM-irrelevant noise
    - Preserves all original semantic content

    It does NOT:
    - Interpret why a variable lacks an equation
    - Suggest what repair to make
    - Add information not present in the original OMC output
    """
    if not omc_text or not omc_text.strip():
        return ""

    eq_count, var_count = _extract_eq_var_counts(omc_text)
    trivial_count = _extract_trivial_eq_count(omc_text)
    main_error = _extract_main_error(omc_text)
    undersolved = _extract_undersolved_variables(omc_text)

    lines: list[str] = []

    # Header: model structure
    lines.append("=== MODEL STRUCTURE ===")
    if eq_count is not None and var_count is not None:
        lines.append(f"Equations: {eq_count}")
        lines.append(f"Variables: {var_count}")
        if trivial_count is not None:
            lines.append(f"Trivial equations: {trivial_count}")
        deficit = var_count - eq_count
        if deficit > 0:
            lines.append(f"Deficit: {deficit} variables lack equations")
    else:
        lines.append("(Could not parse equation/variable counts)")

    lines.append("")

    # Main error
    if main_error:
        lines.append(f"Error: {main_error}")
        lines.append("")

    # Undersolved variables grouped
    if undersolved:
        lines.append(f"=== VARIABLES WITHOUT EQUATIONS ({len(undersolved)}) ===")
        for i, uv in enumerate(undersolved, 1):
            location = f" ({uv.line_info})" if uv.line_info else ""
            lines.append(f"{i}. {uv.name}{location}")
            for eq in uv.equations:
                lines.append(f"   Referenced in: {eq}")
        # Note if OMC did not report all deficit variables
        if eq_count is not None and var_count is not None:
            deficit = var_count - eq_count
            if deficit > len(undersolved):
                missing = deficit - len(undersolved)
                lines.append(f"   (Note: OMC reports deficit of {deficit} but only flagged {len(undersolved)} variables;")
                lines.append(f"    {missing} additional variable(s) may also lack equations)")
        lines.append("")
    else:
        if eq_count is not None and var_count is not None:
            deficit = var_count - eq_count
            if deficit > 0:
                lines.append(f"=== NO VARIABLES EXPLICITLY FLAGGED AS MISSING EQUATIONS ===")
                lines.append(f"   (Note: deficit is {deficit} but OMC did not list specific variables)")
            else:
                lines.append("=== NO VARIABLES FLAGGED AS MISSING EQUATIONS ===")
        else:
            lines.append("=== NO VARIABLES FLAGGED AS MISSING EQUATIONS ===")
        lines.append("")

    return "\n".join(lines)


def format_omc_error_excerpt_compact(omc_text: str) -> str:
    """Compact variant: single-line variable list + deficit, for tight prompt budgets."""
    eq_count, var_count = _extract_eq_var_counts(omc_text)
    undersolved = _extract_undersolved_variables(omc_text)

    parts: list[str] = []
    if eq_count is not None and var_count is not None:
        deficit = var_count - eq_count
        parts.append(f"Eq={eq_count}, Var={var_count}, Deficit={deficit}")

    if undersolved:
        var_names = ", ".join(uv.name for uv in undersolved)
        parts.append(f"No-equation vars: {var_names}")

    return "; ".join(parts) if parts else ""
