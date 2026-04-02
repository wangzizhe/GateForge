from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Dual-cap context truncation utility
#
# Trims any text string before it is injected into an LLM prompt, preventing
# silent prompt inflation from large structured context blocks (multistep
# memory, planner experience context, external agent briefs, etc.).
#
# Two independent caps are applied in order — whichever fires first wins:
#   1. Line cap  — natural human-readable boundary; truncates at a line edge
#   2. Byte cap  — encoding safety; truncates at the last newline before the cap
#
# When truncated, a one-line warning is appended so the model knows content
# was omitted.  The warning itself is kept short and never truncated.
# ---------------------------------------------------------------------------

LINE_CAP_DEFAULT = 200
BYTE_CAP_DEFAULT = 20_000

_REASON_NONE = "none"
_REASON_LINE = "line_cap"
_REASON_BYTE = "byte_cap"


@dataclass(frozen=True)
class TruncationResult:
    """Immutable result of a dual-cap truncation operation."""

    text: str               # final text ready for prompt injection
    was_truncated: bool
    truncation_reason: str  # "none" | "line_cap" | "byte_cap"
    original_line_count: int
    original_byte_count: int
    final_line_count: int
    final_byte_count: int

    def summary(self) -> dict:
        return {
            "was_truncated": self.was_truncated,
            "truncation_reason": self.truncation_reason,
            "original_line_count": self.original_line_count,
            "original_byte_count": self.original_byte_count,
            "final_line_count": self.final_line_count,
            "final_byte_count": self.final_byte_count,
        }


def truncate_context(
    text: str,
    *,
    max_lines: int = LINE_CAP_DEFAULT,
    max_bytes: int = BYTE_CAP_DEFAULT,
    label: str = "context",
) -> TruncationResult:
    """Apply dual-cap truncation to *text* and return a TruncationResult.

    Parameters
    ----------
    text:
        The raw context string to truncate.
    max_lines:
        Maximum number of lines to retain.  Default: 200.
    max_bytes:
        Maximum byte length of the returned text (UTF-8).  Default: 20,000.
        Truncation happens at the last newline before this limit so no line
        is split mid-way.
    label:
        Short name used in the appended warning (e.g. "planner_context",
        "multistep_memory").  Helps the model identify which block was cut.
    """
    raw = str(text or "")
    lines = raw.splitlines()

    original_line_count = len(lines)
    original_byte_count = len(raw.encode("utf-8"))

    # --- Step 1: line cap ------------------------------------------------
    reason = _REASON_NONE
    if len(lines) > max_lines:
        omitted = len(lines) - max_lines
        lines = lines[:max_lines]
        warning = (
            f"[{label}: line_cap reached — {omitted} line(s) omitted "
            f"(max_lines={max_lines})]"
        )
        lines.append(warning)
        reason = _REASON_LINE

    result_text = "\n".join(lines)

    # --- Step 2: byte cap ------------------------------------------------
    encoded = result_text.encode("utf-8")
    if len(encoded) > max_bytes:
        # Truncate at the last newline before the byte limit so we never
        # split a multi-byte character or leave a half-line.
        truncated_bytes = encoded[:max_bytes]
        # Find the last newline within the truncated byte slice
        last_nl = truncated_bytes.rfind(b"\n")
        if last_nl > 0:
            truncated_bytes = truncated_bytes[:last_nl]
        safe_text = truncated_bytes.decode("utf-8", errors="replace")

        original_bytes_for_warning = original_byte_count if reason == _REASON_NONE else len(result_text.encode("utf-8"))
        omitted_bytes = original_bytes_for_warning - len(truncated_bytes)
        warning = (
            f"[{label}: byte_cap reached — ~{omitted_bytes} byte(s) omitted "
            f"(max_bytes={max_bytes})]"
        )
        result_text = safe_text.rstrip("\n") + "\n" + warning
        reason = _REASON_BYTE

    final_lines = result_text.splitlines()
    final_line_count = len(final_lines)
    final_byte_count = len(result_text.encode("utf-8"))

    return TruncationResult(
        text=result_text,
        was_truncated=(reason != _REASON_NONE),
        truncation_reason=reason,
        original_line_count=original_line_count,
        original_byte_count=original_byte_count,
        final_line_count=final_line_count,
        final_byte_count=final_byte_count,
    )


def truncate_context_text(
    text: str,
    *,
    max_lines: int = LINE_CAP_DEFAULT,
    max_bytes: int = BYTE_CAP_DEFAULT,
    label: str = "context",
) -> str:
    """Convenience wrapper — returns the truncated string directly.

    Use when you only need the text and not the full TruncationResult metadata.
    """
    return truncate_context(text, max_lines=max_lines, max_bytes=max_bytes, label=label).text


def needs_truncation(
    text: str,
    *,
    max_lines: int = LINE_CAP_DEFAULT,
    max_bytes: int = BYTE_CAP_DEFAULT,
) -> bool:
    """Return True if *text* would be truncated under the given caps.

    Useful for a pre-check when building context blocks, to decide whether
    to spend time constructing the full string before truncating it.
    """
    raw = str(text or "")
    if len(raw.splitlines()) > max_lines:
        return True
    if len(raw.encode("utf-8")) > max_bytes:
        return True
    return False
