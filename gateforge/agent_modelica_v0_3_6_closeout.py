from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_6_closeout"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_6_closeout"


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


def build_v0_3_6_closeout(
    *,
    refreshed_summary_path: str,
    classifier_summary_path: str,
    dev_priorities_summary_path: str,
    verifier_summary_path: str,
    comparative_checkpoint_summary_path: str,
    previous_closeout_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    refreshed = _load_json(refreshed_summary_path)
    classifier = _load_json(classifier_summary_path)
    dev = _load_json(dev_priorities_summary_path)
    verifier = _load_json(verifier_summary_path)
    checkpoint = _load_json(comparative_checkpoint_summary_path)
    previous = _load_json(previous_closeout_summary_path)

    lane = refreshed.get("lane_summary") if isinstance(refreshed.get("lane_summary"), dict) else {}
    lane_comp = lane.get("composition") if isinstance(lane.get("composition"), dict) else {}
    classifier_metrics = classifier.get("metrics") if isinstance(classifier.get("metrics"), dict) else {}
    counts = classifier_metrics.get("failure_bucket_counts") if isinstance(classifier_metrics.get("failure_bucket_counts"), dict) else {}
    dev_next = dev.get("next_bottleneck") if isinstance(dev.get("next_bottleneck"), dict) else {}
    dev_cover = dev.get("deterministic_coverage_explanation") if isinstance(dev.get("deterministic_coverage_explanation"), dict) else {}

    lane_status = _norm(lane.get("lane_status"))
    dev_status = _norm(dev.get("status"))
    verifier_status = _norm(verifier.get("status"))
    checkpoint_status = _norm(checkpoint.get("status"))
    previous_classification = _norm(previous.get("classification"))
    next_bottleneck = _norm(dev_next.get("lever"))
    deterministic_coverage_present = bool(dev_cover.get("present"))

    if (
        dev_status == "PASS"
        and verifier_status == "PASS"
        and checkpoint_status == "DEFER"
        and lane_status in {"ADMISSION_VALID", "FREEZE_READY"}
        and (
            next_bottleneck
            or deterministic_coverage_present
        )
    ):
        classification = "post_restore_frontier_advanced_next_bottleneck_identified"
    else:
        classification = "post_restore_frontier_v0_3_6_incomplete"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if classification != "post_restore_frontier_v0_3_6_incomplete" else "FAIL",
        "classification": classification,
        "inputs": {
            "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
            "classifier_summary_path": str(Path(classifier_summary_path).resolve()) if Path(classifier_summary_path).exists() else str(classifier_summary_path),
            "dev_priorities_summary_path": str(Path(dev_priorities_summary_path).resolve()) if Path(dev_priorities_summary_path).exists() else str(dev_priorities_summary_path),
            "verifier_summary_path": str(Path(verifier_summary_path).resolve()) if Path(verifier_summary_path).exists() else str(verifier_summary_path),
            "comparative_checkpoint_summary_path": str(Path(comparative_checkpoint_summary_path).resolve()) if Path(comparative_checkpoint_summary_path).exists() else str(comparative_checkpoint_summary_path),
            "previous_closeout_summary_path": str(Path(previous_closeout_summary_path).resolve()) if Path(previous_closeout_summary_path).exists() else str(previous_closeout_summary_path),
        },
        "metrics": {
            "previous_classification": previous_classification,
            "lane_status": lane_status,
            "admitted_count": int(lane.get("admitted_count") or 0),
            "single_sweep_success_rate_pct": float(lane_comp.get("single_sweep_success_rate_pct") or 0.0),
            "first_correction_residual_count": int(lane_comp.get("first_correction_residual_count") or 0),
            "success_beyond_single_sweep_count": int(classifier_metrics.get("success_beyond_single_sweep_count") or 0),
            "stalled_search_after_progress_count": int(counts.get("stalled_search_after_progress") or 0),
            "next_bottleneck": next_bottleneck,
            "deterministic_coverage_present": deterministic_coverage_present,
            "comparative_checkpoint_status": checkpoint_status,
        },
        "notes": [
            "v0.3.6 is still development-first: it validated the correct harder direction without reopening paper-grade comparative work.",
            "The collapse-only post-restore lane is admission-valid rather than freeze-ready, which means the direction is real but still mixed with some single-sweep-resolved cases.",
            "The main engineering conclusion is that the next unsolved lever has moved beyond v0.3.5 numeric sweep and is now centered on guided replan after progress.",
            "Comparative work remains explicitly deferred through the fixed v0.3.6 comparative reopen checkpoint artifact.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.6 Closeout",
                "",
                f"- classification: `{payload['classification']}`",
                f"- lane_status: `{payload['metrics']['lane_status']}`",
                f"- admitted_count: `{payload['metrics']['admitted_count']}`",
                f"- single_sweep_success_rate_pct: `{payload['metrics']['single_sweep_success_rate_pct']}`",
                f"- success_beyond_single_sweep_count: `{payload['metrics']['success_beyond_single_sweep_count']}`",
                f"- stalled_search_after_progress_count: `{payload['metrics']['stalled_search_after_progress_count']}`",
                f"- next_bottleneck: `{payload['metrics']['next_bottleneck']}`",
                f"- comparative_checkpoint_status: `{payload['metrics']['comparative_checkpoint_status']}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.6 release closeout summary.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--classifier-summary", required=True)
    parser.add_argument("--dev-priorities-summary", required=True)
    parser.add_argument("--verifier-summary", required=True)
    parser.add_argument("--comparative-checkpoint-summary", required=True)
    parser.add_argument("--previous-closeout-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_6_closeout(
        refreshed_summary_path=str(args.refreshed_summary),
        classifier_summary_path=str(args.classifier_summary),
        dev_priorities_summary_path=str(args.dev_priorities_summary),
        verifier_summary_path=str(args.verifier_summary),
        comparative_checkpoint_summary_path=str(args.comparative_checkpoint_summary),
        previous_closeout_summary_path=str(args.previous_closeout_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
