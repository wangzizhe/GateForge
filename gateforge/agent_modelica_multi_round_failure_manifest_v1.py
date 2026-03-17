from __future__ import annotations

import json
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_multi_round_failure_pack_manifest_v1"
ALLOWED_SEEN_RISK_BANDS = ("known_public", "less_likely_seen", "hard_unseen")
ALLOWED_SOURCE_TYPES = ("public_repo", "research_artifact", "private_curated", "internal_mirror")


def _norm(value: object) -> str:
    return str(value or "").strip()


def load_multi_round_failure_manifest(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("multi-round failure manifest must be a JSON object")
    payload["_manifest_path"] = str(Path(path).resolve())
    return payload


def validate_multi_round_failure_manifest(payload: dict) -> tuple[list[dict], list[str]]:
    reasons: list[str] = []
    if _norm(payload.get("schema_version")) != SCHEMA_VERSION:
        reasons.append("schema_version_mismatch")
    libraries = payload.get("libraries")
    if not isinstance(libraries, list) or not libraries:
        reasons.append("libraries_missing")
        return [], reasons

    validated: list[dict] = []
    model_count = 0
    for idx, library in enumerate(libraries):
        if not isinstance(library, dict):
            reasons.append(f"library_invalid:{idx}")
            continue
        missing_library = [
            key
            for key in (
                "library_id",
                "package_name",
                "source_library",
                "license_provenance",
                "domain",
                "seen_risk_band",
                "source_type",
                "selection_reason",
                "exposure_notes",
            )
            if not _norm(library.get(key))
        ]
        if missing_library:
            reasons.append(f"library_missing_fields:{_norm(library.get('library_id')) or idx}:{','.join(missing_library)}")
            continue
        band = _norm(library.get("seen_risk_band")).lower()
        if band not in ALLOWED_SEEN_RISK_BANDS:
            reasons.append(f"library_seen_risk_band_invalid:{_norm(library.get('library_id'))}:{band}")
            continue
        source_type = _norm(library.get("source_type")).lower()
        if source_type not in ALLOWED_SOURCE_TYPES:
            reasons.append(f"library_source_type_invalid:{_norm(library.get('library_id'))}:{source_type}")
            continue
        models = library.get("allowed_models")
        if not isinstance(models, list) or not models:
            reasons.append(f"allowed_models_missing:{_norm(library.get('library_id'))}")
            continue
        checked_models: list[dict] = []
        for model in models:
            if not isinstance(model, dict):
                reasons.append(f"model_invalid:{_norm(library.get('library_id'))}")
                continue
            missing_model = [
                key
                for key in (
                    "model_id",
                    "qualified_model_name",
                    "model_path",
                    "seen_risk_band",
                    "source_type",
                    "selection_reason",
                    "exposure_notes",
                )
                if not _norm(model.get(key))
            ]
            if missing_model:
                reasons.append(
                    f"model_missing_fields:{_norm(library.get('library_id'))}:{_norm(model.get('model_id'))}:{','.join(missing_model)}"
                )
                continue
            model_band = _norm(model.get("seen_risk_band")).lower()
            if model_band not in ALLOWED_SEEN_RISK_BANDS:
                reasons.append(
                    f"model_seen_risk_band_invalid:{_norm(library.get('library_id'))}:{_norm(model.get('model_id'))}:{model_band}"
                )
                continue
            model_source_type = _norm(model.get("source_type")).lower()
            if model_source_type not in ALLOWED_SOURCE_TYPES:
                reasons.append(
                    f"model_source_type_invalid:{_norm(library.get('library_id'))}:{_norm(model.get('model_id'))}:{model_source_type}"
                )
                continue
            if not Path(_norm(model.get("model_path"))).exists():
                reasons.append(f"model_path_missing:{_norm(library.get('library_id'))}:{_norm(model.get('model_id'))}")
                continue
            checked_models.append(model)
            model_count += 1
        if checked_models:
            row = dict(library)
            row["allowed_models"] = checked_models
            validated.append(row)
    if len(validated) < 2:
        reasons.append("library_count_below_minimum")
    if model_count < 6:
        reasons.append("model_count_below_minimum")
    return validated, sorted(set(reasons))
