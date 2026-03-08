#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L5_EVAL_OUT_DIR:-artifacts/agent_modelica_l5_eval_v1}"
BASE_TASKSET="${GATEFORGE_AGENT_L5_EVAL_TASKSET:-assets_private/agent_modelica_l2_freeze_pack_v0/taskset_frozen.json}"
SCALES_RAW="${GATEFORGE_AGENT_L5_EVAL_SCALES:-small,medium}"

PLANNER_BACKEND="${GATEFORGE_AGENT_L5_EVAL_PLANNER_BACKEND:-rule}"
BACKEND="${GATEFORGE_AGENT_L5_EVAL_BACKEND:-openmodelica_docker}"
OM_DOCKER_IMAGE="${GATEFORGE_AGENT_L5_EVAL_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"

MAX_ROUNDS="${GATEFORGE_AGENT_L5_EVAL_MAX_ROUNDS:-1}"
MAX_TIME_SEC="${GATEFORGE_AGENT_L5_EVAL_MAX_TIME_SEC:-120}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_L5_EVAL_LIVE_TIMEOUT_SEC:-90}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_L5_EVAL_LIVE_MAX_OUTPUT_CHARS:-1600}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_L5_EVAL_RUNTIME_THRESHOLD:-0.2}"

L3_LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_L5_EVAL_L3_LIVE_EXECUTOR_CMD:-python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${PLANNER_BACKEND}\" --backend \"${BACKEND}\" --docker-image \"${OM_DOCKER_IMAGE}\"}"
L4_LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_L5_EVAL_L4_LIVE_EXECUTOR_CMD:-${L3_LIVE_EXECUTOR_CMD}}"

L5_GATE_MODE="${GATEFORGE_AGENT_L5_GATE_MODE:-strict}"
L5_MIN_DELTA_SUCCESS_PP="${GATEFORGE_AGENT_L5_MIN_DELTA_SUCCESS_PP:-5}"
L5_MAX_PHYSICS_WORSEN_PP="${GATEFORGE_AGENT_L5_MAX_PHYSICS_WORSEN_PP:-2}"
L5_MAX_REGRESSION_WORSEN_PP="${GATEFORGE_AGENT_L5_MAX_REGRESSION_WORSEN_PP:-2}"
L5_INFRA_FAILURE_MUST_EQUAL="${GATEFORGE_AGENT_L5_INFRA_FAILURE_MUST_EQUAL:-0}"
L5_MIN_L3_PARSE_PCT="${GATEFORGE_AGENT_L5_MIN_L3_PARSE_PCT:-95}"
L5_MIN_L3_TYPE_PCT="${GATEFORGE_AGENT_L5_MIN_L3_TYPE_PCT:-70}"
L5_MIN_L3_STAGE_PCT="${GATEFORGE_AGENT_L5_MIN_L3_STAGE_PCT:-70}"

L5_LEDGER_PATH="${GATEFORGE_AGENT_L5_LEDGER_PATH:-${OUT_DIR}/private/l5_eval_ledger_v1.jsonl}"
L5_WEEKLY_OUT_JSON="${GATEFORGE_AGENT_L5_WEEKLY_OUT_JSON:-${OUT_DIR}/l5_weekly_metrics.json}"
L5_WEEKLY_OUT_MD="${GATEFORGE_AGENT_L5_WEEKLY_OUT_MD:-${OUT_DIR}/l5_weekly_metrics.md}"

if [ ! -f "$BASE_TASKSET" ]; then
  echo "Missing base taskset: $BASE_TASKSET" >&2
  exit 1
fi

mkdir -p "$OUT_DIR" "$OUT_DIR/l3" "$OUT_DIR/l4"
PREP_TASKSET="$OUT_DIR/taskset_prepared.json"

python3 - "$BASE_TASKSET" "$PREP_TASKSET" "$OUT_DIR" "$SCALES_RAW" <<'PY'
import json
import sys
from pathlib import Path

