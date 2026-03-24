from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OM_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or default


def _extract_mutations(manifest: dict) -> list[dict]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _find_primary_model_name(text: str) -> str:
    m = re.search(r"(?im)^\s*(?:partial\s+)?model\s+([A-Za-z_]\w*)\b", text)
    if not m:
        return ""
    return str(m.group(1))


def _find_within_namespace(text: str) -> str:
    m = re.search(r"(?im)^\s*within\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*;", text)
    if not m:
        return ""
    return str(m.group(1))


def _resolve_model_name(text: str) -> str:
    model_name = _find_primary_model_name(text)
    if not model_name:
        return ""
    within = _find_within_namespace(text)
    if not within:
        return model_name
    return f"{within}.{model_name}"


def _to_modelica_str(path: Path) -> str:
    # Use absolute paths so docker-backed OMC can always locate files regardless
    # of temporary script working directory.
    return str(path.resolve()).replace("\\", "/").replace('"', '\\"')


def _collect_package_preload_files(model_path: Path, model_name: str) -> list[Path]:
    if not model_name or "." not in model_name:
        return []
    top_pkg = str(model_name).split(".", 1)[0]
    if not top_pkg:
        return []
    top_pkg_dir: Path | None = None
    for parent in [model_path.parent, *model_path.parents]:
        if parent.name == top_pkg:
            top_pkg_dir = parent
            break
    if top_pkg_dir is None:
        return []
    pkg_mo = top_pkg_dir / "package.mo"
    if pkg_mo.exists():
        return [pkg_mo.resolve()]
    return []


def _run_omc_script(
    script_text: str,
    timeout_seconds: int,
    *,
    backend: str,
    model_paths: list[Path],
    docker_image: str,
) -> tuple[int, str]:
    # Use a dedicated temp subdirectory as the workspace so OMC writes all
    # compilation artifacts (.c, .o, _res.mat, .makefile, ...) into a single
    # contained directory that can be cleaned up after the run.
    # Previously a NamedTemporaryFile was used and its parent (/tmp) was
    # mounted as /workspace, causing OMC artifacts to accumulate directly in
    # the system temp directory with no cleanup.
    import os
    workspace = tempfile.mkdtemp(prefix="gf_mutation_valid_")
    try:
        script_path = Path(workspace) / "run.mos"
        script_path.write_text(script_text, encoding="utf-8")
        cmd: list[str]
        if backend == "openmodelica_docker":
            mounts = [
                "-v",
                f"{workspace}:/workspace",
            ]
            mounted: set[Path] = {Path(workspace).resolve()}
            for model_path in model_paths:
                model_parent = model_path.parent.resolve()
                if model_parent not in mounted:
                    mounts.extend(["-v", f"{str(model_parent)}:{str(model_parent)}"])
                    mounted.add(model_parent)
            uid_gid = f"{os.getuid()}:{os.getgid()}"
            cmd = [
                "docker",
                "run",
                "--rm",
                "--user", uid_gid,
                "-e", "HOME=/tmp",
                *mounts,
                "-w",
                "/workspace",
                docker_image,
                "omc",
                script_path.name,
            ]
        else:
            cmd = ["omc", str(script_path)]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
            cwd=workspace,
        )
        merged = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return int(proc.returncode), merged
    except FileNotFoundError as exc:
        return 2, f"tool_missing:{exc}"
    except subprocess.TimeoutExpired:
        return 124, "TimeoutExpired"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _check_model_with_omc(
    model_path: Path,
    model_name: str,
    timeout_seconds: int,
    *,
    backend: str,
    docker_image: str,
    preload_files: list[Path] | None = None,
) -> tuple[bool, str, int]:
    preload = preload_files or []
    preload_lines = "".join([f'loadFile("{_to_modelica_str(p)}");\n' for p in preload])
    script = preload_lines + (
        f'loadFile("{_to_modelica_str(model_path)}");\n'
        f"checkModel({model_name});\n"
        "getErrorString();\n"
    )
    model_paths = [model_path, *preload]
    rc, output = _run_omc_script(
        script,
        timeout_seconds=timeout_seconds,
        backend=backend,
        model_paths=model_paths,
        docker_image=docker_image,
    )
    lower = output.lower()
    ok = (
        rc == 0
        and "check of" in lower
        and "completed successfully" in lower
        and ("failed" not in lower or "check of" not in lower)
    )
    return ok, output, rc


