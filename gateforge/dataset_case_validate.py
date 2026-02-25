from __future__ import annotations

import argparse
import json

from .dataset_case import load_dataset_case, validate_dataset_case


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate GateForge dataset case JSON")
    parser.add_argument("--in", dest="input_path", required=True, help="Path to dataset case JSON")
    parser.add_argument("--out", default=None, help="Optional path to write validation result JSON")
    args = parser.parse_args()

    try:
        payload = load_dataset_case(args.input_path)
        validate_dataset_case(payload)
        result = {"valid": True, "case_id": payload["case_id"]}
        exit_code = 0
    except Exception as exc:  # noqa: BLE001
        result = {"valid": False, "error": str(exc)}
        exit_code = 1

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(json.dumps(result, indent=2))
    print(json.dumps(result))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