base_taskset = Path(sys.argv[1])
out_taskset = Path(sys.argv[2])
out_dir = Path(sys.argv[3])
scales_raw = str(sys.argv[4] or "")
allowed_scales = {x.strip().lower() for x in scales_raw.split(",") if x.strip()}

payload = json.loads(base_taskset.read_text(encoding="utf-8"))
tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []

model_dir = out_dir / "_prepared_models"
model_dir.mkdir(parents=True, exist_ok=True)
default_model = model_dir / "A1_default.mo"
default_model.write_text(
    "\n".join(
        [
            "model A1_default",
            "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);",
            "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);",
            "  Modelica.Electrical.Analog.Basic.Ground G1;",
            "equation",
            "  connect(V1.p, R1.p);",
            "  connect(R1.n, G1.p);",
            "  connect(V1.n, G1.p);",
            "end A1_default;",
            "",
        ]
    ),
    encoding="utf-8",
)

filtered = []
for row in tasks:
    if not isinstance(row, dict):
        continue
    scale = str(row.get("scale") or "").strip().lower()
    if scale not in allowed_scales:
        continue
    updated = dict(row)
    source = str(updated.get("source_model_path") or "").strip()
    mutated = str(updated.get("mutated_model_path") or "").strip()
    if not source:
        source = str(default_model)
    if not mutated:
        mutated = source
    updated["source_model_path"] = source
    updated["mutated_model_path"] = mutated
    filtered.append(updated)

out_payload = {
    "schema_version": str(payload.get("schema_version") or "agent_modelica_l5_taskset_prepared_v1"),
    "generated_from": str(base_taskset),
    "allowed_scales": sorted(allowed_scales),
    "tasks": filtered,
}
out_taskset.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            "status": "PASS" if filtered else "FAIL",
            "base_task_count": len(tasks),
            "prepared_task_count": len(filtered),
            "allowed_scales": sorted(allowed_scales),
        }
    )
)
if not filtered:
    raise SystemExit(1)
PY

set +e
GATEFORGE_AGENT_L3_STABILITY_TASKSET="$PREP_TASKSET" \
GATEFORGE_AGENT_L3_STABILITY_SCALES="$SCALES_RAW" \
GATEFORGE_AGENT_L3_STABILITY_OUT_DIR="$OUT_DIR/l3" \
GATEFORGE_AGENT_L3_STABILITY_PLANNER_BACKEND="$PLANNER_BACKEND" \
GATEFORGE_AGENT_L3_STABILITY_BACKEND="$BACKEND" \
GATEFORGE_AGENT_L3_STABILITY_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
GATEFORGE_AGENT_L3_STABILITY_MAX_ROUNDS="$MAX_ROUNDS" \
GATEFORGE_AGENT_L3_STABILITY_MAX_TIME_SEC="$MAX_TIME_SEC" \
GATEFORGE_AGENT_L3_STABILITY_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
GATEFORGE_AGENT_L3_STABILITY_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
GATEFORGE_AGENT_L3_STABILITY_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
GATEFORGE_AGENT_L3_STABILITY_LIVE_EXECUTOR_CMD="$L3_LIVE_EXECUTOR_CMD" \
bash scripts/run_agent_modelica_l3_stability_regression_v0.sh
L3_RC=$?

GATEFORGE_AGENT_L4_CLOSED_LOOP_TASKSET="$PREP_TASKSET" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_SCALES="$SCALES_RAW" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_OUT_DIR="$OUT_DIR/l4" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_PLANNER_BACKEND="$PLANNER_BACKEND" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_BACKEND="$BACKEND" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_OM_DOCKER_IMAGE="$OM_DOCKER_IMAGE" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_ROUNDS="$MAX_ROUNDS" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_MAX_TIME_SEC="$MAX_TIME_SEC" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_TIMEOUT_SEC="$LIVE_TIMEOUT_SEC" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_MAX_OUTPUT_CHARS="$LIVE_MAX_OUTPUT_CHARS" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_RUNTIME_THRESHOLD="$RUNTIME_THRESHOLD" \
GATEFORGE_AGENT_L4_CLOSED_LOOP_LIVE_EXECUTOR_CMD="$L4_LIVE_EXECUTOR_CMD" \
GATEFORGE_AGENT_L4_MIN_SUCCESS_DELTA_PP="$L5_MIN_DELTA_SUCCESS_PP" \
GATEFORGE_AGENT_L4_MAX_REGRESSION_WORSEN_PP="$L5_MAX_REGRESSION_WORSEN_PP" \
GATEFORGE_AGENT_L4_MAX_PHYSICS_WORSEN_PP="$L5_MAX_PHYSICS_WORSEN_PP" \
bash scripts/run_agent_modelica_l4_closed_loop_v0.sh
L4_RC=$?

