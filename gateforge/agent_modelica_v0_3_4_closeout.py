from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_4_closeout"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_4_closeout"


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


def build_v0_3_4_closeout(
    *,
    dev_priorities_summary_path: str,
    promotion_summary_path: str,
    previous_closeout_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    dev = _load_json(dev_priorities_summary_path)
    promotion = _load_json(promotion_summary_path)
    previous = _load_json(previous_closeout_summary_path)

    dev_status = _norm(dev.get("status"))
    previous_classification = _norm(previous.get("classification"))
    primary_repair_lever = _norm((dev.get("primary_repair_lever") or {}).get("lever"))
    best_harder_lane = _norm((dev.get("best_harder_lane") or {}).get("family_id"))
    promotion_status = _norm(promotion.get("status"))
    promote = bool((promotion.get("decision") or {}).get("promote"))
    observed = promotion.get("observed_metrics") if isinstance(promotion.get("observed_metrics"), dict) else {}
    rescue_count = int(observed.get("deterministic_multi_round_rescue_count") or 0)
    applicable_count = int(observed.get("applicable_multi_round_rows") or 0)

    comparative_path_retained = previous_classification in {
        "development_priorities_shifted_comparative_path_retained",
        "paper_usable_comparative_path",
        "comparative_path_retained_provisional",
    }
    lane_ready = _norm((dev.get("best_harder_lane") or {}).get("status")) == "FREEZE_READY"

    if (
        dev_status == "PASS"
        and promotion_status == "PROMOTION_READY"
        and promote
        and primary_repair_lever == "multi_round_deterministic_repair_validation"
        and lane_ready
        and comparative_path_retained
    ):
        classification = "development_frontier_advanced_multi_round_promoted"
    else:
        classification = "development_frontier_incomplete"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if classification != "development_frontier_incomplete" else "FAIL",
        "classification": classification,
        "dev_priorities_summary_path": str(Path(dev_priorities_summary_path).resolve()) if Path(dev_priorities_summary_path).exists() else str(dev_priorities_summary_path),
        "promotion_summary_path": str(Path(promotion_summary_path).resolve()) if Path(promotion_summary_path).exists() else str(promotion_summary_path),
        "previous_closeout_summary_path": str(Path(previous_closeout_summary_path).resolve()) if Path(previous_closeout_summary_path).exists() else str(previous_closeout_summary_path),
        "metrics": {
            "previous_comparative_classification": previous_classification,
            "comparative_path_retained": comparative_path_retained,
            "primary_repair_lever": primary_repair_lever,
            "best_harder_lane": best_harder_lane,
            "best_harder_lane_status": _norm((dev.get("best_harder_lane") or {}).get("status")),
            "top_bottleneck_lever": _norm((dev.get("top_bottleneck_lever") or {}).get("lever")),
            "deterministic_multi_round_rescue_count": rescue_count,
            "applicable_multi_round_rows": applicable_count,
            "deterministic_multi_round_rescue_rate_pct": float(observed.get("deterministic_multi_round_rescue_rate_pct") or 0.0),
            "promotion_ready": promote,
        },
        "notes": [
            "v0.3.4 is a development-first release that builds on the v0.3.3 retained comparative path rather than trying to complete the paper-grade matrix.",
            "The primary engineering conclusion is that validated multi-round deterministic repair is now the primary repair lever on the hard_multiround_simulate_failure frontier.",
            "Full external repeated-run comparison remains deferred; the comparative route is preserved through the v0.3.3 closeout baseline.",
        ],
    }

    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.4 Closeout",
                "",
                f"- classification: `{payload['classification']}`",
                f"- previous_comparative_classification: `{payload['metrics']['previous_comparative_classification']}`",
                f"- primary_repair_lever: `{payload['metrics']['primary_repair_lever']}`",
                f"- best_harder_lane: `{payload['metrics']['best_harder_lane']}`",
                f"- best_harder_lane_status: `{payload['metrics']['best_harder_lane_status']}`",
                f"- deterministic_multi_round_rescue_count: `{payload['metrics']['deterministic_multi_round_rescue_count']}`",
                f"- deterministic_multi_round_rescue_rate_pct: `{payload['metrics']['deterministic_multi_round_rescue_rate_pct']}`",
                f"- promotion_ready: `{payload['metrics']['promotion_ready']}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.4 release closeout summary.")
    parser.add_argument("--dev-priorities-summary", required=True)
    parser.add_argument("--promotion-summary", required=True)
    parser.add_argument("--previous-closeout-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_4_closeout(
        dev_priorities_summary_path=str(args.dev_priorities_summary),
        promotion_summary_path=str(args.promotion_summary),
        previous_closeout_summary_path=str(args.previous_closeout_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
