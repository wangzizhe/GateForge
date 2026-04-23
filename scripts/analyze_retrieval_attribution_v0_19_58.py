from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent

FOCUS_CASES = [
    "v01945_HydroTurbineGov_v0_pp_at_dturb_pv_q_nl",
    "v01945_HydroTurbineGov_v0_pp_r__pv_pmech0+p",
    "v01945_ThermalZone_v0_pp_c1_c3_pv_phi1",
    "v01945_HydroTurbineGov_v0_pp_r__pv_pmech0+q",
    "v01945_SyncMachineSimplified_v0_pp_efd_set_id_set_pv_xadifd",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _case_model_family(candidate_id: str) -> str:
    parts = str(candidate_id or "").split("_")
    return parts[1] if len(parts) > 1 else "unknown"


def _load_case_payload(root: Path, dataset: str, mode: str, candidate_id: str) -> dict[str, Any] | None:
    path = root / dataset / mode / f"{candidate_id}_{mode}.json"
    if not path.exists():
        return None
    return _load_json(path)


def _iter_case_ids(root: Path, dataset: str) -> list[str]:
    out: set[str] = set()
    for mode in ("baseline-c5", "retrieval-c5"):
        mode_dir = root / dataset / mode
        if not mode_dir.exists():
            continue
        for path in mode_dir.glob("*.json"):
            if path.name == "summary.json":
                continue
            suffix = f"_{mode}.json"
            if path.name.endswith(suffix):
                out.add(path.name[: -len(suffix)])
    return sorted(out)


def _store_hit_map(store: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in store.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("trajectory_success") is not True:
            continue
        candidate_id = str(entry.get("candidate_id") or "").strip()
        if not candidate_id or candidate_id in out:
            continue
        out[candidate_id] = {
            "candidate_id": candidate_id,
            "mutation_family": str(entry.get("mutation_family") or "unknown"),
            "failure_type": str(entry.get("failure_type") or "unknown"),
            "summary": str(entry.get("summary") or ""),
            "mode": str(entry.get("mode") or "unknown"),
            "model_family": _case_model_family(candidate_id),
        }
    return out


def classify_outcome_transition(
    baseline_status: str | None,
    retrieval_status: str | None,
) -> str:
    base = str(baseline_status or "missing")
    ret = str(retrieval_status or "missing")
    if base == "pass" and ret == "fail":
        return "retrieval_regression"
    if base == "fail" and ret == "pass":
        return "retrieval_uplift"
    if base == "pass" and ret == "pass":
        return "both_pass"
    if base == "fail" and ret == "fail":
        return "both_fail"
    return "incomplete_pair"


def first_divergence_round(
    baseline_rounds: list[dict[str, Any]],
    retrieval_rounds: list[dict[str, Any]],
) -> int | None:
    max_len = max(len(baseline_rounds), len(retrieval_rounds))
    for idx in range(max_len):
        base = baseline_rounds[idx] if idx < len(baseline_rounds) else {}
        ret = retrieval_rounds[idx] if idx < len(retrieval_rounds) else {}
        keys = (
            "advance",
            "chosen_candidate_id",
            "coverage_check_pass",
            "coverage_simulate_pass",
        )
        if any(base.get(key) != ret.get(key) for key in keys):
            return idx + 1
    return None


def infer_mechanism(
    *,
    candidate_id: str,
    baseline_payload: dict[str, Any] | None,
    retrieval_payload: dict[str, Any] | None,
    retrieval_hit_infos: list[dict[str, Any]],
) -> tuple[str, str]:
    transition = classify_outcome_transition(
        None if baseline_payload is None else baseline_payload.get("final_status"),
        None if retrieval_payload is None else retrieval_payload.get("final_status"),
    )
    current_family = _case_model_family(candidate_id)
    cross_family_hits = [
        hit for hit in retrieval_hit_infos
        if str(hit.get("model_family") or "") != current_family
    ]
    baseline_rounds = [] if baseline_payload is None else list(baseline_payload.get("rounds") or [])
    retrieval_rounds = [] if retrieval_payload is None else list(retrieval_payload.get("rounds") or [])
    baseline_max_check = max((int(rd.get("coverage_check_pass") or 0) for rd in baseline_rounds), default=0)
    retrieval_max_check = max((int(rd.get("coverage_check_pass") or 0) for rd in retrieval_rounds), default=0)

    if transition == "retrieval_regression":
        if baseline_max_check > 0 and retrieval_max_check == 0:
            return (
                "retrieval_diluted_current_omc_signal",
                "baseline 已出现可用 check_pass 候选，但 retrieval 臂在所有轮次都没把任何候选推进到 check_pass。",
            )
        if cross_family_hits:
            return (
                "cross_model_transfer_misled_search",
                "检索命中了跨模型族成功轨迹，历史经验更像表面相似迁移，可能把搜索方向带偏。",
            )
        return (
            "retrieval_added_unhelpful_context",
            "检索上下文改变了搜索分布，但没有把候选推进到更强结构状态。",
        )

    if transition == "retrieval_uplift":
        if retrieval_max_check > baseline_max_check:
            return (
                "retrieval_helped_search_direction",
                "retrieval 臂比 baseline 更早产生 check_pass / simulate_pass 候选，说明历史轨迹帮助缩小了搜索空间。",
            )
        return (
            "retrieval_helped_late_convergence",
            "retrieval 没显著提升前几轮结构信号，但最终帮助收敛到了可通过候选。",
        )

    if transition == "both_fail":
        if retrieval_payload and retrieval_payload.get("round_count", 0) < (baseline_payload or {}).get("round_count", 0):
            return (
                "retrieval_shortened_search_without_solving",
                "retrieval 让轨迹更快停住，但没有真正把问题解开。",
            )
        return (
            "retrieval_no_material_effect",
            "两臂都未解出，retrieval 没形成稳定正向作用。",
        )

    if transition == "both_pass":
        if retrieval_payload and retrieval_payload.get("round_count", 0) > (baseline_payload or {}).get("round_count", 0):
            return (
                "retrieval_preserved_success_but_slower",
                "retrieval 没改变最终结果，但增加了轮数和搜索开销。",
            )
        return (
            "retrieval_preserved_success",
            "retrieval 没改变最终结果，也没有形成明显副作用。",
        )

    return (
        "insufficient_data",
        "case 对照不完整，无法做稳定归因。",
    )


def _round_retrieval_details(
    retrieval_payload: dict[str, Any] | None,
    hit_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if retrieval_payload is None:
        return []
    details: list[dict[str, Any]] = []
    for rd in retrieval_payload.get("rounds") or []:
        hit_ids = [str(x) for x in (rd.get("retrieved_candidate_ids") or [])]
        hits = []
        for candidate_id in hit_ids:
            info = hit_map.get(candidate_id, {})
            hits.append(
                {
                    "candidate_id": candidate_id,
                    "model_family": str(info.get("model_family") or "unknown"),
                    "mutation_family": str(info.get("mutation_family") or "unknown"),
                    "failure_type": str(info.get("failure_type") or "unknown"),
                    "summary": str(info.get("summary") or ""),
                }
            )
        details.append(
            {
                "round": int(rd.get("round") or len(details) + 1),
                "advance": str(rd.get("advance") or "unknown"),
                "retrieval_hit_count": int(rd.get("retrieval_hit_count") or 0),
                "coverage_check_pass": int(rd.get("coverage_check_pass") or 0),
                "coverage_simulate_pass": int(rd.get("coverage_simulate_pass") or 0),
                "chosen_candidate_id": rd.get("chosen_candidate_id"),
                "hits": hits,
            }
        )
    return details


def analyze_case(
    *,
    candidate_id: str,
    dataset: str,
    root: Path,
    hit_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    baseline_payload = _load_case_payload(root, dataset, "baseline-c5", candidate_id)
    retrieval_payload = _load_case_payload(root, dataset, "retrieval-c5", candidate_id)
    round_hit_details = _round_retrieval_details(retrieval_payload, hit_map)
    flattened_hits = [hit for rd in round_hit_details for hit in rd.get("hits", [])]
    mechanism, rationale = infer_mechanism(
        candidate_id=candidate_id,
        baseline_payload=baseline_payload,
        retrieval_payload=retrieval_payload,
        retrieval_hit_infos=flattened_hits,
    )
    report = {
        "candidate_id": candidate_id,
        "dataset": dataset,
        "model_family": _case_model_family(candidate_id),
        "baseline": None if baseline_payload is None else {
            "final_status": baseline_payload.get("final_status"),
            "round_count": baseline_payload.get("round_count"),
        },
        "retrieval": None if retrieval_payload is None else {
            "final_status": retrieval_payload.get("final_status"),
            "round_count": retrieval_payload.get("round_count"),
        },
        "transition": classify_outcome_transition(
            None if baseline_payload is None else baseline_payload.get("final_status"),
            None if retrieval_payload is None else retrieval_payload.get("final_status"),
        ),
        "first_divergence_round": first_divergence_round(
            [] if baseline_payload is None else list(baseline_payload.get("rounds") or []),
            [] if retrieval_payload is None else list(retrieval_payload.get("rounds") or []),
        ),
        "mechanism": mechanism,
        "rationale": rationale,
        "retrieval_rounds": round_hit_details,
    }
    return report


def aggregate_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    transition_counts: dict[str, int] = {}
    mechanism_counts: dict[str, int] = {}
    by_dataset: dict[str, dict[str, int]] = {}
    for report in reports:
        transition = str(report.get("transition") or "unknown")
        mechanism = str(report.get("mechanism") or "unknown")
        dataset = str(report.get("dataset") or "unknown")
        transition_counts[transition] = transition_counts.get(transition, 0) + 1
        mechanism_counts[mechanism] = mechanism_counts.get(mechanism, 0) + 1
        bucket = by_dataset.setdefault(dataset, {})
        bucket[transition] = bucket.get(transition, 0) + 1
    return {
        "case_count": len(reports),
        "transition_counts": transition_counts,
        "mechanism_counts": mechanism_counts,
        "by_dataset": by_dataset,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze retrieval attribution for v0.19.58")
    parser.add_argument(
        "--results-root",
        type=Path,
        default=REPO_ROOT / "artifacts" / "retrieval_trajectory_v0_19_58",
    )
    parser.add_argument(
        "--store-path",
        type=Path,
        default=REPO_ROOT / "artifacts" / "trajectory_store_v0_19_57" / "store.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "retrieval_attribution_v0_19_58",
    )
    parser.add_argument("--focus-only", action="store_true")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    store = _load_json(args.store_path)
    hit_map = _store_hit_map(store)

    reports: list[dict[str, Any]] = []
    for dataset in ("hot", "cold"):
        case_ids = _iter_case_ids(args.results_root, dataset)
        for candidate_id in case_ids:
            if args.focus_only and candidate_id not in FOCUS_CASES:
                continue
            report = analyze_case(
                candidate_id=candidate_id,
                dataset=dataset,
                root=args.results_root,
                hit_map=hit_map,
            )
            reports.append(report)
            (args.out_dir / f"{candidate_id}.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    summary = aggregate_summary(reports)
    summary["focus_cases"] = FOCUS_CASES
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