python3 -m gateforge.agent_modelica_l5_eval_v1 \
  --run-summary "$OUT_DIR/l4/on/run_summary.json" \
  --run-results "$OUT_DIR/l4/on/run_results.json" \
  --l3-quality-summary "$OUT_DIR/l3/run2/diagnostic_quality_summary.json" \
  --l3-gate-summary "$OUT_DIR/l3/run2/l3_diagnostic_gate_summary.json" \
  --l4-ab-compare-summary "$OUT_DIR/l4/ab_compare_summary.json" \
  --gate-mode "$L5_GATE_MODE" \
  --min-delta-success-at-k-pp "$L5_MIN_DELTA_SUCCESS_PP" \
  --max-physics-fail-rate-worsen-pp "$L5_MAX_PHYSICS_WORSEN_PP" \
  --max-regression-fail-rate-worsen-pp "$L5_MAX_REGRESSION_WORSEN_PP" \
  --infra-failure-count-must-equal "$L5_INFRA_FAILURE_MUST_EQUAL" \
  --min-l3-parse-coverage-pct "$L5_MIN_L3_PARSE_PCT" \
  --min-l3-type-match-rate-pct "$L5_MIN_L3_TYPE_PCT" \
  --min-l3-stage-match-rate-pct "$L5_MIN_L3_STAGE_PCT" \
  --out "$OUT_DIR/l5_eval_summary.json" \
  --report-out "$OUT_DIR/l5_eval_summary.md"
L5_RC=$?
set -e

python3 - "$PREP_TASKSET" "$OUT_DIR/l5_eval_summary.json" "$L5_LEDGER_PATH" "$L5_WEEKLY_OUT_JSON" "$L5_WEEKLY_OUT_MD" "$L3_RC" "$L4_RC" "$L5_RC" "$PLANNER_BACKEND" "$BACKEND" "$L5_GATE_MODE" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from gateforge.agent_modelica_l4_l5_reason_map_v0 import (
    ALLOWED_WEEKLY_RECOMMENDATION_REASONS,
    map_l4_to_weekly_recommendation_reason_v0,
    normalize_l4_primary_reason_v0,
)

prep_taskset = Path(sys.argv[1])
l5_summary_path = Path(sys.argv[2])
ledger_path = Path(sys.argv[3])
weekly_json = Path(sys.argv[4])
weekly_md = Path(sys.argv[5])
l3_rc = int(sys.argv[6])
l4_rc = int(sys.argv[7])
l5_rc = int(sys.argv[8])
planner_backend = str(sys.argv[9] or "").strip()
backend = str(sys.argv[10] or "").strip()
gate_mode = str(sys.argv[11] or "").strip()

summary = json.loads(l5_summary_path.read_text(encoding="utf-8")) if l5_summary_path.exists() else {}
l4_ab_summary_path = l5_summary_path.parent / "l4" / "ab_compare_summary.json"
l4_ab_summary = json.loads(l4_ab_summary_path.read_text(encoding="utf-8")) if l4_ab_summary_path.exists() else {}
taskset_hash = hashlib.sha256(prep_taskset.read_bytes()).hexdigest() if prep_taskset.exists() else ""
reason_enum = summary.get("reason_enum") if isinstance(summary.get("reason_enum"), list) else []
reason_enum = [str(x).strip() for x in reason_enum if str(x).strip()]
primary_reason = str(summary.get("primary_reason") or "none")

