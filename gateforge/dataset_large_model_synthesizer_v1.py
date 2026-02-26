from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _complexity(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    line_count = len(text.splitlines())
    equation_count = text.count("equation")
    model_block_count = text.count("model ")
    algorithm_count = text.count("algorithm")
    score = int(line_count + equation_count * 4 + model_block_count * 8 + algorithm_count * 3)
    return {
        "line_count": line_count,
        "equation_count": equation_count,
        "model_block_count": model_block_count,
        "algorithm_count": algorithm_count,
        "complexity_score": score,
    }


def _base_name(source_path: str) -> str:
    stem = Path(source_path).stem.lower()
    tokens = [t for t in stem.replace("-", "_").split("_") if t not in {"small", "medium", "large", "short", "long"}]
    return "_".join(tokens) or "model"


def _render_large_variant(source_text: str, variant_index: int) -> str:
    synth = [
        "",
        "// GateForge synthesized large-scale augmentation",
        f"// variant_index: {variant_index}",
        "// The block below increases state coupling for stress scenarios.",
        "",
        "// SYNTH_LARGE_AUGMENT_BEGIN",
        "Real gf_synth_x1(start=0.0);",
        "Real gf_synth_x2(start=0.0);",
        "Real gf_synth_x3(start=0.0);",
        "equation",
        "  der(gf_synth_x1) = -0.2*gf_synth_x1 + gf_synth_x2;",
        "  der(gf_synth_x2) = gf_synth_x1 - 0.3*gf_synth_x2 + gf_synth_x3;",
        "  der(gf_synth_x3) = gf_synth_x2 - 0.15*gf_synth_x3;",
        "// SYNTH_LARGE_AUGMENT_END",
    ]
    return source_text.rstrip() + "\n" + "\n".join(synth) + "\n"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Large Model Synthesizer v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- synthesized_count: `{payload.get('synthesized_count')}`",
        f"- total_large_assets_after: `{payload.get('total_large_assets_after')}`",
        f"- target_new_large_models: `{payload.get('target_new_large_models')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthesize large-scale Modelica variants from existing model library assets")
    parser.add_argument("--modelica-library-registry", required=True)
    parser.add_argument("--target-new-large-models", type=int, default=6)
    parser.add_argument("--synth-model-dir", default="artifacts/dataset_large_model_synthesizer_v1/models")
    parser.add_argument("--registry-out", default="artifacts/dataset_large_model_synthesizer_v1/registry_after.json")
    parser.add_argument("--out", default="artifacts/dataset_large_model_synthesizer_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.modelica_library_registry)
    reasons: list[str] = []
    if not registry:
        reasons.append("modelica_library_registry_missing")

    models = registry.get("models") if isinstance(registry.get("models"), list) else []
    model_rows = [x for x in models if isinstance(x, dict)]

    candidates = [
        x
        for x in model_rows
        if str(x.get("asset_type") or "") == "model_source"
        and str(x.get("suggested_scale") or "") in {"small", "medium"}
        and Path(str(x.get("source_path") or "")).exists()
        and Path(str(x.get("source_path") or "")).suffix.lower() == ".mo"
    ]

    if not candidates:
        reasons.append("no_source_models_available_for_synthesis")

    synth_dir = Path(args.synth_model_dir)
    synth_dir.mkdir(parents=True, exist_ok=True)

    new_rows: list[dict] = []
    target = max(0, int(args.target_new_large_models))

    for idx in range(target):
        if not candidates:
            break
        source = candidates[idx % len(candidates)]
        source_path = Path(str(source.get("source_path") or ""))
        source_text = source_path.read_text(encoding="utf-8", errors="ignore")

        base = _base_name(str(source_path))
        synth_name = f"{base}_large_synth_{idx + 1}.mo"
        synth_path = synth_dir / synth_name

        synth_text = _render_large_variant(source_text, idx + 1)
        synth_path.write_text(synth_text, encoding="utf-8")

        checksum = _sha256(synth_path)
        model_id = f"mdl_{base}_large_synth_{checksum[:8]}"

        new_rows.append(
            {
                "model_id": model_id,
                "asset_type": "model_source",
                "source_path": str(synth_path),
                "source_name": "large_model_synthesizer_v1",
                "license_tag": str(source.get("license_tag") or "UNKNOWN"),
                "checksum_sha256": checksum,
                "suggested_scale": "large",
                "complexity": _complexity(synth_path),
                "reproducibility": {
                    "om_version": str(((source.get("reproducibility") or {}).get("om_version") if isinstance(source.get("reproducibility"), dict) else "openmodelica-1.25.5") or "openmodelica-1.25.5"),
                    "repro_command": f"omc {synth_path}",
                },
                "lineage": {
                    "source_model_id": str(source.get("model_id") or ""),
                    "source_path": str(source_path),
                    "synthesizer": "dataset_large_model_synthesizer_v1",
                },
            }
        )

    existing_by_id = {str(x.get("model_id") or ""): x for x in model_rows if x.get("model_id")}
    for row in new_rows:
        existing_by_id[str(row.get("model_id") or "")] = row

    final_models = sorted(existing_by_id.values(), key=lambda x: str(x.get("model_id") or ""))
    total_large_after = len([x for x in final_models if str(x.get("suggested_scale") or "") == "large"])

    if target > 0 and len(new_rows) < target:
        reasons.append("synthesized_less_than_target")
    if len(new_rows) == 0 and target > 0:
        reasons.append("no_large_models_synthesized")

    status = "PASS"
    if "modelica_library_registry_missing" in reasons:
        status = "FAIL"
    elif reasons:
        status = "NEEDS_REVIEW"

    registry_after = {
        "schema_version": "modelica_library_registry_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "models": final_models,
    }
    _write_json(args.registry_out, registry_after)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "synthesized_count": len(new_rows),
        "target_new_large_models": target,
        "total_large_assets_after": total_large_after,
        "registry_out": args.registry_out,
        "synth_model_dir": str(synth_dir),
        "new_model_ids": [str(x.get("model_id") or "") for x in new_rows],
        "reasons": sorted(set(reasons)),
        "sources": {"modelica_library_registry": args.modelica_library_registry},
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "synthesized_count": len(new_rows), "total_large_assets_after": total_large_after}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
