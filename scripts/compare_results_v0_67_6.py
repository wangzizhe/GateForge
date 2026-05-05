from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_gateforge_results(path: Path) -> dict[str, dict[str, Any]]:
    """Load GateForge results from a results.jsonl file."""
    results: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return results
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cid = row.get("case_id", "")
        if cid:
            results[cid] = row
    return results


def load_opencode_results(dirpath: Path) -> dict[str, dict[str, Any]]:
    """Load OpenCode results from a directory of .json files."""
    results: dict[str, dict[str, Any]] = {}
    if not dirpath.exists():
        return results
    for path in sorted(dirpath.glob("*.json")):
        # Skip trajectory files
        if "trajectory" in path.name:
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        cid = row.get("case_id", "")
        if cid:
            results[cid] = row
    return results


def format_verdict(v: str) -> str:
    if v == "PASS":
        return "PASS"
    return "FAIL"


def generate_comparison(
    gf: dict[str, dict[str, Any]],
    oc: dict[str, dict[str, Any]],
) -> str:
    lines: list[str] = []
    all_cases = sorted(set(gf.keys()) | set(oc.keys()))

    lines.append("# GateForge vs OpenCode Comparison Report")
    lines.append("")
    lines.append("| Case | GateForge | OpenCode | Δ | GF OMC | OC OMC | Notes |")
    lines.append("|------|-----------|----------|---|--------|--------|-------|")

    gf_pass = 0
    oc_pass = 0
    total = len(all_cases)

    for cid in all_cases:
        gf_row = gf.get(cid, {})
        oc_row = oc.get(cid, {})
        gv = format_verdict(gf_row.get("final_verdict", "?"))
        ov = format_verdict(oc_row.get("final_verdict", "?"))
        gf_omc = gf_row.get("step_count", "—")
        oc_omc = oc_row.get("omc_invocation_count", "—")

        if gv == "?":
            gv = "—"
        if ov == "?":
            ov = "—"

        if gv == "PASS" and ov == "PASS":
            delta = "="
        elif gv == "FAIL" and ov == "PASS":
            delta = "← OC"
        elif gv == "PASS" and ov == "FAIL":
            delta = "GF →"
        elif gv == "FAIL" and ov == "FAIL":
            delta = "✗"
        elif gv == "—" or ov == "—":
            delta = "—"
        else:
            delta = "?"

        notes = ""
        if delta == "—" and ov == "—":
            notes = "not tested"
        elif delta == "← OC":
            oc_notes = oc_row.get("notes", "")[:80]
            notes = oc_notes if oc_notes else ""
        elif delta == "✗":
            notes = "both FAIL"

        if gv == "PASS":
            gf_pass += 1
        if ov == "PASS":
            oc_pass += 1

        lines.append(f"| {cid} | {gv} | {ov} | {delta} | {gf_omc} | {oc_omc} | {notes} |")

    lines.append("")
    oc_tested = len(oc)
    lines.append(f"**GateForge**: {gf_pass}/{total} PASS")
    lines.append(f"**OpenCode**: {oc_pass}/{oc_tested} tested ({oc_pass}/{total} of all cases)")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare GateForge and OpenCode results.")
    parser.add_argument("--gateforge", type=Path, required=True,
                        help="Path to GateForge results.jsonl")
    parser.add_argument("--opencode", type=Path, required=True,
                        help="Directory of OpenCode result .json files")
    parser.add_argument("--out", type=Path, default=None,
                        help="Write markdown report to file")
    args = parser.parse_args()

    gf = load_gateforge_results(args.gateforge)
    oc = load_opencode_results(args.opencode)

    if not gf:
        print(f"Warning: No GateForge results found in {args.gateforge}", file=sys.stderr)
    if not oc:
        print(f"Warning: No OpenCode results found in {args.opencode}", file=sys.stderr)

    report = generate_comparison(gf, oc)
    if args.out:
        args.out.write_text(report + "\n", encoding="utf-8")
        print(f"Report written to {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