def _infer_l4_primary_reason(payload: dict) -> str:
    on_payload = payload.get("on") if isinstance(payload.get("on"), dict) else {}
    reason_distribution = (
        on_payload.get("reason_distribution") if isinstance(on_payload.get("reason_distribution"), dict) else {}
    )
    ranked = sorted(
        [(str(k), int(v) if isinstance(v, int) else 0) for k, v in reason_distribution.items() if str(k).strip()],
        key=lambda row: (-row[1], row[0]),
    )
    if not ranked:
        return "none"
    for reason, _count in ranked:
        normalized = normalize_l4_primary_reason_v0(reason)
        if normalized not in {"none", "hard_checks_pass", "reason_enum_unknown"}:
            return normalized
    return normalize_l4_primary_reason_v0(ranked[0][0])

l4_primary_reason = normalize_l4_primary_reason_v0(str(summary.get("l4_primary_reason") or ""))
if l4_primary_reason in {"none", "reason_enum_unknown"}:
    l4_primary_reason = _infer_l4_primary_reason(l4_ab_summary if isinstance(l4_ab_summary, dict) else {})

row = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "taskset_sha256": taskset_hash,
    "thresholds": summary.get("thresholds") if isinstance(summary.get("thresholds"), dict) else {},
    "gate_mode": str(summary.get("gate_mode") or gate_mode),
    "gate_result": summary.get("gate_result"),
    "status": summary.get("status"),
    "l5_gate_status": summary.get("status"),
    "success_at_k_pct": summary.get("success_at_k_pct"),
    "delta_success_at_k_pp": summary.get("delta_success_at_k_pp"),
    "physics_fail_rate_pct": summary.get("physics_fail_rate_pct"),
    "regression_fail_rate_pct": summary.get("regression_fail_rate_pct"),
    "infra_failure_count": summary.get("infra_failure_count"),
    "l3_parse_coverage_pct": summary.get("l3_parse_coverage_pct"),
    "l3_type_match_rate_pct": summary.get("l3_type_match_rate_pct"),
    "l3_stage_match_rate_pct": summary.get("l3_stage_match_rate_pct"),
    "planner_backend": planner_backend,
    "backend": backend,
    "primary_reason": primary_reason,
    "l4_primary_reason": l4_primary_reason,
    "reasons": [str(x) for x in (summary.get("reasons") or []) if isinstance(x, str)],
    "reason_enum": reason_enum,
    "script_exit_codes": {
        "l3": l3_rc,
        "l4": l4_rc,
        "l5": l5_rc,
    },
}

ledger_path.parent.mkdir(parents=True, exist_ok=True)
with ledger_path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=True) + "\n")

rows = []
for line in ledger_path.read_text(encoding="utf-8").splitlines():
    text = str(line or "").strip()
    if not text:
        continue
    try:
        obj = json.loads(text)
    except Exception:
        continue
    if isinstance(obj, dict):
        rows.append(obj)

by_week = {}
for item in rows:
    dt_text = str(item.get("generated_at_utc") or "")
    try:
        dt = datetime.fromisoformat(dt_text.replace("Z", "+00:00"))
    except ValueError:
        continue
    year, week, _ = dt.isocalendar()
    key = f"{year}-W{week:02d}"
    prev = by_week.get(key)
    if prev is None or str(item.get("generated_at_utc") or "") >= str(prev.get("generated_at_utc") or ""):
        by_week[key] = item

week_keys = sorted(by_week.keys())
current_key = week_keys[-1] if week_keys else ""
previous_key = week_keys[-2] if len(week_keys) >= 2 else ""
current = by_week.get(current_key) if current_key else {}
previous = by_week.get(previous_key) if previous_key else {}

def _f(v, default=0.0):
    return float(v) if isinstance(v, (int, float)) else float(default)

