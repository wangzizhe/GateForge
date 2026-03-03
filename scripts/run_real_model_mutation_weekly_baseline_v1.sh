#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_WEEKLY_BASELINE_OUT_DIR:-artifacts/real_model_mutation_weekly_baseline_v1}"
WEEK_TAG="${GATEFORGE_WEEK_TAG:-$(date -u +%G-W%V)}"
BOOTSTRAP_SUMMARY="${GATEFORGE_MODELICA_BOOTSTRAP_SUMMARY:-artifacts/modelica_open_source_bootstrap_v1/summary.json}"
SCALE_SUMMARY="${GATEFORGE_SCALE_BATCH_SUMMARY:-}"
SCALE_GATE_SUMMARY="${GATEFORGE_SCALE_GATE_SUMMARY:-}"
DEPTH_REPORT_SUMMARY="${GATEFORGE_DEPTH_UPGRADE_REPORT_SUMMARY:-}"
STABILITY_SUMMARY="${GATEFORGE_STABILITY_TRIPLET_SUMMARY:-artifacts/private_model_mutation_depth6_stability_triplet_v1/summary.json}"
LEDGER_PATH="${GATEFORGE_WEEKLY_LEDGER_PATH:-$OUT_DIR/history.jsonl}"

if [ -z "$SCALE_SUMMARY" ]; then
  if [ -f "artifacts/private_model_mutation_scale_depth6_sprint_v1/summary.json" ]; then
    SCALE_SUMMARY="artifacts/private_model_mutation_scale_depth6_sprint_v1/summary.json"
  elif [ -f "artifacts/private_model_mutation_scale_depth4_sprint_v1/summary.json" ]; then
    SCALE_SUMMARY="artifacts/private_model_mutation_scale_depth4_sprint_v1/summary.json"
  else
    SCALE_SUMMARY="artifacts/private_model_mutation_scale_sprint_v1/summary.json"
  fi
fi

if [ -z "$SCALE_GATE_SUMMARY" ]; then
  if [ -f "artifacts/private_model_mutation_scale_depth6_sprint_v1/scale_gate_summary.json" ]; then
    SCALE_GATE_SUMMARY="artifacts/private_model_mutation_scale_depth6_sprint_v1/scale_gate_summary.json"
  elif [ -f "artifacts/private_model_mutation_scale_depth4_sprint_v1/scale_gate_summary.json" ]; then
    SCALE_GATE_SUMMARY="artifacts/private_model_mutation_scale_depth4_sprint_v1/scale_gate_summary.json"
  else
    SCALE_GATE_SUMMARY="artifacts/private_model_mutation_scale_sprint_v1/scale_gate_summary.json"
  fi
fi

if [ -z "$DEPTH_REPORT_SUMMARY" ]; then
  if [ -f "artifacts/private_model_mutation_scale_depth6_sprint_v1/depth_upgrade_report.json" ]; then
    DEPTH_REPORT_SUMMARY="artifacts/private_model_mutation_scale_depth6_sprint_v1/depth_upgrade_report.json"
  elif [ -f "artifacts/private_model_mutation_scale_depth4_sprint_v1/depth_upgrade_report.json" ]; then
    DEPTH_REPORT_SUMMARY="artifacts/private_model_mutation_scale_depth4_sprint_v1/depth_upgrade_report.json"
  else
    DEPTH_REPORT_SUMMARY=""
  fi
fi

mkdir -p "$OUT_DIR"
export OUT_DIR

if [ -f "$OUT_DIR/history_summary.json" ]; then
  cp "$OUT_DIR/history_summary.json" "$OUT_DIR/history_summary_previous.json"
else
  rm -f "$OUT_DIR/history_summary_previous.json"
fi

rm -f "$OUT_DIR"/weekly_summary.json "$OUT_DIR"/weekly_summary.md "$OUT_DIR"/history_summary.json "$OUT_DIR"/history_summary.md "$OUT_DIR"/history_trend.json "$OUT_DIR"/history_trend.md "$OUT_DIR"/summary.json "$OUT_DIR"/summary.md

