from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_9_block_b_decision"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_9_block_b_decision"


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


def build_v0_3_9_block_b_decision(
    *,
    mainline_manifest_path: str,
    contrast_manifest_path: str,
    absorbed_classifier_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    mainline = _load_json(mainline_manifest_path)
    contrast = _load_json(contrast_manifest_path)
    classifier = _load_json(absorbed_classifier_summary_path)

    counts = ((classifier.get("metrics") or {}).get("primary_bucket_counts") or {})
    total = int((classifier.get("metrics") or {}).get("total_rows") or 0)
    sorted_counts = sorted(((bucket, int(count)) for bucket, count in counts.items()), key=lambda item: item[1], reverse=True)
    top_bucket, top_count = sorted_counts[0] if sorted_counts else ("", 0)
    residual_count = total - top_count
    top_coverage_pct = round(100.0 * top_count / total, 1) if total else 0.0
    residual_pct = round(100.0 * residual_count / total, 1) if total else 0.0

    decision = "blocked"
    reason = "insufficient_absorption_signal"
    replacement_hypothesis = ""
    if total > 0 and top_coverage_pct >= 80.0 and residual_pct <= 20.0:
        decision = "replacement_hypothesis_supported"
        reason = "single_absorption_mechanism_dominates_contrast_manifest"
        replacement_hypothesis = top_bucket

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if total > 0 else "EMPTY",
        "decision": decision,
        "reason": reason,
        "mainline_manifest_path": str(Path(mainline_manifest_path).resolve()) if Path(mainline_manifest_path).exists() else str(mainline_manifest_path),
        "contrast_manifest_path": str(Path(contrast_manifest_path).resolve()) if Path(contrast_manifest_path).exists() else str(contrast_manifest_path),
        "absorbed_classifier_summary_path": str(Path(absorbed_classifier_summary_path).resolve()) if Path(absorbed_classifier_summary_path).exists() else str(absorbed_classifier_summary_path),
        "metrics": {
            "mainline_task_count": int(mainline.get("task_count") or 0),
            "contrast_task_count": int(contrast.get("task_count") or 0),
            "top_bucket": top_bucket,
            "top_bucket_count": top_count,
            "top_bucket_coverage_pct": top_coverage_pct,
            "residual_count": residual_count,
            "residual_pct": residual_pct,
        },
        "replacement_hypothesis": replacement_hypothesis,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.9 Block B Decision",
                "",
                f"- decision: `{decision}`",
                f"- reason: `{reason}`",
                f"- top_bucket: `{top_bucket}`",
                f"- top_bucket_coverage_pct: `{top_coverage_pct}`",
                f"- residual_pct: `{residual_pct}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the single Block B decision for v0.3.9.")
    parser.add_argument("--mainline-manifest", required=True)
    parser.add_argument("--contrast-manifest", required=True)
    parser.add_argument("--absorbed-classifier-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_9_block_b_decision(
        mainline_manifest_path=str(args.mainline_manifest),
        contrast_manifest_path=str(args.contrast_manifest),
        absorbed_classifier_summary_path=str(args.absorbed_classifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))


if __name__ == "__main__":
    main()
