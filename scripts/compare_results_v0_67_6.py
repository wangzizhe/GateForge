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


def load_external_agent_results(dirpath: Path) -> dict[str, dict[str, Any]]:
    """Load external agent results from a directory of .json files."""
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
        cid = row.get("case_id", row.get("task", ""))
        verdict = str(row.get("final_verdict", row.get("status", ""))).upper()
        if "PASS" in verdict:
            row["final_verdict"] = "PASS"
        elif "FAIL" in verdict:
            row["final_verdict"] = "FAIL"
        else:
            row["final_verdict"] = verdict
        if cid:
            results[cid] = row
    return results


def format_verdict(v: str) -> str:
    if v == "PASS":
        return "PASS"
    if "TIMEOUT" in v or "INTERRUPTED" in v:
        return "FAIL"
    return "FAIL"


def generate_comparison(
    gf: dict[str, dict[str, Any]],
    oc: dict[str, dict[str, Any]],
) -> str:
    lines: list[str] = []
    all_cases = sorted(set(gf.keys()) | set(oc.keys()))

    lines.append("# GateForge vs External Agent Comparison Report")
    lines.append("")
    lines.append("| Case | GateForge | Ext Agent | Δ | GF OMC | Ext OMC | Notes |")
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
            delta = "← Ext"
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
        elif delta == "← Ext":
            oc_notes = oc_row.get("notes", "")[:80]
            notes = oc_notes if oc_notes else ""
        elif delta == "✗":
            notes = "both FAIL"
        elif delta == "GF →" and "TIMEOUT" in str(oc_row.get("final_verdict", "")):
            notes = "ext agent interrupted"
        elif delta == "GF →" and "INTERRUPTED" in str(oc_row.get("final_verdict", "")):
            notes = "ext agent interrupted"

        if gv == "PASS":
            gf_pass += 1
        if ov == "PASS":
            oc_pass += 1

        lines.append(f"| {cid} | {gv} | {ov} | {delta} | {gf_omc} | {oc_omc} | {notes} |")

    lines.append("")
    timeout_count = sum(1 for cid, oc_row in oc.items() 
                        if "TIMEOUT" in str(oc_row.get("final_verdict", "")).upper()
                        or "INTERRUPTED" in str(oc_row.get("final_verdict", "")).upper())
    lines.append(f"**GateForge**: {gf_pass}/{total} PASS")
    lines.append(f"**External Agent**: {oc_pass}/{total} PASS ({timeout_count} interrupted/FAIL within budget)")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare GateForge and external agent results.")
    parser.add_argument("--gateforge", type=Path, required=True,
                        help="Path to GateForge results.jsonl")
    parser.add_argument("--external-agent", type=Path, required=True,
                        help="Directory of external agent result .json files", dest="ext_dir")
    parser.add_argument("--out", type=Path, default=None,
                        help="Write markdown report to file")
    args = parser.parse_args()

    gf = load_gateforge_results(args.gateforge)
    oc = load_external_agent_results(args.ext_dir)

    if not gf:
        print(f"Warning: No GateForge results found in {args.gateforge}", file=sys.stderr)
    if not oc:
        print(f"Warning: No external agent results found in {args.ext_dir}", file=sys.stderr)

    report = generate_comparison(gf, oc)
    if args.out:
        args.out.write_text(report + "\n", encoding="utf-8")
        print(f"Report written to {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
