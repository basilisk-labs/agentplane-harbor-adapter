from __future__ import annotations

from agentplane_harbor_adapter.common import (
    GENERIC_AGENTPLANE_POLICY,
    ExecutorSpec,
    policy_hash,
    render_agentplane_command,
    render_proof_collection_command,
)


def test_policy_hash_is_stable_sha256() -> None:
    digest = policy_hash()

    assert len(digest) == 64
    assert "oracle" in GENERIC_AGENTPLANE_POLICY.lower()
    assert "internet" in GENERIC_AGENTPLANE_POLICY.lower()


def test_render_agentplane_command_uses_generic_policy_and_executor() -> None:
    executor = ExecutorSpec(
        agent_name="agentplane-test",
        npm_package="example",
        version_command="example --version",
        run_command_template="example run {model_flag} {instruction}",
        model_flag="--model",
        api_key_env="EXAMPLE_API_KEY",
    )

    command = render_agentplane_command("fix the task", executor, "provider/model")

    assert "agentplane init --yes" in command
    assert "agentplane task new" in command
    assert "agentplane verify" in command
    assert "example run --model provider/model 'fix the task'" in command
    assert "Do not inspect oracle solutions" in command


def test_render_proof_collection_command_records_integrity_flags() -> None:
    executor = ExecutorSpec(
        agent_name="agentplane-test",
        npm_package="example",
        version_command="example --version",
        run_command_template="example run {instruction}",
        model_flag="--model",
        api_key_env="EXAMPLE_API_KEY",
    )

    command = render_proof_collection_command(executor, "provider/model")

    assert ".agentplane-harbor/proof.json" in command
    assert '"modifies_benchmark_timeouts": false' in command
    assert '"uses_oracle_solutions": false' in command
    assert "git diff --binary" in command
