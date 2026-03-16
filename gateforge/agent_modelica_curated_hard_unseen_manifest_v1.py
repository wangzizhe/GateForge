from __future__ import annotations

import json
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_curated_hard_unseen_pool_manifest_v1"
ALLOWED_SEEN_RISK_BANDS = ("known_public", "less_likely_seen", "hard_unseen")
ALLOWED_SOURCE_TYPES = ("public_repo", "research_artifact", "private_curated", "internal_mirror")
REQUIRED_LIBRARY_KEYS = (
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
REQUIRED_MODEL_KEYS = (
    "model_id",
    "qualified_model_name",
    "model_path",
    "seen_risk_band",
    "source_type",
    "selection_reason",
    "exposure_notes",
)


def load_curated_hard_unseen_manifest(path: str) -> dict:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    payload["_manifest_path"] = str(manifest_path.resolve())
    return payload


def _norm(value: object) -> str:
    return str(value or "").strip()


def _resolve_path(base_dir: Path, raw_path: object) -> Path:
    candidate = Path(_norm(raw_path))
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def _package_prefixes(package_name: str) -> list[str]:
    parts = [part.strip().lower() for part in str(package_name or "").split(".") if part.strip()]
    return [".".join(parts[:idx]) for idx in range(1, len(parts) + 1)]


def validate_curated_hard_unseen_manifest(payload: dict) -> tuple[list[dict], list[str]]:
    if not isinstance(payload, dict):
        return [], ["manifest_not_object"]

    reasons: list[str] = []
    if _norm(payload.get("schema_version")) != SCHEMA_VERSION:
        reasons.append("schema_version_invalid")

    manifest_path = Path(_norm(payload.get("_manifest_path")) or ".").resolve()
    base_dir = manifest_path.parent
    libraries = payload.get("libraries") if isinstance(payload.get("libraries"), list) else []
    if not libraries:
        reasons.append("libraries_missing")
        return [], reasons

    normalized: list[dict] = []
    seen_library_ids: set[str] = set()
    total_models = 0

    for idx, library in enumerate(libraries):
        if not isinstance(library, dict):
            reasons.append(f"library_row_not_object:{idx}")
            continue
        row = dict(library)
        library_id = _norm(row.get("library_id")).lower()
        for key in REQUIRED_LIBRARY_KEYS:
            if not _norm(row.get(key)):
                reasons.append(f"library_missing_field:{library_id or idx}:{key}")
        if not _norm(row.get("local_path")) and not _norm(row.get("accepted_source_path")):
            reasons.append(f"library_missing_field:{library_id or idx}:local_path_or_accepted_source_path")
        if library_id in seen_library_ids:
            reasons.append(f"library_id_duplicate:{library_id}")
        seen_library_ids.add(library_id)

        seen_risk_band = _norm(row.get("seen_risk_band")).lower()
        if seen_risk_band not in ALLOWED_SEEN_RISK_BANDS:
            reasons.append(f"library_seen_risk_band_invalid:{library_id}:{seen_risk_band}")
        source_type = _norm(row.get("source_type")).lower()
        if source_type not in ALLOWED_SOURCE_TYPES:
            reasons.append(f"library_source_type_invalid:{library_id}:{source_type}")

        local_path = _norm(row.get("local_path"))
        accepted_source_path = _norm(row.get("accepted_source_path"))
        if local_path:
            row["local_path"] = str(_resolve_path(base_dir, local_path))
        if accepted_source_path:
            row["accepted_source_path"] = str(_resolve_path(base_dir, accepted_source_path))

        package_name = _norm(row.get("package_name"))
        library_hints = [str(x) for x in (row.get("library_hints") or []) if isinstance(x, str)]
        row["library_hints"] = sorted({*library_hints, *_package_prefixes(package_name), library_id})

        models = row.get("allowed_models") if isinstance(row.get("allowed_models"), list) else []
        if len(models) < 2:
            reasons.append(f"library_has_insufficient_models:{library_id}")

        normalized_models: list[dict] = []
        seen_model_ids: set[str] = set()
        for model_idx, model in enumerate(models):
            if not isinstance(model, dict):
                reasons.append(f"model_row_not_object:{library_id}:{model_idx}")
                continue
            model_row = dict(model)
            model_id = _norm(model_row.get("model_id")).lower()
            for key in REQUIRED_MODEL_KEYS:
                if not _norm(model_row.get(key)):
                    reasons.append(f"model_missing_field:{library_id}:{model_id or model_idx}:{key}")
            if model_id in seen_model_ids:
                reasons.append(f"model_id_duplicate:{library_id}:{model_id}")
            seen_model_ids.add(model_id)

            model_seen_risk_band = _norm(model_row.get("seen_risk_band")).lower()
            if model_seen_risk_band not in ALLOWED_SEEN_RISK_BANDS:
                reasons.append(f"model_seen_risk_band_invalid:{library_id}:{model_id}:{model_seen_risk_band}")
            model_source_type = _norm(model_row.get("source_type")).lower()
            if model_source_type not in ALLOWED_SOURCE_TYPES:
                reasons.append(f"model_source_type_invalid:{library_id}:{model_id}:{model_source_type}")

            model_path = _resolve_path(base_dir, model_row.get("model_path"))
            model_row["model_path"] = str(model_path)
            if not model_path.exists():
                reasons.append(f"model_path_missing:{library_id}:{model_id}")
            normalized_models.append(model_row)
            total_models += 1

        row["allowed_models"] = normalized_models
        normalized.append(row)

    if len(normalized) < 2:
        reasons.append("library_count_below_minimum")
    if total_models < 6:
        reasons.append("model_count_below_minimum")
    return normalized, sorted(set(reasons))
