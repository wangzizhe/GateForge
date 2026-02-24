from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def _run_compare(snapshot: str, min_margin: int, out_dir: Path, out_path: Path, report_path: Path) -> tuple[int, dict]:
    cmd = [
        sys.executable,
        "-m",
        "gateforge.governance_promote_compare",
        "--snapshot",
        snapshot,
        "--profiles",
        "default",
        "industrial_strict",
        "--min-top-score-margin",
        str(int(min_margin)),
        "--out-dir",
        str(out_dir),
        "--out",
        str(out_path),
        "--report",
        str(report_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload = _load_json(str(out_path)) if out_path.exists() else {}
    return int(proc.returncode), payload


def _run_apply(compare_summary: Path, policy_profile: str, out_path: Path, report_path: Path, audit_path: Path) -> tuple[int, dict]:
    compare_payload = _load_json(str(compare_summary)) if compare_summary.exists() else {}
    status = str(compare_payload.get("status") or "")
    cmd = [
        sys.executable,
        "-m",
        "gateforge.governance_promote_apply",
        "--compare-summary",
        str(compare_summary),
        "--policy-profile",
        policy_profile,
        "--actor",
        "autotune.bot",
        "--out",
        str(out_path),
        "--report",
        str(report_path),
        "--audit",
        str(audit_path),
    ]
    if status.upper() == "NEEDS_REVIEW":
        cmd.extend(["--review-ticket-id", "AUTO-TUNE-REVIEW-001"])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload = _load_json(str(out_path)) if out_path.exists() else {}
    return int(proc.returncode), payload


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline = payload.get("baseline", {})
    tuned = payload.get("tuned", {})
    lines = [
        "# GateForge Policy Auto-Tune Promote Flow",
        "",
        f"- advisor_profile: `{payload.get('advisor_profile')}`",
        f"- baseline_compare_status: `{baseline.get('compare_status')}`",
        f"- baseline_apply_status: `{baseline.get('apply_status')}`",
        f"- tuned_compare_status: `{tuned.get('compare_status')}`",
        f"- tuned_apply_status: `{tuned.get('apply_status')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run baseline vs autotuned promote compare/apply flow")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--advisor", required=True)
    parser.add_argument("--out-dir", default="artifacts/policy_autotune_governance")
    parser.add_argument("--out", default=None)
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_out = Path(args.out) if args.out else out_dir / "flow_summary.json"
    report_out = Path(args.report) if args.report else Path(_default_md_path(str(summary_out)))

    advisor = _load_json(args.advisor)
    advice = advisor.get("advice") if isinstance(advisor.get("advice"), dict) else {}
    patch = advice.get("threshold_patch") if isinstance(advice.get("threshold_patch"), dict) else {}
    advisor_profile = str(advice.get("suggested_policy_profile") or "default")
    if advisor_profile not in {"default", "industrial_strict"}:
        advisor_profile = "default"
    tuned_min_margin = patch.get("require_min_top_score_margin")
    if not isinstance(tuned_min_margin, int):
        tuned_min_margin = 0

    baseline_compare_out = out_dir / "baseline_compare.json"
    baseline_compare_report = out_dir / "baseline_compare.md"
    baseline_compare_dir = out_dir / "baseline_compare_profiles"
    baseline_compare_rc, baseline_compare = _run_compare(
        args.snapshot,
        min_margin=0,
        out_dir=baseline_compare_dir,
        out_path=baseline_compare_out,
        report_path=baseline_compare_report,
    )

    baseline_apply_out = out_dir / "baseline_apply.json"
    baseline_apply_report = out_dir / "baseline_apply.md"
    baseline_apply_audit = out_dir / "baseline_apply_audit.jsonl"
    baseline_apply_rc, baseline_apply = _run_apply(
        baseline_compare_out,
        policy_profile="default",
        out_path=baseline_apply_out,
        report_path=baseline_apply_report,
        audit_path=baseline_apply_audit,
    )

    tuned_compare_out = out_dir / "tuned_compare.json"
    tuned_compare_report = out_dir / "tuned_compare.md"
    tuned_compare_dir = out_dir / "tuned_compare_profiles"
    tuned_compare_rc, tuned_compare = _run_compare(
        args.snapshot,
        min_margin=tuned_min_margin,
        out_dir=tuned_compare_dir,
        out_path=tuned_compare_out,
        report_path=tuned_compare_report,
    )

    tuned_apply_out = out_dir / "tuned_apply.json"
    tuned_apply_report = out_dir / "tuned_apply.md"
    tuned_apply_audit = out_dir / "tuned_apply_audit.jsonl"
    tuned_apply_rc, tuned_apply = _run_apply(
        tuned_compare_out,
        policy_profile=advisor_profile,
        out_path=tuned_apply_out,
        report_path=tuned_apply_report,
        audit_path=tuned_apply_audit,
    )

    payload = {
        "snapshot_path": args.snapshot,
        "advisor_path": args.advisor,
        "advisor_profile": advisor_profile,
        "advisor_min_top_score_margin": tuned_min_margin,
        "baseline": {
            "compare_rc": baseline_compare_rc,
            "compare_status": baseline_compare.get("status"),
            "compare_path": str(baseline_compare_out),
            "apply_rc": baseline_apply_rc,
            "apply_status": baseline_apply.get("final_status"),
            "apply_path": str(baseline_apply_out),
        },
        "tuned": {
            "compare_rc": tuned_compare_rc,
            "compare_status": tuned_compare.get("status"),
            "compare_path": str(tuned_compare_out),
            "apply_rc": tuned_apply_rc,
            "apply_status": tuned_apply.get("final_status"),
            "apply_path": str(tuned_apply_out),
        },
    }
    _write_json(str(summary_out), payload)
    _write_markdown(str(report_out), payload)
    print(
        json.dumps(
            {
                "advisor_profile": advisor_profile,
                "baseline_apply_status": payload["baseline"].get("apply_status"),
                "tuned_apply_status": payload["tuned"].get("apply_status"),
            }
        )
    )


if __name__ == "__main__":
    main()