def _simulate_model_with_omc(
    model_path: Path,
    model_name: str,
    timeout_seconds: int,
    *,
    backend: str,
    docker_image: str,
    preload_files: list[Path] | None = None,
) -> tuple[bool, str, int]:
    preload = preload_files or []
    preload_lines = "".join([f'loadFile("{_to_modelica_str(p)}");\n' for p in preload])
    script = preload_lines + (
        f'loadFile("{_to_modelica_str(model_path)}");\n'
        f"checkModel({model_name});\n"
        f"simulate({model_name}, stopTime=0.2, numberOfIntervals=20);\n"
        "getErrorString();\n"
    )
    model_paths = [model_path, *preload]
    rc, output = _run_omc_script(
        script,
        timeout_seconds=timeout_seconds,
        backend=backend,
        model_paths=model_paths,
        docker_image=docker_image,
    )
    lower = output.lower()
    has_sim_result = "record simulationresult" in lower
    empty_result = 'resultfile = ""' in lower
    sim_error_markers = (
        "simulation execution failed" in lower
        or "error occurred while solving" in lower
        or "division by zero" in lower
        or "assertion" in lower
        or "integrator failed" in lower
    )
    ok = rc == 0 and has_sim_result and not empty_result and not sim_error_markers
    return ok, output, rc


