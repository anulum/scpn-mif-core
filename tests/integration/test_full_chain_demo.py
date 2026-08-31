# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""Real sibling + Rust stochastic + Verilator full-chain integration gate."""

from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from scpn_mif_core.cli import DEMO_SCENARIO, main, scenario_from_mapping
from scpn_mif_core.full_chain import (
    FullChainCaseResult,
    FullChainError,
    evaluate_neuro_symbolic_admission,
    evaluate_pulsed_scheduler_admission,
    run_full_chain_demo,
    verify_full_chain_replay,
)
from scpn_mif_core.full_chain.rtl import build_trigger_fabric
from scpn_mif_core.merge_trigger import evaluate_merge_trigger

pytestmark = pytest.mark.full_chain


@pytest.fixture(scope="module")
def evidence(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the public CLI once; missing ecosystem dependencies fail this gate."""
    output = tmp_path_factory.mktemp("fusion-to-fire") / "evidence"
    assert main(["full-chain", "--output", str(output)]) == 0
    return output


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_no_json_float(value: Any) -> None:
    assert not isinstance(value, float)
    if isinstance(value, list):
        for item in value:
            _assert_no_json_float(item)
    elif isinstance(value, dict):
        for item in value.values():
            _assert_no_json_float(item)


def test_nominal_case_causes_exactly_one_rtl_trigger_then_fusion_actuation(evidence: Path) -> None:
    nominal = _load(evidence / "nominal.json")
    assert nominal["mif_outcome"] == "fire"
    assert nominal["control_neuro_symbolic"]["backend"] == "rust"
    assert nominal["control_neuro_symbolic"]["execution_mode"] == "stateless_transition_gate"
    assert nominal["control_neuro_symbolic"]["state_lifecycle"] == ("reset_before_single_transition_evaluation")
    assert nominal["control_neuro_symbolic"]["temporal_state_preserved"] is False
    assert nominal["control_neuro_symbolic"]["fidelity_boundary"] == (
        "threshold permit only; no temporal LIF-dynamics claim"
    )
    assert nominal["control_neuro_symbolic"]["formal_fire_reachable"] is True
    assert nominal["control_scheduler"]["permit"] is True
    assert nominal["control_permit"] is True
    assert nominal["rtl"]["bit_true"] is True
    assert nominal["rtl_trigger_count"] == 1
    assert nominal["fusion"]["actuator_invoked"] is True
    assert float(nominal["fusion"]["compression_ratio"]) > 1.0
    assert float(nominal["fusion"]["recovered_energy_J"]) > 0.0


def test_safety_fault_vetoes_every_rtl_cycle_and_never_invokes_fusion(evidence: Path) -> None:
    veto = _load(evidence / "safety_veto.json")
    assert veto["mif_outcome"] == "abort_unsafe"
    assert veto["mif_safety_passed"] is False
    assert veto["control_neuro_symbolic"]["execution_mode"] == "stateless_transition_gate"
    assert veto["control_neuro_symbolic"]["temporal_state_preserved"] is False
    assert veto["control_neuro_symbolic"]["formal_marking_bounds_hold"] is True
    assert veto["control_neuro_symbolic"]["formal_fire_reachable"] is False
    assert veto["control_scheduler"]["permit"] is True
    assert veto["control_permit"] is False
    assert all(cycle["safety_veto"] for cycle in veto["rtl"]["cycles"])
    assert veto["rtl"]["bit_true"] is True
    assert veto["rtl_trigger_count"] == 0
    assert veto["fusion"] == {
        "actuator_invoked": False,
        "coil_command_A": "0",
        "reason": "fail-closed: no unanimous MIF, CONTROL and RTL fire admission",
    }


def test_manifest_binds_all_artifacts_and_preserves_claim_boundaries(evidence: Path) -> None:
    manifest = _load(evidence / "chain_manifest.json")
    for name, digest in manifest["artifacts"].items():
        assert _sha256(evidence / name) == digest
    assert manifest["replay"] == {
        "fusion_trajectory_bit_identical": True,
        "nominal_bit_identical": True,
        "safety_veto_bit_identical": True,
    }
    assert manifest["claims"]["cosim"] == "local-verilator"
    assert manifest["claims"]["timing_post_route"] == "hardware-gated-not-claimed"
    assert manifest["claims"]["hil"] == "hardware-gated-not-claimed"
    assert len(manifest["repositories"]) == 4
    assert all(len(record["sha"]) == 40 for record in manifest["repositories"].values())


def test_evidence_json_is_float_free_and_trajectory_is_pickle_free(evidence: Path) -> None:
    for name in ("nominal.json", "safety_veto.json", "chain_manifest.json"):
        _assert_no_json_float(_load(evidence / name))
    with np.load(evidence / "fusion_trajectory.npz", allow_pickle=False) as trajectory:
        assert set(trajectory.files) == {
            "magnetic_field_T",
            "magnetic_field_rate_T_s",
            "radial_velocity_m_s",
            "radius_m",
            "time_s",
        }
        assert bool(np.all(np.diff(trajectory["time_s"]) > 0.0))
        assert float(trajectory["radius_m"][-1]) < float(trajectory["radius_m"][0])


def test_cli_refuses_to_overwrite_existing_evidence(
    evidence: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["full-chain", "--output", str(evidence)]) == 2
    assert "output directory must be empty" in capsys.readouterr().err


def test_public_runtime_rejects_file_output_and_wrong_checkout_root(tmp_path: Path) -> None:
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("occupied", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory"):
        run_full_chain_demo(output_file)
    with pytest.raises(RuntimeError, match="not imported from selected checkout"):
        run_full_chain_demo(tmp_path / "unused-output", code_root=tmp_path)


def test_public_runtime_rejects_an_unrunnable_verilator(tmp_path: Path) -> None:
    empty_output = tmp_path / "empty-output"
    empty_output.mkdir()
    with pytest.raises(RuntimeError, match="not runnable"):
        run_full_chain_demo(empty_output, verilator=tmp_path / "absent-verilator")


def test_public_control_admissions_fail_closed_on_a_real_no_lock_report() -> None:
    scenario_data = deepcopy(DEMO_SCENARIO)
    scenario_data["merge_window"]["consecutive_samples"] = 300
    report = evaluate_merge_trigger(scenario_from_mapping(scenario_data))
    assert report.lock_achieved is False

    neuro = evaluate_neuro_symbolic_admission(report)
    scheduler = evaluate_pulsed_scheduler_admission(report)
    assert neuro["backend"] == "rust"
    assert neuro["stochastic_permit"] is False
    assert neuro["formal_fire_reachable"] is False
    assert scheduler["permit"] is False


def test_control_transition_gate_does_not_accumulate_membrane_state_between_calls() -> None:
    """Bind the current CONTROL API to its documented stateless gate semantics."""
    from scpn_control.scpn import FusionCompiler, StochasticPetriNet

    net = StochasticPetriNet()
    net.add_place("input", initial_tokens=0.5)
    net.add_place("output", initial_tokens=0.0)
    net.add_transition("gate", threshold=0.8)
    net.add_arc("input", "gate", weight=1.0)
    net.add_arc("gate", "output", weight=1.0)
    compiled = FusionCompiler(bitstream_length=64, seed=1).compile(net)
    subthreshold_current = np.asarray([0.5], dtype=np.float64)

    observed = [float(compiled.lif_fire(subthreshold_current)[0]) for _ in range(3)]

    assert observed == [0.0, 0.0, 0.0]


def test_public_neuro_symbolic_admission_rejects_non_rust_execution() -> None:
    report = evaluate_merge_trigger(scenario_from_mapping(DEMO_SCENARIO))
    with pytest.raises(FullChainError, match="dense permit path requires the SC-NeuroCore Rust backend"):
        evaluate_neuro_symbolic_admission(report, backend_name="numpy")


def test_verilator_builder_rejects_missing_and_malformed_tracked_sources(tmp_path: Path) -> None:
    verilator = shutil.which("verilator")
    assert verilator is not None
    with pytest.raises(RuntimeError, match="tracked RTL source is missing"):
        build_trigger_fabric(tmp_path, tmp_path / "missing-build", verilator=verilator)

    malformed = tmp_path / "malformed"
    rtl = malformed / "hdl" / "src" / "triggers"
    fixture = malformed / "hdl" / "sim"
    rtl.mkdir(parents=True)
    fixture.mkdir(parents=True)
    (rtl / "mif_trigger_fabric.sv").write_text("this is not SystemVerilog\n", encoding="utf-8")
    (fixture / "mif_trigger_fabric_tb.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="build failed"):
        build_trigger_fabric(malformed, tmp_path / "malformed-build", verilator=verilator)


def test_verilator_builder_rejects_success_without_the_expected_binary(tmp_path: Path) -> None:
    true = shutil.which("true")
    assert true is not None
    repo = Path(__file__).resolve().parents[2]
    with pytest.raises(RuntimeError, match="emitted no trigger-fabric binary"):
        build_trigger_fabric(repo, tmp_path / "empty-build", verilator=true)


def test_replay_verifier_rejects_tampered_real_evidence(evidence: Path) -> None:
    payload = _load(evidence / "nominal.json")
    with np.load(evidence / "fusion_trajectory.npz", allow_pickle=False) as loaded:
        arrays = {name: loaded[name].copy() for name in loaded.files}
    original = FullChainCaseResult(payload=payload, fusion_trajectory=arrays)
    verify_full_chain_replay(original, original)

    changed_payload = dict(payload)
    changed_payload["mif_outcome"] = "tampered"
    with pytest.raises(RuntimeError, match="payload was not deterministic"):
        verify_full_chain_replay(original, FullChainCaseResult(changed_payload, arrays))
    with pytest.raises(RuntimeError, match="presence changed"):
        verify_full_chain_replay(original, FullChainCaseResult(payload, None))

    missing_channel = dict(arrays)
    missing_channel.pop("radius_m")
    with pytest.raises(RuntimeError, match="channels changed"):
        verify_full_chain_replay(original, FullChainCaseResult(payload, missing_channel))

    changed_arrays = dict(arrays)
    changed_arrays["radius_m"] = arrays["radius_m"].copy()
    changed_arrays["radius_m"][0] += 1.0
    with pytest.raises(RuntimeError, match=r"radius_m.*not bit-identical"):
        verify_full_chain_replay(original, FullChainCaseResult(payload, changed_arrays))


def test_cli_json_mode_runs_the_same_real_chain(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "json-evidence"
    code_root = Path(__file__).resolve().parents[3]
    assert main(["full-chain", "--output", str(output), "--code-root", str(code_root), "--json"]) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["demo"] == "Fusion-to-Fire"
    assert manifest == _load(output / "chain_manifest.json")
