from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Pack Compare",
        "",
        f"- decision: `{payload.get('decision')}`",
        f"- baseline_pack_id: `{payload.get('baseline_pack_id')}`",
        f"- candidate_pack_id: `{payload.get('candidate_pack_id')}`",
        f"- baseline_match_rate: `{payload.get('baseline_match_rate')}`",
        f"- candidate_match_rate: `{payload.get('candidate_match_rate')}`",
        f"- delta_match_rate: `{payload.get('delta_match_rate')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        for r in reasons:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare mutation pack metrics between baseline and candidate")
    parser.add_argument("--baseline", required=True, help="Baseline metrics JSON")
    parser.add_argument("--candidate", required=True, help="Candidate metrics JSON")
    parser.add_argument("--out", default="artifacts/mutation_pack_compare/summary.json", help="Summary JSON output")
    parser.add_argument("--report-out", default=None, help="Summary markdown output")
    args = parser.parse_args()

    baseline = _load_json(args.baseline)
    candidate = _load_json(args.candidate)

    base_rate = float(baseline.get("expected_vs_actual_match_rate", 0.0) or 0.0)
    cand_rate = float(candidate.get("expected_vs_actual_match_rate", 0.0) or 0.0)
    delta = round(cand_rate - base_rate, 4)

    reasons: list[str] = []
    decision = "PASS"
    if cand_rate < base_rate:
        decision = "FAIL"
        reasons.append("expected_vs_actual_match_rate_regressed")
    elif cand_rate > base_rate:
        reasons.append("expected_vs_actual_match_rate_improved")
    else:
        reasons.append("expected_vs_actual_match_rate_unchanged")

    payload = {
        "decision": decision,
        "baseline_pack_id": baseline.get("pack_id"),
        "candidate_pack_id": candidate.get("pack_id"),
        "baseline_match_rate": base_rate,
        "candidate_match_rate": cand_rate,
        "delta_match_rate": delta,
        "reasons": reasons,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"decision": decision, "delta_match_rate": delta}))
    if decision != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