def _is_promote_ready(item: dict) -> bool:
    if not isinstance(item, dict) or not item:
        return False
    gate_ok = str(item.get("l5_gate_status") or item.get("status") or "") == "PASS"
    delta_ok = _f(item.get("delta_success_at_k_pp")) >= 5.0
    infra_ok = int(item.get("infra_failure_count") or 0) == 0
    return bool(gate_ok and delta_ok and infra_ok)

current_primary_reason = str((current or {}).get("primary_reason") or "none")
if current_primary_reason != "none" and reason_enum and current_primary_reason not in reason_enum:
    current_primary_reason = "reason_enum_unknown"
current_l4_primary_reason = normalize_l4_primary_reason_v0(str((current or {}).get("l4_primary_reason") or "none"))
consecutive_promote_ready = _is_promote_ready(current) and _is_promote_ready(previous)
recommendation = "promote" if consecutive_promote_ready else "hold"
if recommendation == "promote":
    recommendation_reason = "two_week_consecutive_pass"
else:
    if not current:
        recommendation_reason = "insufficient_history"
    elif not previous:
        recommendation_reason = "insufficient_consecutive_history"
    elif current_primary_reason != "none":
        recommendation_reason = current_primary_reason
    else:
        recommendation_reason = map_l4_to_weekly_recommendation_reason_v0(current_l4_primary_reason)

if recommendation_reason not in ALLOWED_WEEKLY_RECOMMENDATION_REASONS:
    recommendation_reason = "reason_enum_unknown"

weekly = {
    "schema_version": "agent_modelica_l5_weekly_metrics_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if current else "NEEDS_REVIEW",
    "current_week": current_key,
    "previous_week": previous_key,
    "current": current,
    "previous": previous,
    "delta": {
        "success_at_k_pp": round(_f(current.get("success_at_k_pct")) - _f(previous.get("success_at_k_pct")), 2),
        "delta_success_at_k_pp": round(_f(current.get("delta_success_at_k_pp")) - _f(previous.get("delta_success_at_k_pp")), 2),
        "physics_fail_rate_pp": round(_f(current.get("physics_fail_rate_pct")) - _f(previous.get("physics_fail_rate_pct")), 2),
        "regression_fail_rate_pp": round(_f(current.get("regression_fail_rate_pct")) - _f(previous.get("regression_fail_rate_pct")), 2),
    },
    "recommendation": recommendation,
    "recommendation_reason": recommendation_reason,
    "l4_primary_reason": current_l4_primary_reason,
    "promote_rule": {
        "requires_two_week_consecutive_pass": True,
        "min_delta_success_at_k_pp": 5.0,
        "infra_failure_count_must_equal": 0,
    },
    "reason_enum": reason_enum,
    "recommendation_reason_enum": sorted(ALLOWED_WEEKLY_RECOMMENDATION_REASONS),
    "ledger_path": str(ledger_path),
    "row_count": len(rows),
}

weekly_json.parent.mkdir(parents=True, exist_ok=True)
weekly_md.parent.mkdir(parents=True, exist_ok=True)
weekly_json.write_text(json.dumps(weekly, indent=2), encoding="utf-8")
weekly_md.write_text(
    "\n".join(
        [
            "# Agent Modelica L5 Weekly Metrics v1",
            "",
            f"- status: `{weekly.get('status')}`",
            f"- current_week: `{weekly.get('current_week')}`",
            f"- previous_week: `{weekly.get('previous_week')}`",
            f"- current_success_at_k_pct: `{(current or {}).get('success_at_k_pct', 0.0)}`",
            f"- previous_success_at_k_pct: `{(previous or {}).get('success_at_k_pct', 0.0)}`",
            f"- delta_success_at_k_pp: `{(weekly.get('delta') or {}).get('success_at_k_pp', 0.0)}`",
            f"- recommendation: `{weekly.get('recommendation')}`",
            f"- recommendation_reason: `{weekly.get('recommendation_reason')}`",
            "",
        ]
    ),
    encoding="utf-8",
)
PY

