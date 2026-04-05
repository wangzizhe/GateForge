from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_4_6_closeout import build_v046_closeout
from gateforge.agent_modelica_v0_4_6_deferred_question_audit import build_v046_deferred_question_audit
from gateforge.agent_modelica_v0_4_6_phase_ledger import build_v046_phase_ledger
from gateforge.agent_modelica_v0_4_6_stop_condition_audit import build_v046_stop_condition_audit
from gateforge.agent_modelica_v0_4_6_v0_5_handoff import build_v046_v0_5_handoff


class AgentModelicaV046PhaseSynthesisFlowTests(unittest.TestCase):
    def _write_closeout(self, path: Path, version_decision: str, extra: dict | None = None) -> None:
        payload = {"conclusion": {"version_decision": version_decision}}
        if extra:
            payload["conclusion"].update(extra)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v046_reaches_prepare_v0_5_when_all_stop_conditions_are_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_closeout(root / "v040" / "summary.json", "v0_4_0_conditioning_substrate_partial")
            self._write_closeout(root / "v041" / "summary.json", "v0_4_1_stage2_conditioning_signal_ready")
            self._write_closeout(root / "v042" / "summary.json", "v0_4_2_synthetic_gain_supported_real_backcheck_partial", {"conditioning_gain_supported": True})
            self._write_closeout(root / "v043" / "summary.json", "v0_4_3_real_backcheck_supported", {"real_backcheck_status": "supported"})
            self._write_closeout(root / "v044" / "summary.json", "v0_4_4_real_authority_promoted")
            self._write_closeout(root / "v045" / "summary.json", "v0_4_5_dispatch_policy_empirically_supported", {"dispatch_policy_support_status": "empirically_supported"})

            build_v046_phase_ledger(
                v040_closeout_path=str(root / "v040" / "summary.json"),
                v041_closeout_path=str(root / "v041" / "summary.json"),
                v042_closeout_path=str(root / "v042" / "summary.json"),
                v043_closeout_path=str(root / "v043" / "summary.json"),
                v044_closeout_path=str(root / "v044" / "summary.json"),
                v045_closeout_path=str(root / "v045" / "summary.json"),
                out_dir=str(root / "ledger"),
            )
            build_v046_stop_condition_audit(
                v042_closeout_path=str(root / "v042" / "summary.json"),
                v043_closeout_path=str(root / "v043" / "summary.json"),
                v045_closeout_path=str(root / "v045" / "summary.json"),
                out_dir=str(root / "audit"),
            )
            build_v046_deferred_question_audit(out_dir=str(root / "deferred"))
            build_v046_v0_5_handoff(
                stop_audit_path=str(root / "audit" / "summary.json"),
                deferred_question_audit_path=str(root / "deferred" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            payload = build_v046_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_audit_path=str(root / "audit" / "summary.json"),
                deferred_question_audit_path=str(root / "deferred" / "summary.json"),
                v0_5_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_phase_complete_prepare_v0_5")
            self.assertTrue((payload.get("conclusion") or {}).get("deferred_questions_non_blocking"))

    def test_v046_does_not_close_phase_when_dispatch_support_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_closeout(root / "v040" / "summary.json", "v0_4_0_conditioning_substrate_partial")
            self._write_closeout(root / "v041" / "summary.json", "v0_4_1_stage2_conditioning_signal_ready")
            self._write_closeout(root / "v042" / "summary.json", "v0_4_2_synthetic_gain_supported_real_backcheck_partial", {"conditioning_gain_supported": True})
            self._write_closeout(root / "v043" / "summary.json", "v0_4_3_real_backcheck_supported", {"real_backcheck_status": "supported"})
            self._write_closeout(root / "v044" / "summary.json", "v0_4_4_real_authority_promoted")
            self._write_closeout(root / "v045" / "summary.json", "v0_4_5_dispatch_policy_inconclusive", {"dispatch_policy_support_status": "inconclusive"})

            build_v046_phase_ledger(
                v040_closeout_path=str(root / "v040" / "summary.json"),
                v041_closeout_path=str(root / "v041" / "summary.json"),
                v042_closeout_path=str(root / "v042" / "summary.json"),
                v043_closeout_path=str(root / "v043" / "summary.json"),
                v044_closeout_path=str(root / "v044" / "summary.json"),
                v045_closeout_path=str(root / "v045" / "summary.json"),
                out_dir=str(root / "ledger"),
            )
            build_v046_stop_condition_audit(
                v042_closeout_path=str(root / "v042" / "summary.json"),
                v043_closeout_path=str(root / "v043" / "summary.json"),
                v045_closeout_path=str(root / "v045" / "summary.json"),
                out_dir=str(root / "audit"),
            )
            build_v046_deferred_question_audit(out_dir=str(root / "deferred"))
            build_v046_v0_5_handoff(
                stop_audit_path=str(root / "audit" / "summary.json"),
                deferred_question_audit_path=str(root / "deferred" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            payload = build_v046_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_audit_path=str(root / "audit" / "summary.json"),
                deferred_question_audit_path=str(root / "deferred" / "summary.json"),
                v0_5_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_phase_not_ready_for_closeout")


if __name__ == "__main__":
    unittest.main()
