from __future__ import annotations

from agentplane_harbor_adapter.common import (
    BENCHMARK_EXECUTION_CONTRACT,
    GENERIC_AGENTPLANE_POLICY,
    PLANNING_EXECUTION_CONTRACT,
    ExecutorSpec,
    policy_hash,
    render_agentplane_command,
    render_proof_collection_command,
)
from agentplane_harbor_adapter.evaluator import EVALUATOR_SCRIPT


def test_policy_hash_is_stable_sha256() -> None:
    digest = policy_hash()

    assert len(digest) == 64
    assert "oracle" in GENERIC_AGENTPLANE_POLICY.lower()
    assert "internet" in GENERIC_AGENTPLANE_POLICY.lower()
    assert "never ask the user follow-up questions" in GENERIC_AGENTPLANE_POLICY
    assert "benchmark timeout" in GENERIC_AGENTPLANE_POLICY


def test_execution_contract_is_non_interactive() -> None:
    assert "Do not ask the user questions" in BENCHMARK_EXECUTION_CONTRACT
    assert "Do not ask for permission to continue" in BENCHMARK_EXECUTION_CONTRACT
    assert "User benchmark instruction:" in BENCHMARK_EXECUTION_CONTRACT


def test_planning_contract_requires_task_graph_artifacts() -> None:
    assert "planning phase" in PLANNING_EXECUTION_CONTRACT
    assert ".agentplane-harbor/agentplane/plan.json" in PLANNING_EXECUTION_CONTRACT
    assert ".agentplane-harbor/agentplane/task-graph.json" in PLANNING_EXECUTION_CONTRACT
    assert "atomic executable leaves" in PLANNING_EXECUTION_CONTRACT
    assert "Do not implement the solution in this phase" in PLANNING_EXECUTION_CONTRACT


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
    assert "agentplane task plan approve" in command
    assert "agentplane verify" in command
    assert "example run --model provider/model" in command
    assert "fix the task" in command
    assert "Do not ask for permission to continue" in command
    assert "executor-exit-code.txt" in command
    assert "executor.log" in command
    assert "Do not inspect oracle solutions" in command


def test_render_agentplane_command_has_runner_evaluator_repair_loop() -> None:
    executor = ExecutorSpec(
        agent_name="agentplane-test",
        npm_package="example",
        version_command="example --version",
        run_command_template="example run {model_flag} {instruction}",
        model_flag="--model",
        api_key_env="EXAMPLE_API_KEY",
    )

    command = render_agentplane_command("fix the task", executor, "provider/model")

    assert "run_evaluator()" in command
    assert 'REPAIR_ATTEMPTS="${AGENTPLANE_REPAIR_ATTEMPTS:-3}"' in command
    assert 'for ATTEMPT in $(seq 1 "$REPAIR_ATTEMPTS")' in command
    assert "executor-attempt-${ATTEMPT}.log" in command
    assert "evaluator-report.json" in command
    assert "evaluator-feedback.txt" in command
    assert "--rework" in command
    assert "Evaluator rejected attempt $ATTEMPT" in command
    assert "Do not read or run hidden graders in /tests" in command
    assert "Previous attempt failed the local evaluator" in command
    assert "does not look like a real MIPS/ELF interpreter" in command
    assert "appears to be a scaffold or fake frame generator" in command


def test_render_agentplane_command_has_planner_phase_gate() -> None:
    executor = ExecutorSpec(
        agent_name="agentplane-test",
        npm_package="example",
        version_command="example --version",
        run_command_template="example run {model_flag} {instruction}",
        model_flag="--model",
        api_key_env="EXAMPLE_API_KEY",
    )

    command = render_agentplane_command("fix the task", executor, "provider/model")

    assert 'PLAN_ATTEMPTS="${AGENTPLANE_PLAN_ATTEMPTS:-2}"' in command
    assert 'if [ "$PLAN_ATTEMPT" = "1" ]' in command
    assert 'eval "$PLANNER_COMMAND"' in command
    assert "=== AgentPlane planner attempt $PLAN_ATTEMPT ===" in command
    assert 'run_evaluator "$PLAN_ATTEMPT" "plan"' in command
    assert "Planner gate accepted attempt $PLAN_ATTEMPT" in command
    assert "Planner gate rejected attempt $PLAN_ATTEMPT" in command
    assert "Previous planning attempt failed the AgentPlane planner gate" in command
    assert "plan-evaluator-exit-code.txt" in command
    assert "planner-attempt-${PLAN_ATTEMPT}.log" in command
    assert "task-graph.json" in command
    assert "execute the atomic leaves in order" in command


def test_embedded_evaluator_has_structured_task_specific_checks() -> None:
    compile(EVALUATOR_SCRIPT, "embedded_evaluator.py", "exec")

    assert "evaluator-report.json" in EVALUATOR_SCRIPT
    assert "evaluate_plan" in EVALUATOR_SCRIPT
    assert "weak_task_decomposition" in EVALUATOR_SCRIPT
    assert "execute_task_graph_leaves_in_order" in EVALUATOR_SCRIPT
    assert "detect_task_type" in EVALUATOR_SCRIPT
    assert "overfull-hbox" in EVALUATOR_SCRIPT
    assert "build-pov-ray" in EVALUATOR_SCRIPT
    assert "circuit-fibsqrt" in EVALUATOR_SCRIPT
    assert "make-mips-interpreter" in EVALUATOR_SCRIPT
    assert "deterministic fibsqrt public oracle cases" in EVALUATOR_SCRIPT
    assert "circuit_cases" in EVALUATOR_SCRIPT
    assert "validate_bmp" in EVALUATOR_SCRIPT
    assert "complete_missing_interpreter_subsystems" in EVALUATOR_SCRIPT
    assert "modify_benchmark_timeout" in EVALUATOR_SCRIPT
    assert "Do not read or run hidden graders in /tests" in EVALUATOR_SCRIPT


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