python3 - "$OUT_DIR" "$L3_RC" "$L4_RC" "$L5_RC" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(sys.argv[1])
l3_rc = int(sys.argv[2])
l4_rc = int(sys.argv[3])
l5_rc = int(sys.argv[4])

l5_summary = json.loads((out_dir / "l5_eval_summary.json").read_text(encoding="utf-8")) if (out_dir / "l5_eval_summary.json").exists() else {}
weekly_summary = json.loads((out_dir / "l5_weekly_metrics.json").read_text(encoding="utf-8")) if (out_dir / "l5_weekly_metrics.json").exists() else {}
reasons = [str(x) for x in (l5_summary.get("reasons") or []) if isinstance(x, str)]
if l3_rc != 0:
    reasons.append("l3_regression_script_nonzero_exit")
if l4_rc != 0:
    reasons.append("l4_closed_loop_script_nonzero_exit")
if l5_rc != 0 and str(l5_summary.get("status") or "") != "FAIL":
    reasons.append("l5_eval_cli_nonzero_exit")

status = str(l5_summary.get("status") or "UNKNOWN")
if status not in {"PASS", "NEEDS_REVIEW", "FAIL"}:
    status = "FAIL"

summary = {
    "schema_version": "agent_modelica_l5_eval_bundle_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "l3_script_exit_code": l3_rc,
    "l4_script_exit_code": l4_rc,
    "l5_eval_exit_code": l5_rc,
    "l5_gate_result": str(l5_summary.get("gate_result") or ""),
    "success_at_k_pct": float(l5_summary.get("success_at_k_pct") or 0.0),
    "delta_success_at_k_pp": float(l5_summary.get("delta_success_at_k_pp") or 0.0),
    "physics_fail_rate_pct": float(l5_summary.get("physics_fail_rate_pct") or 0.0),
    "regression_fail_rate_pct": float(l5_summary.get("regression_fail_rate_pct") or 0.0),
    "infra_failure_count": int(l5_summary.get("infra_failure_count") or 0),
    "l3_parse_coverage_pct": float(l5_summary.get("l3_parse_coverage_pct") or 0.0),
    "l3_type_match_rate_pct": float(l5_summary.get("l3_type_match_rate_pct") or 0.0),
    "l3_stage_match_rate_pct": float(l5_summary.get("l3_stage_match_rate_pct") or 0.0),
    "l5_primary_reason": str(l5_summary.get("primary_reason") or "none"),
    "l4_primary_reason": str(l5_summary.get("l4_primary_reason") or "none"),
    "l5_reason_enum": [str(x) for x in (l5_summary.get("reason_enum") or []) if isinstance(x, str)],
    "weekly_recommendation": str(weekly_summary.get("recommendation") or ""),
    "weekly_recommendation_reason": str(weekly_summary.get("recommendation_reason") or ""),
    "reasons": sorted(set(reasons)),
    "paths": {
        "l3_summary": str(out_dir / "l3" / "summary.json"),
        "l4_summary": str(out_dir / "l4" / "ab_compare_summary.json"),
        "l5_eval_summary": str(out_dir / "l5_eval_summary.json"),
        "weekly_summary": str(out_dir / "l5_weekly_metrics.json"),
    },
}
(out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out_dir / "summary.md").write_text(
    "\n".join(
        [
            "# Agent Modelica L5 Eval Bundle v1",
            "",
            f"- status: `{summary.get('status')}`",
            f"- l5_gate_result: `{summary.get('l5_gate_result')}`",
            f"- success_at_k_pct: `{summary.get('success_at_k_pct')}`",
            f"- delta_success_at_k_pp: `{summary.get('delta_success_at_k_pp')}`",
            f"- physics_fail_rate_pct: `{summary.get('physics_fail_rate_pct')}`",
            f"- regression_fail_rate_pct: `{summary.get('regression_fail_rate_pct')}`",
            f"- infra_failure_count: `{summary.get('infra_failure_count')}`",
            f"- reasons: `{summary.get('reasons')}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps(summary))
if summary.get("status") == "FAIL":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
