from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_COMPARE_KEYS = [
    "status",
    "best_profile",
    "best_decision",
    "best_reason",
    "best_total_score",
    "top_score_margin",
    "min_top_score_margin",
    "constraint_reason",
    "decision_explanation_score",
    "recommended_profile",
    "recommended_profile_decision",
    "require_recommended_eligible",
    "scoring",
]

DEFAULT_APPLY_KEYS = [
    "final_status",
    "apply_action",
    "best_profile",
    "best_decision",
    "recommended_profile",
    "policy_profile",
    "policy_version",
    "policy_hash",
    "effective_guardrails_hash",
    "require_ranking_explanation",
    "require_min_top_score_margin",
    "require_min_explanation_quality",
    "require_ranking_explanation_structure",
    "strict_ranking_explanation_structure",
    "strict_guardrail_drift",
    "guardrail_drift_detected",
]


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_jsonl(path: str, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return int(proc.returncode), proc.stdout or "", proc.stderr or ""


def _append_mismatch(mismatches: list[dict], code: str, *, expected: object, actual: object) -> None:
    mismatches.append({"code": code, "expected": expected, "actual": actual})


def _compare_key(
    mismatches: list[dict],
    *,
    domain: str,
    key: str,
    expected_payload: dict,
    actual_payload: dict,
) -> None:
    expected = expected_payload.get(key)
    actual = actual_payload.get(key)
    if expected != actual:
        _append_mismatch(
            mismatches,
            f"{domain}_{key}_mismatch",
            expected=expected,
            actual=actual,
        )


def _parse_keys_csv(raw: str | None) -> list[str]:
    if not isinstance(raw, str) or not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_reasons(payload: dict, key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return sorted(str(item) for item in value)


def _compare_compare_summary(mismatches: list[dict], source: dict, replayed: dict, keys: list[str]) -> None:
    for key in keys:
        _compare_key(mismatches, domain="compare", key=key, expected_payload=source, actual_payload=replayed)


def _compare_apply_summary(mismatches: list[dict], source: dict, replayed: dict, keys: list[str]) -> None:
    for key in keys:
        _compare_key(mismatches, domain="apply", key=key, expected_payload=source, actual_payload=replayed)

    expected_reasons = _normalize_reasons(source, "reasons")
    actual_reasons = _normalize_reasons(replayed, "reasons")
    if expected_reasons != actual_reasons:
        _append_mismatch(
            mismatches,
            "apply_reasons_mismatch",
            expected=expected_reasons,
            actual=actual_reasons,
        )


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Replay",
        "",
        f"- decision: `{summary.get('decision')}`",
        f"- strict: `{summary.get('strict')}`",
        f"- source_compare_summary_path: `{summary.get('source_compare_summary_path')}`",
        f"- source_apply_summary_path: `{summary.get('source_apply_summary_path')}`",
        f"- replay_compare_summary_path: `{summary.get('replay_compare_summary_path')}`",
        f"- replay_apply_summary_path: `{summary.get('replay_apply_summary_path')}`",
        f"- compare_exit_code: `{summary.get('compare_exit_code')}`",
        f"- apply_exit_code: `{summary.get('apply_exit_code')}`",
        f"- compare_keys: `{','.join(summary.get('compare_keys') or [])}`",
        f"- apply_keys: `{','.join(summary.get('apply_keys') or [])}`",
        f"- ignore_compare_keys: `{','.join(summary.get('ignore_compare_keys') or [])}`",
        f"- ignore_apply_keys: `{','.join(summary.get('ignore_apply_keys') or [])}`",
        "",
        "## Mismatches",
        "",
    ]
    mismatches = summary.get("mismatches", [])
    if isinstance(mismatches, list) and mismatches:
        for item in mismatches:
            lines.append(
                f"- `{item.get('code')}` expected=`{item.get('expected')}` actual=`{item.get('actual')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay governance compare/apply and verify decision consistency")
    parser.add_argument("--compare-summary", required=True, help="Source governance_promote_compare summary JSON")
    parser.add_argument("--apply-summary", required=True, help="Source governance_promote_apply summary JSON")
    parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled, any mismatch is FAIL (otherwise NEEDS_REVIEW)",
    )
    parser.add_argument(
        "--compare-keys",
        default=None,
        help="Comma-separated compare summary keys to validate (default built-in keyset)",
    )
    parser.add_argument(
        "--apply-keys",
        default=None,
        help="Comma-separated apply summary keys to validate (default built-in keyset)",
    )
    parser.add_argument(
        "--ignore-compare-key",
        action="append",
        default=[],
        help="Compare summary key to ignore (repeatable)",
    )
    parser.add_argument(
        "--ignore-apply-key",
        action="append",
        default=[],
        help="Apply summary key to ignore (repeatable)",
    )
    parser.add_argument(
        "--ledger",
        default=None,
        help="Optional JSONL path to append replay result rows",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Optional short tag recorded in replay ledger row",
    )
    parser.add_argument("--out", default="artifacts/governance_replay/summary.json", help="Replay summary output JSON")
    parser.add_argument("--report", default=None, help="Replay summary markdown path")
    args = parser.parse_args()

    source_compare = _load_json(args.compare_summary)
    source_apply = _load_json(args.apply_summary)
    mismatches: list[dict] = []
    compare_keys = _parse_keys_csv(args.compare_keys) or list(DEFAULT_COMPARE_KEYS)
    apply_keys = _parse_keys_csv(args.apply_keys) or list(DEFAULT_APPLY_KEYS)
    ignore_compare = {str(k) for k in (args.ignore_compare_key or [])}
    ignore_apply = {str(k) for k in (args.ignore_apply_key or [])}
    compare_keys = [key for key in compare_keys if key not in ignore_compare]
    apply_keys = [key for key in apply_keys if key not in ignore_apply]

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        replay_compare_path = root / "replay_compare.json"
        replay_apply_path = root / "replay_apply.json"

        profiles = [str(row.get("profile")) for row in (source_compare.get("profile_results") or []) if row.get("profile")]
        if not profiles:
            _append_mismatch(mismatches, "compare_profiles_missing", expected="non-empty", actual=profiles)
            replay_compare = {}
            compare_rc = -1
        else:
            compare_cmd = [
                sys.executable,
                "-m",
                "gateforge.governance_promote_compare",
                "--snapshot",
                str(source_compare.get("snapshot_path")),
                "--profiles",
                *profiles,
                "--score-decision-weight",
                str((source_compare.get("scoring") or {}).get("decision_weight", 100)),
                "--score-exit-penalty",
                str((source_compare.get("scoring") or {}).get("exit_penalty", 5)),
                "--score-reason-penalty",
                str((source_compare.get("scoring") or {}).get("reason_penalty", 1)),
                "--score-recommended-bonus",
                str((source_compare.get("scoring") or {}).get("recommended_bonus", 3)),
                "--min-top-score-margin",
                str(source_compare.get("min_top_score_margin", 0)),
                "--out",
                str(replay_compare_path),
            ]
            if source_compare.get("override_map_path"):
                compare_cmd.extend(["--override-map", str(source_compare.get("override_map_path"))])
            if bool(source_compare.get("require_recommended_eligible")):
                compare_cmd.append("--require-recommended-eligible")

            compare_rc, _, _ = _run(compare_cmd)
            replay_compare = _load_json(str(replay_compare_path)) if replay_compare_path.exists() else {}

        expected_compare_rc = 1 if str(source_compare.get("status", "")).upper() == "FAIL" else 0
        if compare_rc != expected_compare_rc:
            _append_mismatch(
                mismatches,
                "compare_exit_code_mismatch",
                expected=expected_compare_rc,
                actual=compare_rc,
            )
        if replay_compare:
            _compare_compare_summary(mismatches, source_compare, replay_compare, compare_keys)

        apply_cmd = [
            sys.executable,
            "-m",
            "gateforge.governance_promote_apply",
            "--compare-summary",
            str(replay_compare_path),
            "--policy-profile",
            str(source_apply.get("policy_profile") or "default"),
            "--actor",
            str(source_apply.get("actor") or "governance.bot"),
            "--out",
            str(replay_apply_path),
        ]
        if source_apply.get("review_ticket_id"):
            apply_cmd.extend(["--review-ticket-id", str(source_apply.get("review_ticket_id"))])
        if source_apply.get("require_ranking_explanation") is True:
            apply_cmd.append("--require-ranking-explanation")
        if isinstance(source_apply.get("require_min_top_score_margin"), int):
            apply_cmd.extend(
                ["--require-min-top-score-margin", str(source_apply.get("require_min_top_score_margin"))]
            )
        if isinstance(source_apply.get("require_min_explanation_quality"), int):
            apply_cmd.extend(
                ["--require-min-explanation-quality", str(source_apply.get("require_min_explanation_quality"))]
            )
        if source_apply.get("require_ranking_explanation_structure") is True:
            apply_cmd.append("--require-ranking-explanation-structure")
        if source_apply.get("strict_ranking_explanation_structure") is True:
            apply_cmd.append("--strict-ranking-explanation-structure")
        if source_apply.get("strict_guardrail_drift") is True:
            apply_cmd.append("--strict-guardrail-drift")

        apply_rc, _, _ = _run(apply_cmd)
        replay_apply = _load_json(str(replay_apply_path)) if replay_apply_path.exists() else {}
        expected_apply_rc = 1 if str(source_apply.get("final_status", "")).upper() == "FAIL" else 0
        if apply_rc != expected_apply_rc:
            _append_mismatch(
                mismatches,
                "apply_exit_code_mismatch",
                expected=expected_apply_rc,
                actual=apply_rc,
            )
        if replay_apply:
            _compare_apply_summary(mismatches, source_apply, replay_apply, apply_keys)

        decision = "PASS"
        if mismatches:
            decision = "FAIL" if args.strict else "NEEDS_REVIEW"
        summary = {
            "decision": decision,
            "strict": bool(args.strict),
            "source_compare_summary_path": args.compare_summary,
            "source_apply_summary_path": args.apply_summary,
            "replay_compare_summary_path": str(replay_compare_path),
            "replay_apply_summary_path": str(replay_apply_path),
            "compare_exit_code": compare_rc,
            "apply_exit_code": apply_rc,
            "compare_keys": compare_keys,
            "apply_keys": apply_keys,
            "ignore_compare_keys": sorted(ignore_compare),
            "ignore_apply_keys": sorted(ignore_apply),
            "mismatches": mismatches,
        }

    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    if args.ledger:
        row = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "tag": args.tag,
            "decision": summary.get("decision"),
            "strict": summary.get("strict"),
            "source_compare_summary_path": summary.get("source_compare_summary_path"),
            "source_apply_summary_path": summary.get("source_apply_summary_path"),
            "compare_exit_code": summary.get("compare_exit_code"),
            "apply_exit_code": summary.get("apply_exit_code"),
            "mismatch_count": len(summary.get("mismatches", [])),
            "mismatches": summary.get("mismatches", []),
            "compare_keys": summary.get("compare_keys", []),
            "apply_keys": summary.get("apply_keys", []),
            "ignore_compare_keys": summary.get("ignore_compare_keys", []),
            "ignore_apply_keys": summary.get("ignore_apply_keys", []),
            "summary_path": args.out,
        }
        _append_jsonl(args.ledger, row)
    print(json.dumps({"decision": summary["decision"], "mismatch_count": len(summary["mismatches"])}))
    if summary["decision"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