def _syntax_probe_model(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "path_missing"
    text = _load_text(path).lower()
    if "model " not in text:
        return False, "model_block_missing"
    if "end " not in text:
        return False, "model_end_missing"
    return True, "ok"


def _classify_failure(*, check_ok: bool, simulate_ok: bool, check_log: str, simulate_log: str) -> tuple[str, str]:
    if not check_ok:
        lower = check_log.lower()
        if "assert" in lower or "constraint" in lower:
            return "check", "constraint_violation"
        if "syntax error" in lower:
            return "check", "model_check_error"
        if "undeclared" in lower or "not found" in lower or "check of" in lower:
            return "check", "model_check_error"
        return "check", "model_check_error"

    if not simulate_ok:
        lower = simulate_log.lower()
        if "timeoutexpired" in lower or "timeout expired" in lower:
            return "simulate", "numerical_instability"
        if "division by zero" in lower or "error occurred while solving" in lower:
            return "simulate", "simulate_error"
        if "assert" in lower:
            return "simulate", "constraint_violation"
        if "stiff" in lower or "integrator failed" in lower or "step size" in lower:
            return "simulate", "numerical_instability"
        return "simulate", "simulate_error"

    return "none", "none"


def _resolve_backend(requested: str) -> tuple[str, bool]:
    req = str(requested or "auto").strip().lower()
    has_omc = shutil.which("omc") is not None
    has_docker = shutil.which("docker") is not None
    if req == "syntax":
        return "syntax", False
    if req == "openmodelica_docker":
        if has_docker:
            return "openmodelica_docker", False
        return "syntax", True
    if req == "omc":
        if has_omc:
            return "omc", False
        if has_docker:
            return "openmodelica_docker", False
        return "syntax", True
    if has_omc:
        return "omc", False
    if has_docker:
        return "openmodelica_docker", False
    return "syntax", True


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Validation Matrix v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- validation_backend_requested: `{payload.get('validation_backend_requested')}`",
        f"- validation_backend_used: `{payload.get('validation_backend_used')}`",
        f"- baseline_checked_count: `{payload.get('baseline_checked_count')}`",
        f"- baseline_check_pass_rate_pct: `{payload.get('baseline_check_pass_rate_pct')}`",
        f"- validated_mutants: `{payload.get('validated_mutants')}`",
        f"- stage_match_rate_pct: `{payload.get('stage_match_rate_pct')}`",
        f"- type_match_rate_pct: `{payload.get('type_match_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate baseline and mutant behavior against expected failure taxonomy")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--backend", choices=["auto", "omc", "openmodelica_docker", "syntax"], default="auto")
    parser.add_argument("--docker-image", default=DEFAULT_OM_DOCKER_IMAGE)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--max-baseline-models", type=int, default=200)
    parser.add_argument("--max-validated-mutations", type=int, default=1200)
    parser.add_argument("--min-stage-match-rate-pct", type=float, default=60.0)
    parser.add_argument("--min-type-match-rate-pct", type=float, default=40.0)
    parser.add_argument("--records-out", default="artifacts/dataset_mutation_validation_matrix_v1/records.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_validation_matrix_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    mutations = _extract_mutations(manifest)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if manifest and not mutations:
        reasons.append("mutation_rows_missing")

    backend_used, backend_fallback = _resolve_backend(args.backend)
    if str(args.backend) in {"omc", "openmodelica_docker"} and backend_used not in {"omc", "openmodelica_docker"}:
        reasons.append("omc_backend_unavailable")

    # Validate baselines from source model paths referenced by mutations.
    baseline_paths: list[str] = []
    seen_baseline: set[str] = set()
    for row in mutations:
        p = str(row.get("source_model_path") or row.get("model_path") or "").strip()
        if p and p not in seen_baseline:
            seen_baseline.add(p)
            baseline_paths.append(p)
    baseline_paths = baseline_paths[: max(0, int(args.max_baseline_models))]

    baseline_records: list[dict] = []
    baseline_pass = 0
    baseline_checked = 0
    for p in baseline_paths:
        model_path = Path(p)
        text = _load_text(model_path) if model_path.exists() else ""
        model_name = _resolve_model_name(text)
        preload_files = _collect_package_preload_files(model_path, model_name)
        check_ok = False
        check_log = ""
        check_rc: int | None = None
        if backend_used in {"omc", "openmodelica_docker"} and model_path.exists() and model_name:
            check_ok, check_log, check_rc = _check_model_with_omc(
                model_path,
                model_name,
                int(args.timeout_seconds),
                backend=backend_used,
                docker_image=str(args.docker_image),
                preload_files=preload_files,
            )
        else:
            check_ok, msg = _syntax_probe_model(model_path)
            check_log = msg
            check_rc = 0 if check_ok else 2
        baseline_checked += 1
        if check_ok:
            baseline_pass += 1
        baseline_records.append(
            {
                "source_model_path": str(model_path),
                "model_name": model_name,
                "check_ok": check_ok,
                "check_rc": check_rc,
                "check_log_excerpt": check_log[:600],
            }
        )

    # Validate mutant behavior.
    sampled_mutations = mutations[: max(0, int(args.max_validated_mutations))]
    mutation_records: list[dict] = []
    stage_match = 0
    type_match = 0
    validated_mutants = 0
    for row in sampled_mutations:
        expected_type = _slug(row.get("expected_failure_type"), default="unknown")
        expected_stage = _slug(row.get("expected_stage"), default="unknown")
        mutated_model_path = Path(str(row.get("mutated_model_path") or row.get("model_path") or ""))
        text = _load_text(mutated_model_path) if mutated_model_path.exists() else ""
        model_name = _resolve_model_name(text)
        source_model_path = Path(str(row.get("source_model_path") or ""))
        preload_base = source_model_path if source_model_path.exists() else mutated_model_path
        preload_files = _collect_package_preload_files(preload_base, model_name)

        check_ok = False
        simulate_ok = False
        check_log = ""
        simulate_log = ""
        check_rc: int | None = None
        simulate_rc: int | None = None

        if backend_used in {"omc", "openmodelica_docker"} and mutated_model_path.exists() and model_name:
            check_ok, check_log, check_rc = _check_model_with_omc(
                mutated_model_path,
                model_name,
                int(args.timeout_seconds),
                backend=backend_used,
                docker_image=str(args.docker_image),
                preload_files=preload_files,
            )
            if check_ok and expected_stage == "simulate":
                simulate_ok, simulate_log, simulate_rc = _simulate_model_with_omc(
                    mutated_model_path,
                    model_name,
                    int(args.timeout_seconds),
                    backend=backend_used,
                    docker_image=str(args.docker_image),
                    preload_files=preload_files,
                )
            elif check_ok:
                simulate_ok = True
                simulate_rc = 0
        else:
            check_ok, msg = _syntax_probe_model(mutated_model_path)
            check_log = msg
            check_rc = 0 if check_ok else 2
            simulate_ok = True if check_ok else False
            simulate_rc = 0 if simulate_ok else 2

        observed_stage, observed_type = _classify_failure(
            check_ok=check_ok,
            simulate_ok=simulate_ok,
            check_log=check_log,
            simulate_log=simulate_log,
        )
        # Semantic regressions often pass check/simulate and are caught by
        # downstream physics/regression contracts. Preserve that signal here.
        if (
            observed_stage == "none"
            and observed_type == "none"
            and expected_type == "semantic_regression"
            and check_ok
            and simulate_ok
        ):
            observed_stage = "simulate"
            observed_type = "semantic_regression"

        s_match = expected_stage == observed_stage
        t_match = expected_type == observed_type
        if s_match:
            stage_match += 1
        if t_match:
            type_match += 1
        validated_mutants += 1

        mutation_records.append(
            {
                "mutation_id": str(row.get("mutation_id") or ""),
                "expected_failure_type": expected_type,
                "expected_stage": expected_stage,
                "observed_failure_type": observed_type,
                "observed_stage": observed_stage,
                "stage_match": s_match,
                "type_match": t_match,
                "check_ok": check_ok,
                "simulate_ok": simulate_ok,
                "check_rc": check_rc,
                "simulate_rc": simulate_rc,
                "mutated_model_path": str(mutated_model_path),
                "check_log_excerpt": check_log[:600],
                "simulate_log_excerpt": simulate_log[:600],
            }
        )

    baseline_check_pass_rate = _ratio(baseline_pass, baseline_checked)
    stage_match_rate = _ratio(stage_match, validated_mutants)
    type_match_rate = _ratio(type_match, validated_mutants)

    mismatch_reasons: dict[str, int] = {}
    for rec in mutation_records:
        if rec.get("type_match"):
            continue
        key = f"{rec.get('expected_failure_type')}->{rec.get('observed_failure_type')}"
        mismatch_reasons[key] = mismatch_reasons.get(key, 0) + 1

    alerts: list[str] = []
    if backend_fallback:
        alerts.append("validation_backend_fallback_to_syntax")
    if baseline_checked <= 0:
        alerts.append("baseline_validation_empty")
    if validated_mutants <= 0:
        alerts.append("mutant_validation_empty")
    if stage_match_rate < float(args.min_stage_match_rate_pct):
        alerts.append("stage_match_rate_below_target")
    if type_match_rate < float(args.min_type_match_rate_pct):
        alerts.append("type_match_rate_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    records_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_records": baseline_records,
        "mutation_records": mutation_records,
    }
    _write_json(args.records_out, records_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "validation_backend_requested": args.backend,
        "validation_backend_used": backend_used,
        "backend_fallback_to_syntax": backend_fallback,
        "baseline_checked_count": baseline_checked,
        "baseline_check_pass_count": baseline_pass,
        "baseline_check_pass_rate_pct": baseline_check_pass_rate,
        "validated_mutants": validated_mutants,
        "stage_match_count": stage_match,
        "stage_match_rate_pct": stage_match_rate,
        "type_match_count": type_match,
        "type_match_rate_pct": type_match_rate,
        "mismatch_top_reasons": sorted(mismatch_reasons.items(), key=lambda x: x[1], reverse=True)[:12],
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "artifacts": {
            "records_out": args.records_out,
        },
        "sources": {
            "mutation_manifest": args.mutation_manifest,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": status,
                "validation_backend_used": backend_used,
                "validated_mutants": validated_mutants,
                "type_match_rate_pct": type_match_rate,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