SCALE_DIR="$(cd "$(dirname "$SCALE_SUMMARY")" && pwd)"
python3 -m gateforge.dataset_real_model_uniqueness_guard_v1 \
  --intake-runner-accepted "$SCALE_DIR/intake_runner_accepted.json" \
  --intake-registry-rows "$SCALE_DIR/intake_registry_rows.json" \
  --out "$OUT_DIR/uniqueness_guard_summary.json" \
  --report-out "$OUT_DIR/uniqueness_guard_summary.md"

python3 -m gateforge.dataset_real_model_mutation_coverage_quality_gate_v1 \
  --real-model-registry "$SCALE_DIR/intake_registry_rows.json" \
  --validated-mutation-manifest "$SCALE_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$SCALE_DIR/mutation_raw_observations.json" \
  --out "$OUT_DIR/coverage_quality_summary.json" \
  --report-out "$OUT_DIR/coverage_quality_summary.md"

WEEKLY_CMD=(python3 -m gateforge.dataset_real_model_mutation_weekly_summary_v1
  --week-tag "$WEEK_TAG"
  --open-source-bootstrap-summary "$BOOTSTRAP_SUMMARY"
  --scale-batch-summary "$SCALE_SUMMARY"
  --scale-gate-summary "$SCALE_GATE_SUMMARY"
  --uniqueness-guard-summary "$OUT_DIR/uniqueness_guard_summary.json"
  --coverage-quality-gate-summary "$OUT_DIR/coverage_quality_summary.json"
  --depth-upgrade-report-summary "$DEPTH_REPORT_SUMMARY"
  --out "$OUT_DIR/weekly_summary.json"
  --report-out "$OUT_DIR/weekly_summary.md"
)
if [ -f "$STABILITY_SUMMARY" ]; then
  WEEKLY_CMD+=(--stability-triplet-summary "$STABILITY_SUMMARY")
fi
"${WEEKLY_CMD[@]}"

python3 -m gateforge.dataset_moat_weekly_summary_history_v1 \
  --record "$OUT_DIR/weekly_summary.json" \
  --ledger "$LEDGER_PATH" \
  --out "$OUT_DIR/history_summary.json" \
  --report-out "$OUT_DIR/history_summary.md"

if [ -f "$OUT_DIR/history_summary_previous.json" ]; then
  python3 -m gateforge.dataset_moat_weekly_summary_history_trend_v1 \
    --previous "$OUT_DIR/history_summary_previous.json" \
    --current "$OUT_DIR/history_summary.json" \
    --out "$OUT_DIR/history_trend.json" \
    --report-out "$OUT_DIR/history_trend.md"
else
  cat > "$OUT_DIR/history_trend.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_avg_real_model_count": 0.0,
    "delta_avg_stability_score": 0.0,
    "delta_avg_advantage_score": 0.0,
    "alerts": []
  }
}
JSON
fi

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
weekly = json.loads((out / "weekly_summary.json").read_text(encoding="utf-8"))
history = json.loads((out / "history_summary.json").read_text(encoding="utf-8"))
trend = json.loads((out / "history_trend.json").read_text(encoding="utf-8"))
kpis = weekly.get("kpis") if isinstance(weekly.get("kpis"), dict) else {}

payload = {
    "week_tag": weekly.get("week_tag"),
    "weekly_status": weekly.get("status"),
    "history_status": history.get("status"),
    "trend_status": trend.get("status"),
    "real_model_count": kpis.get("real_model_count"),
    "unique_real_model_count": kpis.get("unique_real_model_count"),
    "duplicate_ratio_pct": kpis.get("duplicate_ratio_pct"),
    "large_model_count": kpis.get("large_model_count"),
    "reproducible_mutation_count": kpis.get("reproducible_mutation_count"),
    "mutations_per_failure_type": kpis.get("mutations_per_failure_type"),
    "failure_distribution_stability_score": kpis.get("failure_distribution_stability_score"),
}
(out / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload))
if str(weekly.get("status") or "") == "FAIL":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
