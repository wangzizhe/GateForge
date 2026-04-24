from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_generation_taxonomy_v0_19_59 import (
    classify_trajectory_record,
    load_nl_tasks,
    parse_taxonomy_markdown,
    validate_generation_taxonomy,
)


class GenerationTaxonomyV01959Tests(unittest.TestCase):
    def test_parse_taxonomy_markdown_reads_bucket_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "taxonomy.md"
            path.write_text(
                "| bucket_id | name | stage | description | typical_signal |\n"
                "|---|---|---|---|---|\n"
                "| ET01 | syntax_parse_error | parse | Syntax issue. | Parser error |\n"
                "| ET02 | missing_class | lookup | Missing class. | Class not found |\n",
                encoding="utf-8",
            )

            buckets = parse_taxonomy_markdown(path)

        self.assertEqual([bucket.bucket_id for bucket in buckets], ["ET01", "ET02"])

    def test_load_nl_tasks_reads_task_list_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool = Path(tmp)
            (pool / "tasks.json").write_text(
                json.dumps({"tasks": [{"task_id": "a"}, {"task_id": "b"}]}),
                encoding="utf-8",
            )

            tasks = load_nl_tasks(pool)

        self.assertEqual([task["task_id"] for task in tasks], ["a", "b"])

    def test_classify_known_trajectory_shapes(self) -> None:
        self.assertEqual(
            classify_trajectory_record(
                {
                    "candidate_id": "v01945_HydroTurbineGov_v0_pp_r__pv_pmech0+p",
                    "failure_type": "constraint_violation",
                }
            ),
            "ET17",
        )
        self.assertEqual(
            classify_trajectory_record(
                {
                    "candidate_id": "v01912_underdet_small_rc_missing_ground",
                    "benchmark_family": "underdetermined_missing_ground",
                    "observed_error_sequence": ["simulate_error", "none"],
                }
            ),
            "ET06",
        )
        self.assertEqual(
            classify_trajectory_record(
                {
                    "candidate_id": "v01914_shortcirc_small_rc",
                    "benchmark_family": "spurious_short_circuit",
                    "observed_error_sequence": ["simulate_error", "none"],
                }
            ),
            "ET08",
        )
        self.assertEqual(
            classify_trajectory_record(
                {
                    "candidate_id": "v01911_overdet_small_rc_kvl",
                    "mutation_mechanism": "redundant_kvl_equation",
                }
            ),
            "ET07",
        )

    def test_validate_generation_taxonomy_reports_pass_on_minimal_complete_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            taxonomy = root / "taxonomy.md"
            rows = [
                f"| ET{i:02d} | bucket_{i:02d} | stage | description | signal |"
                for i in range(1, 18)
            ]
            taxonomy.write_text(
                "| bucket_id | name | stage | description | typical_signal |\n"
                "|---|---|---|---|---|\n"
                + "\n".join(rows)
                + "\n",
                encoding="utf-8",
            )
            mapping = root / "mapping.md"
            mapping.write_text(
                "| taxonomy_bucket | existing_mutation_family | mapping_status | notes |\n"
                "|---|---|---|---|\n"
                + "\n".join(f"| ET{i:02d} bucket | family | strong | note |" for i in range(1, 18))
                + "\n",
                encoding="utf-8",
            )
            pool = root / "pool"
            pool.mkdir()
            tasks = [
                {
                    "task_id": f"task_{idx}",
                    "difficulty": f"T{(idx % 5) + 1}",
                    "domain": f"domain_{idx % 4}",
                }
                for idx in range(15)
            ]
            (pool / "tasks.json").write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
            trajectory = root / "trajectory.json"
            trajectory.write_text(
                json.dumps(
                    {
                        "summaries": [
                            {
                                "candidate_id": f"case_{idx}_underdet_missing_ground",
                                "benchmark_family": "underdetermined_missing_ground",
                            }
                            for idx in range(50)
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_generation_taxonomy(
                taxonomy_path=taxonomy,
                nl_task_pool_dir=pool,
                mapping_path=mapping,
                trajectory_sources=[trajectory],
            )

        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["trajectory_sample_count"], 50)
        self.assertEqual(payload["unclassified_count"], 0)


if __name__ == "__main__":
    unittest.main()
