from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_12_one_shot_classifier"
CLASSIFIER_VERSION = "v0_3_12_one_shot_classifier_v1"
DEFAULT_REFRESHED_SUMMARY = "artifacts/agent_modelica_same_branch_continuity_candidate_refresh_v0_3_10_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_12_one_shot_classifier"
SUCCESS_LABELS = (
    "one_shot",
    "unknown",
    "true_continuity",
    "multi_step_non_continuity",
)
ALL_LABELS = SUCCESS_LABELS + ("failed_or_unresolved",)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _item_id(row: dict) -> str:
    return str(row.get("task_id") or row.get("item_id") or "").strip()


def _is_success(row: dict) -> bool:
    verdict = str(row.get("verdict") or row.get("executor_status") or "").strip().upper()
    return verdict == "PASS"


def _runtime_hygiene(row: dict, detail: dict) -> dict:
    payload = row.get("executor_runtime_hygiene")
    if isinstance(payload, dict):
        return dict(payload)
    payload = detail.get("executor_runtime_hygiene")
    return dict(payload) if isinstance(payload, dict) else {}


def _attempt_rows(row: dict, detail: dict) -> list[dict]:
    rows = row.get("attempts")
    if isinstance(rows, list):
        return [item for item in rows if isinstance(item, dict)]
    rows = detail.get("attempts")
    return [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []


def _branch_sequence(row: dict) -> list[str]:
    rows = row.get("detected_branch_sequence")
    return [str(item).strip() for item in rows if str(item).strip()] if isinstance(rows, list) else []


def _scenario_pass_count(attempt: dict) -> int | None:
    rows = attempt.get("scenario_results")
    if not isinstance(rows, list):
        return None
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if bool(row.get("pass")):
            count += 1
    return count


def _progress_reasons(previous: dict, current: dict) -> list[str]:
    reasons: list[str] = []
    pairs = (
        ("check_model_pass", "check_ok_improved"),
        ("simulate_pass", "simulate_ok_improved"),
        ("physics_contract_pass", "physics_contract_pass_improved"),
    )
    for field, reason in pairs:
        prev_value = previous.get(field)
        curr_value = current.get(field)
        if prev_value is False and curr_value is True:
            reasons.append(reason)
    prev_scenarios = _scenario_pass_count(previous)
    curr_scenarios = _scenario_pass_count(current)
    if (
        prev_scenarios is not None
        and curr_scenarios is not None
        and curr_scenarios > prev_scenarios
    ):
        reasons.append("scenario_pass_count_increased")
    return reasons


def classify_one_shot_case(*, row: dict, detail: dict | None = None) -> dict:
    detail_payload = detail if isinstance(detail, dict) else {}
    item_id = _item_id(row)
    success = _is_success(row)
    runtime_hygiene = _runtime_hygiene(row, detail_payload)
    attempts = _attempt_rows(row, detail_payload)
    branch_sequence = _branch_sequence(row)
    planner_event_count = runtime_hygiene.get("planner_event_count")
    planner_event_count = int(planner_event_count) if isinstance(planner_event_count, int) else None

    base = {
        "item_id": item_id,
        "task_id": str(row.get("task_id") or item_id),
        "success": success,
        "planner_event_count": planner_event_count,
        "detected_branch_sequence": branch_sequence,
        "attempt_count": len(attempts),
    }
    if not success:
        return {
            **base,
            "label": "failed_or_unresolved",
            "reason": "case_not_successful",
            "audit": {
                "meets_true_continuity": False,
                "progress_signal_pairs": [],
            },
        }

    if planner_event_count == 1:
        return {
            **base,
            "label": "one_shot",
            "reason": "planner_event_count_eq_1",
            "audit": {
                "meets_true_continuity": False,
                "progress_signal_pairs": [],
            },
        }

    missing = []
    if planner_event_count is None:
        missing.append("planner_event_count_missing")
    if not branch_sequence:
        missing.append("detected_branch_sequence_missing")
    if len(attempts) < 2:
        missing.append("attempts_missing_or_lt_2")
    if missing:
        return {
            **base,
            "label": "unknown",
            "reason": ",".join(missing),
            "audit": {
                "meets_true_continuity": False,
                "progress_signal_pairs": [],
            },
        }

    progress_signal_pairs = []
    for idx in range(1, len(attempts)):
        reasons = _progress_reasons(attempts[idx - 1], attempts[idx])
        if not reasons:
            continue
        progress_signal_pairs.append(
            {
                "from_round": int(attempts[idx - 1].get("round") or idx),
                "to_round": int(attempts[idx].get("round") or (idx + 1)),
                "reasons": reasons,
            }
        )
    single_branch = len(set(branch_sequence)) == 1
    meets_true_continuity = bool(
        planner_event_count is not None
        and planner_event_count >= 2
        and single_branch
        and bool(progress_signal_pairs)
    )
    if meets_true_continuity:
        return {
            **base,
            "label": "true_continuity",
            "reason": "planner_ge_2_single_branch_progress_seen",
            "audit": {
                "meets_true_continuity": True,
                "progress_signal_pairs": progress_signal_pairs,
            },
        }
    non_continuity_reasons = []
    if planner_event_count < 2:
        non_continuity_reasons.append("planner_event_count_lt_2")
    if not single_branch:
        non_continuity_reasons.append("branch_sequence_not_single_value")
    if not progress_signal_pairs:
        non_continuity_reasons.append("no_progress_signal_pair")
    return {
        **base,
        "label": "multi_step_non_continuity",
        "reason": ",".join(non_continuity_reasons) or "multi_step_without_continuity",
        "audit": {
            "meets_true_continuity": False,
            "progress_signal_pairs": progress_signal_pairs,
        },
    }


def build_v0_3_12_one_shot_classifier(
    *,
    refreshed_summary_path: str = DEFAULT_REFRESHED_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    refreshed = _load_json(refreshed_summary_path)
    rows = _task_rows(refreshed)
    classified_rows = []
    successful_label_counts = {label: 0 for label in SUCCESS_LABELS}
    all_label_counts = {label: 0 for label in ALL_LABELS}
    successful_case_count = 0
    failed_or_unresolved_count = 0
    successful_labeled_count = 0

    for row in rows:
        detail = _load_json(row.get("result_json_path") or "")
        classified = classify_one_shot_case(row=row, detail=detail)
        label = str(classified["label"])
        all_label_counts[label] = int(all_label_counts.get(label) or 0) + 1
        if classified["success"]:
            successful_case_count += 1
            successful_label_counts[label] = int(successful_label_counts.get(label) or 0) + 1
            if label != "unknown":
                successful_labeled_count += 1
        else:
            failed_or_unresolved_count += 1
        classified_rows.append(
            {
                **classified,
                "result_json_path": str(row.get("result_json_path") or ""),
            }
        )

    unknown_success_count = int(successful_label_counts.get("unknown") or 0)
    true_continuity_count = int(successful_label_counts.get("true_continuity") or 0)
    unknown_success_pct = round((100.0 * unknown_success_count / successful_case_count), 1) if successful_case_count else 0.0
    true_continuity_pct = round((100.0 * true_continuity_count / successful_labeled_count), 1) if successful_labeled_count else 0.0
    payload = {
        "schema_version": SCHEMA_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if classified_rows else "EMPTY",
        "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "metrics": {
            "total_rows": len(classified_rows),
            "successful_case_count": successful_case_count,
            "failed_or_unresolved_count": failed_or_unresolved_count,
            "successful_label_counts": successful_label_counts,
            "all_label_counts": all_label_counts,
            "successful_labeled_count": successful_labeled_count,
            "labeled_count": successful_labeled_count,
            "unknown_success_count": unknown_success_count,
            "unknown_success_pct": unknown_success_pct,
            "true_continuity_count": true_continuity_count,
            "true_continuity_pct": true_continuity_pct,
        },
        "labeled_cases_path": "",
    }
    out_root = Path(out_dir)
    labeled_cases_path = out_root / "labeled_cases.json"
    payload["labeled_cases_path"] = str(labeled_cases_path.resolve())
    _write_json(labeled_cases_path, {"rows": classified_rows})
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.12 One-Shot Classifier",
                "",
                f"- status: `{payload['status']}`",
                f"- classifier_version: `{CLASSIFIER_VERSION}`",
                f"- total_rows: `{payload['metrics']['total_rows']}`",
                f"- successful_case_count: `{payload['metrics']['successful_case_count']}`",
                f"- successful_labeled_count: `{payload['metrics']['successful_labeled_count']}`",
                f"- unknown_success_pct: `{payload['metrics']['unknown_success_pct']}`",
                f"- true_continuity_pct: `{payload['metrics']['true_continuity_pct']}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.12 one-shot classifier summary.")
    parser.add_argument("--refreshed-summary", default=DEFAULT_REFRESHED_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_12_one_shot_classifier(
        refreshed_summary_path=str(args.refreshed_summary),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "total_rows": (payload.get("metrics") or {}).get("total_rows"),
                "successful_labeled_count": (payload.get("metrics") or {}).get("successful_labeled_count"),
            }
        )
    )


if __name__ == "__main__":
    main()
