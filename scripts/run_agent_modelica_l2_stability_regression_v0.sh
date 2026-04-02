#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_L2_STABILITY_OUT_DIR:-artifacts/agent_modelica_l2_stability_regression_v0}"
TASKSET="${GATEFORGE_AGENT_L2_STABILITY_TASKSET:-assets_private/agent_modelica_l2_freeze_pack_v0/taskset_frozen.json}"
ACCEPT_PASS_RATE_PCT="${GATEFORGE_AGENT_L2_ACCEPT_PASS_RATE_PCT:-80.0}"

MAX_ROUNDS="${GATEFORGE_AGENT_L2_STABILITY_MAX_ROUNDS:-2}"
MAX_TIME_SEC="${GATEFORGE_AGENT_L2_STABILITY_MAX_TIME_SEC:-240}"
RUNTIME_THRESHOLD="${GATEFORGE_AGENT_L2_STABILITY_RUNTIME_THRESHOLD:-0.2}"
LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_L2_STABILITY_LIVE_TIMEOUT_SEC:-180}"
LIVE_MAX_OUTPUT_CHARS="${GATEFORGE_AGENT_L2_STABILITY_LIVE_MAX_OUTPUT_CHARS:-2400}"
LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-python3 -m gateforge.agent_modelica_live_executor_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-auto}\" --backend \"${GATEFORGE_AGENT_LIVE_OM_BACKEND:-openmodelica_docker}\" --docker-image \"${GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}\"}"

REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}"
RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}"

if [ ! -f "$TASKSET" ]; then
  echo "Missing taskset: $TASKSET" >&2
  exit 1
fi

mkdir -p "$OUT_DIR/run1" "$OUT_DIR/run2"

run_once () {
  local run_tag="$1"
  python3 -m gateforge.agent_modelica_run_contract_v1 \
    --taskset "$TASKSET" \
    --mode live \
    --max-rounds "$MAX_ROUNDS" \
    --max-time-sec "$MAX_TIME_SEC" \
    --runtime-threshold "$RUNTIME_THRESHOLD" \
    --repair-history "$REPAIR_MEMORY_PATH" \
    --patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
    --retrieval-policy "$RETRIEVAL_POLICY_PATH" \
    --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
    --live-timeout-sec "$LIVE_TIMEOUT_SEC" \
    --live-max-output-chars "$LIVE_MAX_OUTPUT_CHARS" \
    --results-out "$OUT_DIR/$run_tag/run_results.json" \
    --out "$OUT_DIR/$run_tag/run_summary.json"
}

run_once run1
run_once run2

export GATEFORGE_AGENT_L2_STABILITY_OUT_DIR="$OUT_DIR"
export GATEFORGE_AGENT_L2_STABILITY_ACCEPT_PASS_RATE="$ACCEPT_PASS_RATE_PCT"
python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(os.environ["GATEFORGE_AGENT_L2_STABILITY_OUT_DIR"])
accept_rate = float(os.environ["GATEFORGE_AGENT_L2_STABILITY_ACCEPT_PASS_RATE"])

def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def _infra_reason(stderr: str, reason: str) -> str:
    text = (str(stderr or "") + " " + str(reason or "")).lower()
    if "timeoutexpired" in text or "timed out" in text or "live_executor_timeout" in text:
        return "timeout"
    if "permission denied while trying to connect to the docker api" in text:
        return "docker_permission_denied"
    if "includes invalid characters for a local volume name" in text:
        return "docker_volume_mount_invalid"
    if "failed to load package modelica" in text:
        return "msl_load_failed"
    if "model_path_missing" in text or "no such file or directory" in text:
        return "path_not_found"
    return ""

def _summarize(run_dir: Path) -> dict:
    summary = _load(run_dir / "run_summary.json")
    results = _load(run_dir / "run_results.json")
    records = results.get("records") if isinstance(results.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    first_observed: dict[str, int] = {}
    infra_by_reason: dict[str, int] = {}
    infra_count = 0
    for rec in records:
        attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
        first = attempts[0] if attempts and isinstance(attempts[0], dict) else {}
        observed = str(first.get("observed_failure_type") or "none")
        first_observed[observed] = int(first_observed.get(observed, 0)) + 1
        for a in attempts:
            if not isinstance(a, dict):
                continue
            infra = _infra_reason(a.get("stderr_snippet"), a.get("reason"))
            if infra:
                infra_count += 1
                infra_by_reason[infra] = int(infra_by_reason.get(infra, 0)) + 1
    return {
        "success_at_k_pct": float(summary.get("success_at_k_pct") or 0.0),
        "regression_count": int(summary.get("regression_count") or 0),
        "physics_fail_count": int(summary.get("physics_fail_count") or 0),
        "infra_failure_count": infra_count,
        "infra_failure_by_reason": {k: infra_by_reason[k] for k in sorted(infra_by_reason.keys())},
        "first_observed_failure_type_counts": {k: first_observed[k] for k in sorted(first_observed.keys())},
    }

run1 = _summarize(out_dir / "run1")
run2 = _summarize(out_dir / "run2")
reasons = []
for idx, row in enumerate((run1, run2), start=1):
    if float(row["success_at_k_pct"]) < accept_rate:
        reasons.append(f"run{idx}_pass_rate_below_threshold")
    if int(row["infra_failure_count"]) > 0:
        reasons.append(f"run{idx}_infra_failures_present")
status = "PASS" if not reasons else "FAIL"

summary = {
    "schema_version": "agent_modelica_l2_stability_regression_v0",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "acceptance": {
        "min_pass_rate_pct": accept_rate,
        "infra_failure_count_must_equal": 0,
    },
    "run1": run1,
    "run2": run2,
    "reasons": reasons,
    "paths": {
        "run1_summary": str(out_dir / "run1" / "run_summary.json"),
        "run1_results": str(out_dir / "run1" / "run_results.json"),
        "run2_summary": str(out_dir / "run2" / "run_summary.json"),
        "run2_results": str(out_dir / "run2" / "run_results.json"),
    },
}
(out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out_dir / "summary.md").write_text(
    "\n".join(
        [
            "# Agent Modelica L2 Stability Regression v0",
            "",
            f"- status: `{status}`",
            f"- run1 success_at_k_pct: `{run1['success_at_k_pct']}`",
            f"- run2 success_at_k_pct: `{run2['success_at_k_pct']}`",
            f"- run1 infra_failure_count: `{run1['infra_failure_count']}`",
            f"- run2 infra_failure_count: `{run2['infra_failure_count']}`",
            f"- reasons: `{reasons}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"status": status, "run1_success_at_k_pct": run1["success_at_k_pct"], "run2_success_at_k_pct": run2["success_at_k_pct"], "run1_infra_failure_count": run1["infra_failure_count"], "run2_infra_failure_count": run2["infra_failure_count"]}))
if status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
