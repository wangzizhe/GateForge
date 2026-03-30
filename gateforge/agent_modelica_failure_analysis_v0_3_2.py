from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_failure_analysis_v0_3_2"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_failure_analysis_v0_3_2"
DEFAULT_CONFIGS = (
    {
        "config_label": "baseline",
        "results_path": "artifacts/agent_modelica_harder_holdout_ablation_v0_3_1/baseline/gf_results.json",
    },
    {
        "config_label": "replay_only",
        "results_path": "artifacts/agent_modelica_harder_holdout_ablation_v0_3_1/replay_only/gf_results.json",
    },
    {
        "config_label": "planner_only",
        "results_path": "artifacts/agent_modelica_harder_holdout_ablation_v0_3_1/planner_only/gf_results.json",
    },
    {
        "config_label": "replay_plus_planner",
        "results_path": "artifacts/agent_modelica_harder_holdout_ablation_v0_3_1/replay_plus_planner/gf_results.json",
    },
)


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


def _norm(value: object) -> str:
    return str(value or "").strip()


def _results(payload: dict) -> list[dict]:
    rows = payload.get("results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def analyze_failure_matrix(configs: list[dict]) -> dict:
    per_mutation: dict[str, dict] = {}
    config_labels: list[str] = []
    for config in configs:
        label = _norm(config.get("config_label"))
        config_labels.append(label)
        payload = _load_json(config.get("results_path") or "")
        for row in _results(payload):
            mutation_id = _norm(row.get("mutation_id"))
            if not mutation_id:
                continue
            bucket = per_mutation.setdefault(
                mutation_id,
                {
                    "mutation_id": mutation_id,
                    "target_scale": _norm(row.get("target_scale")),
                    "expected_failure_type": _norm(row.get("expected_failure_type")),
                    "by_config": {},
                },
            )
            bucket["by_config"][label] = {
                "success": bool(row.get("success")),
                "executor_status": _norm(row.get("executor_status")),
                "elapsed_sec": float(row.get("elapsed_sec") or 0.0),
                "rounds_used": int(row.get("rounds_used") or 0),
                "resolution_path": _norm(row.get("resolution_path")),
                "dominant_stage_subtype": _norm(row.get("dominant_stage_subtype")),
                "planner_invoked": bool(row.get("planner_invoked")),
                "planner_used": bool(row.get("planner_used")),
                "planner_decisive": bool(row.get("planner_decisive")),
                "replay_used": bool(row.get("replay_used")),
            }

    case_rows: list[dict] = []
    for mutation_id, row in sorted(per_mutation.items()):
        by_config = row.get("by_config") if isinstance(row.get("by_config"), dict) else {}
        failed = [label for label in config_labels if not bool((by_config.get(label) or {}).get("success"))]
        succeeded = [label for label in config_labels if bool((by_config.get(label) or {}).get("success"))]
        resolution_paths = sorted(
            {
                _norm((by_config.get(label) or {}).get("resolution_path"))
                for label in failed
                if _norm((by_config.get(label) or {}).get("resolution_path"))
            }
        )
        stage_subtypes = sorted(
            {
                _norm((by_config.get(label) or {}).get("dominant_stage_subtype"))
                for label in failed
                if _norm((by_config.get(label) or {}).get("dominant_stage_subtype"))
            }
        )
        planner_invoked_any = any(bool((by_config.get(label) or {}).get("planner_invoked")) for label in config_labels)
        planner_decisive_any = any(bool((by_config.get(label) or {}).get("planner_decisive")) for label in config_labels)
        replay_used_any = any(bool((by_config.get(label) or {}).get("replay_used")) for label in config_labels)
        elapsed_values = [float((by_config.get(label) or {}).get("elapsed_sec") or 0.0) for label in config_labels if label in by_config]
        rounds_values = [int((by_config.get(label) or {}).get("rounds_used") or 0) for label in config_labels if label in by_config]
        case_rows.append(
            {
                "mutation_id": mutation_id,
                "target_scale": row.get("target_scale"),
                "expected_failure_type": row.get("expected_failure_type"),
                "failed_configs": failed,
                "succeeded_configs": succeeded,
                "persistent_failure": len(failed) == len(config_labels),
                "ablation_sensitive": bool(failed) and bool(succeeded),
                "failure_resolution_paths": resolution_paths,
                "failure_stage_subtypes": stage_subtypes,
                "planner_invoked_any": planner_invoked_any,
                "planner_decisive_any": planner_decisive_any,
                "replay_used_any": replay_used_any,
                "elapsed_sec_range": [min(elapsed_values) if elapsed_values else 0.0, max(elapsed_values) if elapsed_values else 0.0],
                "rounds_used_values": sorted(set(rounds_values)),
                "by_config": by_config,
            }
        )

    persistent_failures = [row for row in case_rows if bool(row.get("persistent_failure"))]
    ablation_sensitive = [row for row in case_rows if bool(row.get("ablation_sensitive"))]
    return {
        "config_labels": config_labels,
        "cases": case_rows,
        "persistent_failure_count": len(persistent_failures),
        "ablation_sensitive_failure_count": len(ablation_sensitive),
        "persistent_failures": persistent_failures,
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# Agent Modelica Failure Analysis v0.3.2",
        "",
        f"- generated_at_utc: `{_norm(payload.get('generated_at_utc'))}`",
        f"- persistent_failure_count: `{payload.get('persistent_failure_count')}`",
        f"- ablation_sensitive_failure_count: `{payload.get('ablation_sensitive_failure_count')}`",
        "",
        "## Persistent Failures",
        "",
    ]
    for row in payload.get("persistent_failures") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"### {row.get('mutation_id')}")
        lines.append("")
        lines.append(f"- expected_failure_type: `{row.get('expected_failure_type')}`")
        lines.append(f"- target_scale: `{row.get('target_scale')}`")
        lines.append(f"- failed_configs: `{', '.join(row.get('failed_configs') or [])}`")
        lines.append(f"- failure_resolution_paths: `{', '.join(row.get('failure_resolution_paths') or [])}`")
        lines.append(f"- failure_stage_subtypes: `{', '.join(row.get('failure_stage_subtypes') or [])}`")
        lines.append(f"- planner_invoked_any: `{row.get('planner_invoked_any')}`")
        lines.append(f"- planner_decisive_any: `{row.get('planner_decisive_any')}`")
        lines.append(f"- replay_used_any: `{row.get('replay_used_any')}`")
        lines.append(f"- elapsed_sec_range: `{row.get('elapsed_sec_range')}`")
        lines.append(f"- rounds_used_values: `{row.get('rounds_used_values')}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def run_failure_analysis(*, out_dir: str = DEFAULT_OUT_DIR, configs: list[dict] | None = None) -> dict:
    config_rows = configs if configs is not None else list(DEFAULT_CONFIGS)
    analysis = analyze_failure_matrix(config_rows)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "config_labels": analysis.get("config_labels") or [],
        "persistent_failure_count": int(analysis.get("persistent_failure_count") or 0),
        "ablation_sensitive_failure_count": int(analysis.get("ablation_sensitive_failure_count") or 0),
        "persistent_failures": analysis.get("persistent_failures") or [],
        "cases": analysis.get("cases") or [],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a v0.3.2 failure analysis summary from harder-holdout ablation results")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = run_failure_analysis(out_dir=str(args.out_dir))
    print(json.dumps({"persistent_failure_count": payload.get("persistent_failure_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
