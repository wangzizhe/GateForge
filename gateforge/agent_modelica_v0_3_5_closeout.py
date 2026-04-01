from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_5_closeout"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_5_closeout"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def build_v0_3_5_closeout(
    *,
    dev_priorities_summary_path: str,
    promotion_summary_path: str,
    post_restore_classifier_summary_path: str,
    previous_closeout_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    dev = _load_json(dev_priorities_summary_path)
    promotion = _load_json(promotion_summary_path)
    classifier = _load_json(post_restore_classifier_summary_path)
    previous = _load_json(previous_closeout_summary_path)

    dev_status = _norm(dev.get("status"))
    promotion_status = _norm(promotion.get("status"))
    classifier_status = _norm(classifier.get("status"))
    previous_classification = _norm(previous.get("classification"))
    primary_repair_lever = _norm((dev.get("primary_repair_lever") or {}).get("lever"))
    best_harder_lane = _norm((dev.get("best_harder_lane") or {}).get("family_id"))
    best_harder_lane_status = _norm((dev.get("best_harder_lane") or {}).get("status"))
    observed = promotion.get("observed_metrics") if isinstance(promotion.get("observed_metrics"), dict) else {}
    classifier_metrics = classifier.get("metrics") if isinstance(classifier.get("metrics"), dict) else {}
    bucket_counts = classifier_metrics.get("failure_bucket_counts") if isinstance(classifier_metrics.get("failure_bucket_counts"), dict) else {}

    comparative_path_retained = previous_classification in {
        "development_priorities_shifted_comparative_path_retained",
        "development_frontier_advanced_multi_round_promoted",
        "post_restore_frontier_advanced_parameter_recovery_promoted",
        "paper_usable_comparative_path",
        "comparative_path_retained_provisional",
    }
    lane_ready = best_harder_lane_status == "FREEZE_READY"
    promotion_ready = bool((promotion.get("decision") or {}).get("promote"))
    success_rate_pct = float(observed.get("success_rate_pct") or 0.0)
    rule_then_llm_rate_pct = float(observed.get("rule_then_llm_rate_pct") or 0.0)

    if (
        dev_status == "PASS"
        and promotion_status == "PROMOTION_READY"
        and classifier_status == "PASS"
        and comparative_path_retained
        and lane_ready
        and promotion_ready
        and primary_repair_lever == "simulate_error_parameter_recovery_sweep"
        and best_harder_lane == "post_restore_residual_conflict"
        and success_rate_pct >= 60.0
        and rule_then_llm_rate_pct >= 50.0
    ):
        classification = "post_restore_frontier_advanced_parameter_recovery_promoted"
    else:
        classification = "post_restore_frontier_incomplete"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if classification != "post_restore_frontier_incomplete" else "FAIL",
        "classification": classification,
        "dev_priorities_summary_path": str(Path(dev_priorities_summary_path).resolve()) if Path(dev_priorities_summary_path).exists() else str(dev_priorities_summary_path),
        "promotion_summary_path": str(Path(promotion_summary_path).resolve()) if Path(promotion_summary_path).exists() else str(promotion_summary_path),
        "post_restore_classifier_summary_path": str(Path(post_restore_classifier_summary_path).resolve()) if Path(post_restore_classifier_summary_path).exists() else str(post_restore_classifier_summary_path),
        "previous_closeout_summary_path": str(Path(previous_closeout_summary_path).resolve()) if Path(previous_closeout_summary_path).exists() else str(previous_closeout_summary_path),
        "metrics": {
            "previous_classification": previous_classification,
            "comparative_path_retained": comparative_path_retained,
            "primary_repair_lever": primary_repair_lever,
            "best_harder_lane": best_harder_lane,
            "best_harder_lane_status": best_harder_lane_status,
            "success_rate_pct": success_rate_pct,
            "planner_invoked_pct": float(observed.get("planner_invoked_pct") or 0.0),
            "deterministic_only_pct": float(observed.get("deterministic_only_pct") or 0.0),
            "rule_then_llm_rate_pct": rule_then_llm_rate_pct,
            "post_restore_progress_rate_pct": float(classifier_metrics.get("post_restore_progress_rate_pct") or 0.0),
            "success_after_restore_count": int(bucket_counts.get("success_after_restore") or 0),
        },
        "notes": [
            "v0.3.5 is a development-first release that advances beyond the v0.3.4 multi-round restore frontier instead of chasing a full external paper matrix.",
            "The primary engineering conclusion is that the post-restore residual-conflict lane is now real, freeze-ready, and no longer dominated by deterministic-only repair.",
            "The promoted v0.3.5 repair lever is simulate_error_parameter_recovery_sweep, which converts planner-diagnosed direction signals into numeric recovery trials.",
            "Comparative work remains preserved through earlier retained baselines and is still deferred to a later dedicated paper-evidence window.",
        ],
    }

    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.5 Closeout",
                "",
                f"- classification: `{payload['classification']}`",
                f"- previous_classification: `{payload['metrics']['previous_classification']}`",
                f"- primary_repair_lever: `{payload['metrics']['primary_repair_lever']}`",
                f"- best_harder_lane: `{payload['metrics']['best_harder_lane']}`",
                f"- best_harder_lane_status: `{payload['metrics']['best_harder_lane_status']}`",
                f"- success_rate_pct: `{payload['metrics']['success_rate_pct']}`",
                f"- rule_then_llm_rate_pct: `{payload['metrics']['rule_then_llm_rate_pct']}`",
                f"- success_after_restore_count: `{payload['metrics']['success_after_restore_count']}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.5 release closeout summary.")
    parser.add_argument("--dev-priorities-summary", required=True)
    parser.add_argument("--promotion-summary", required=True)
    parser.add_argument("--post-restore-classifier-summary", required=True)
    parser.add_argument("--previous-closeout-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_5_closeout(
        dev_priorities_summary_path=str(args.dev_priorities_summary),
        promotion_summary_path=str(args.promotion_summary),
        post_restore_classifier_summary_path=str(args.post_restore_classifier_summary),
        previous_closeout_summary_path=str(args.previous_closeout_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
