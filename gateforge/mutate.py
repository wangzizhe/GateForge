from __future__ import annotations

import argparse
import json
from pathlib import Path


MUTATION_TYPES = (
    "script_parse_error",
    "model_check_error",
    "simulate_error",
    "semantic_regression",
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _rel(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _expected_for(kind: str, backend: str) -> dict:
    if backend == "mock":
        return {
            "gate": "PASS",
            "failure_type": "none",
            "check_ok": True,
            "simulate_ok": True,
        }
    if kind == "script_parse_error":
        return {
            "gate": "FAIL",
            "failure_type": "script_parse_error",
            "check_ok": False,
            "simulate_ok": False,
        }
    if kind == "model_check_error":
        return {
            "gate": "FAIL",
            "failure_type": "model_check_error",
            "check_ok": False,
            "simulate_ok": False,
        }
    if kind == "simulate_error":
        return {
            "gate": "FAIL",
            "failure_type": "simulate_error",
            "check_ok": True,
            "simulate_ok": False,
        }
    return {
        "gate": "PASS",
        "failure_type": "none",
        "check_ok": True,
        "simulate_ok": True,
    }


def _make_case(index: int, kind: str, out_dir: Path, backend: str, repo_root: Path) -> dict:
    prefix = f"mut_{index:03d}_{kind}"
    script_path = out_dir / f"{prefix}.mos"
    files = [script_path]
    if kind == "script_parse_error":
        content = (
            'loadFile("examples/openmodelica/MinimalProbe.mo");\n'
            "checkModel(MinimalProbe);\n"
            "this_is_not_valid_syntax(\n"
            "simulate(MinimalProbe, stopTime = 1.0, numberOfIntervals = 20);\n"
            "getErrorString();\n"
        )
    elif kind == "model_check_error":
        model_name = f"MutBrokenCheck{index:03d}"
        model_path = out_dir / f"{model_name}.mo"
        files.append(model_path)
        _write_text(
            model_path,
            (
                f"model {model_name}\n"
                "  Real x;\n"
                "equation\n"
                "  der(x) = y;\n"
                f"end {model_name};\n"
            ),
        )
        content = (
            f'loadFile("{_rel(model_path, repo_root)}");\n'
            f"checkModel({model_name});\n"
            f"simulate({model_name}, stopTime = 1.0, numberOfIntervals = 20);\n"
            "getErrorString();\n"
        )
    elif kind == "simulate_error":
        model_name = f"MutSimFail{index:03d}"
        model_path = out_dir / f"{model_name}.mo"
        files.append(model_path)
        _write_text(
            model_path,
            (
                f"model {model_name}\n"
                "  Real x(start = 0.0);\n"
                "equation\n"
                "  der(x) = 1 / x;\n"
                f"end {model_name};\n"
            ),
        )
        content = (
            f'loadFile("{_rel(model_path, repo_root)}");\n'
            f"checkModel({model_name});\n"
            f"simulate({model_name}, stopTime = 1.0, numberOfIntervals = 40);\n"
            "getErrorString();\n"
        )
    else:
        content = (
            'loadFile("examples/openmodelica/MediumOscillator.mo");\n'
            "checkModel(MediumOscillator);\n"
            "simulate(MediumOscillator, stopTime=1.5, numberOfIntervals=60);\n"
            "getErrorString();\n"
        )
    _write_text(script_path, content)
    case_name = prefix
    rel_script = _rel(script_path, repo_root)
    expected = _expected_for(kind, backend)
    return {
        "name": case_name,
        "mutation_type": kind,
        "backend": backend,
        "script": rel_script,
        "expected": expected,
        "generated_files": [_rel(p, repo_root) for p in files],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mutation fixtures and benchmark pack")
    parser.add_argument("--out-dir", default="examples/mutants/v0", help="Where mutated scripts/models are written")
    parser.add_argument(
        "--manifest-out",
        default="artifacts/mutation_pack_v0/manifest.json",
        help="Where to write mutation manifest JSON",
    )
    parser.add_argument(
        "--pack-out",
        default="artifacts/mutation_pack_v0/pack.json",
        help="Where to write benchmark pack JSON",
    )
    parser.add_argument("--pack-id", default="mutation_pack_v0", help="Pack identifier")
    parser.add_argument(
        "--backend",
        default="openmodelica_docker",
        choices=["mock", "openmodelica", "openmodelica_docker"],
        help="Backend value written into generated pack",
    )
    parser.add_argument("--count", type=int, default=20, help="Number of mutation cases")
    args = parser.parse_args()

    if args.count <= 0:
        raise SystemExit("--count must be > 0")

    repo_root = Path.cwd()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Keep generated mutation directory deterministic across reruns.
    for p in out_dir.glob("*"):
        if p.is_file() and (p.suffix in {".mos", ".mo"}):
            p.unlink()

    cases: list[dict] = []
    for i in range(args.count):
        kind = MUTATION_TYPES[i % len(MUTATION_TYPES)]
        cases.append(_make_case(i + 1, kind, out_dir, args.backend, repo_root))

    manifest = {
        "schema_version": "0.1.0",
        "pack_id": args.pack_id,
        "backend": args.backend,
        "total_cases": len(cases),
        "mutation_types": sorted({c["mutation_type"] for c in cases}),
        "cases": cases,
    }
    pack = {
        "pack_id": args.pack_id,
        "backend": args.backend,
        "cases": [
            {
                "name": c["name"],
                "backend": c["backend"],
                "script": c["script"],
                "expected": c["expected"],
            }
            for c in cases
        ],
    }
    _write_json(Path(args.manifest_out), manifest)
    _write_json(Path(args.pack_out), pack)
    print(
        json.dumps(
            {
                "pack_id": args.pack_id,
                "backend": args.backend,
                "total_cases": len(cases),
                "manifest": args.manifest_out,
                "pack": args.pack_out,
            }
        )
    )


if __name__ == "__main__":
    main()
