from inspection_gate.evidence_gates import Stage, execution_contract


def test_every_stage_has_evidence_command_and_unblock_path():
    for stage in Stage:
        contract = execution_contract(stage)
        assert contract["stage"] == stage.value
        assert contract["required_evidence"]
        assert contract["command"]
        assert contract["unblock_action"]
        assert "Fixture evidence" in contract["fixture_boundary"]


def test_contract_does_not_present_fixture_as_deployment_evidence():
    assert "cannot prove" in execution_contract(Stage.DEMO_CAPTURE)["fixture_boundary"]


def test_real_verification_commands_start_with_the_implemented_gate_cli():
    for stage in (Stage.EVALUATION, Stage.ONNX_PARITY, Stage.DOCKER_SMOKE, Stage.DEMO_CAPTURE):
        assert "scripts.check_evidence_gate" in execution_contract(stage)["command"]

