from __future__ import annotations

import hashlib
import json
import shlex
import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .evaluator import EVALUATOR_SCRIPT

DEFAULT_REPAIR_ATTEMPTS = 3

GENERIC_AGENTPLANE_POLICY = textwrap.dedent(
    """
    # AgentPlane Terminal-Bench Policy

    You are running inside an official benchmark sandbox.

    Rules:
    - Solve only the user-provided benchmark instruction.
    - Operate fully autonomously; never ask the user follow-up questions.
    - If information is missing, make a reasonable benchmark-safe assumption and continue.
    - Do not stop at a plan, diagnosis, or partial implementation when more execution is possible.
    - Treat local check failures as mandatory repair input.
    - Iterate until the task is solved, local verification passes, or the benchmark
      timeout stops you.
    - Before exiting, run the most relevant available check or smoke command for the task.
    - If the solution remains incomplete, leave the best final attempt in the workspace.
    - State any remaining failure in the executor log without requesting permission to
      continue.
    - Do not look up task solutions on the internet.
    - Do not inspect oracle solutions or hidden graders.
    - Do not modify benchmark timeouts, grader scripts, or reward files.
    - Keep changes scoped to the task workspace.
    - Run reasonable local verification when available.
    - Leave a clear final state for the benchmark grader.
    """
).strip()


BENCHMARK_EXECUTION_CONTRACT = textwrap.dedent(
    """
    You are in a non-interactive benchmark run.

    Execution contract:
    - Do not ask the user questions.
    - Do not ask for permission to continue.
    - Continue autonomously until you have produced the best final answer the grader can test.
    - Prefer executing and verifying over explaining possible next steps.
    - Treat any evaluator failure feedback as mandatory repair input.
    - If you cannot fully solve the task, leave your best working files in place and
      finish with a concise failure summary.

    User benchmark instruction:
    """
).strip()


@dataclass(frozen=True)
class ExecutorSpec:
    agent_name: str
    npm_package: str
    version_command: str
    run_command_template: str
    model_flag: str
    api_key_env: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def policy_hash() -> str:
    return hashlib.sha256(GENERIC_AGENTPLANE_POLICY.encode("utf-8")).hexdigest()


def shell_quote(value: str) -> str:
    return shlex.quote(value)


def json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def render_agentplane_command(
    instruction: str,
    executor: ExecutorSpec,
    model: str | None = None,
) -> str:
    benchmark_instruction = f"{BENCHMARK_EXECUTION_CONTRACT}\n\n{instruction}"
    quoted_instruction = shell_quote(benchmark_instruction)
    quoted_policy = shell_quote(GENERIC_AGENTPLANE_POLICY)
    model_flag = f"{executor.model_flag} {shell_quote(model)}" if model else ""
    repair_instruction = shell_quote(
        "Previous attempt failed the local evaluator. Continue from the current "
        "workspace state, read .agentplane-harbor/agentplane/evaluator-report.json "
        "and .agentplane-harbor/agentplane/evaluator-feedback.txt, fix the recorded "
        "failure, run a relevant check, and leave the best final state for the grader. "
        "Do not ask questions. If the same failure repeats, change strategy instead "
        "of making a narrow cosmetic edit.\n\nOriginal benchmark instruction:\n"
        f"{benchmark_instruction}"
    )
    initial_executor_command = executor.run_command_template.format(
        instruction=quoted_instruction,
        model_flag=model_flag,
    )
    repair_executor_command = executor.run_command_template.format(
        instruction=repair_instruction,
        model_flag=model_flag,
    )
    quoted_initial_executor_command = shell_quote(initial_executor_command)
    quoted_repair_executor_command = shell_quote(repair_executor_command)
    quoted_evaluator_script = shell_quote(EVALUATOR_SCRIPT)

    return textwrap.dedent(
        f"""
        set -euo pipefail
        mkdir -p .agentplane-harbor/agentplane
        printf '%s\n' {quoted_policy} > AGENTS.md
        printf '%s\n' {quoted_evaluator_script} > .agentplane-harbor/agentplane/evaluator.py
        chmod +x .agentplane-harbor/agentplane/evaluator.py

        agentplane init --yes || true
        TASK_ID="$(agentplane task new \
          --title "Terminal-Bench task" \
          --description "Solve one Terminal-Bench task under the AgentPlane Harbor adapter." \
          --priority med \
          --owner CODER \
          --tag benchmark | tail -n 1 | awk '{{print $1}}')"

        if [ -z "${{TASK_ID:-}}" ]; then
          TASK_ID="terminal-bench-task"
        fi

        agentplane task plan set "$TASK_ID" \
          --text "Plan: inspect, make scoped changes, run checks, and leave grader-ready state." \
          --updated-by CODER || true
        agentplane task plan approve "$TASK_ID" --by ORCHESTRATOR || true
        agentplane task start-ready "$TASK_ID" \
          --author CODER \
          --body "Start: Terminal-Bench run with generic AgentPlane policy." || true

        run_evaluator() {{
          set +e
          local attempt="$1"
          local python_bin
          python_bin="$(command -v python3 || command -v python || true)"
          if [ -z "$python_bin" ]; then
            echo "FAIL: python is unavailable for local evaluator." \
              > .agentplane-harbor/agentplane/evaluator-feedback.txt
            return 1
          fi
          "$python_bin" .agentplane-harbor/agentplane/evaluator.py \
            --attempt "$attempt" \
            --artifact-dir .agentplane-harbor/agentplane
          return "$?"
        }}

        record_rework() {{
          local note="$1"
          local impact="$2"
          local resolution="$3"
          local observation
          set +e
          observation="$(head -c 600 .agentplane-harbor/agentplane/evaluator-feedback.txt \
            2>/dev/null)"
          cp .agentplane-harbor/agentplane/evaluator-report.json \
            ".agentplane-harbor/agentplane/evaluator-report-rework-${{note//[^A-Za-z0-9]/_}}.json" \
            2>/dev/null || true
          agentplane verify "$TASK_ID" \
            --rework \
            --by EVALUATOR \
            --note "$note" \
            --observation "$observation" \
            --impact "$impact" \
            --resolution "$resolution" \
            --local-only
          set -e
          return 0
        }}

        REPAIR_ATTEMPTS="${{AGENTPLANE_REPAIR_ATTEMPTS:-{DEFAULT_REPAIR_ATTEMPTS}}}"
        if ! printf '%s' "$REPAIR_ATTEMPTS" | grep -Eq '^[1-9][0-9]*$'; then
          REPAIR_ATTEMPTS="{DEFAULT_REPAIR_ATTEMPTS}"
        fi

        RUNNER_EXIT_CODE=0
        EVALUATOR_EXIT_CODE=1
        for ATTEMPT in $(seq 1 "$REPAIR_ATTEMPTS"); do
          if [ "$ATTEMPT" = "1" ]; then
            EXECUTOR_COMMAND={quoted_initial_executor_command}
          else
            EXECUTOR_COMMAND={quoted_repair_executor_command}
          fi

          set +e
          {{
            echo "=== AgentPlane runner attempt $ATTEMPT ==="
            date -u
            eval "$EXECUTOR_COMMAND"
          }} > ".agentplane-harbor/agentplane/executor-attempt-${{ATTEMPT}}.log" 2>&1
          RUNNER_EXIT_CODE="$?"
          set -e
          cp ".agentplane-harbor/agentplane/executor-attempt-${{ATTEMPT}}.log" \
            .agentplane-harbor/agentplane/executor.log
          printf '%s\\n' "$RUNNER_EXIT_CODE" \
            > .agentplane-harbor/agentplane/executor-exit-code.txt

          set +e
          run_evaluator "$ATTEMPT"
          EVALUATOR_EXIT_CODE="$?"
          set -e
          printf '%s\\n' "$EVALUATOR_EXIT_CODE" \
            > .agentplane-harbor/agentplane/evaluator-exit-code.txt

          if [ "$EVALUATOR_EXIT_CODE" = "0" ]; then
            agentplane verify "$TASK_ID" \
              --ok \
              --by CODER \
              --note "Evaluator accepted attempt $ATTEMPT; official grader remains scoring truth." \
              --local-only || true
            break
          fi

          record_rework \
            "Evaluator rejected attempt $ATTEMPT." \
            "Runner must repair the current workspace before final grading." \
            "Retrying with evaluator feedback."
        done

        if [ "$EVALUATOR_EXIT_CODE" != "0" ]; then
          record_rework \
            "Evaluator still rejected the final attempt; leaving best workspace state." \
            "Official grader will score the best available failed state." \
            "Repair attempts exhausted."
        fi
        agentplane task show "$TASK_ID" > .agentplane-harbor/agentplane/task-show.txt 2>&1 || true
        agentplane task verify-show "$TASK_ID" \
          > .agentplane-harbor/agentplane/verify-show.txt 2>&1 || true
        exit 0
        """
    ).strip()


def render_proof_collection_command(executor: ExecutorSpec, model: str | None) -> str:
    proof = {
        "adapter": executor.agent_name,
        "model": model,
        "policy_sha256": policy_hash(),
        "ended_at": utc_now(),
        "integrity": {
            "generic_policy_only": True,
            "modifies_benchmark_timeouts": False,
            "uses_oracle_solutions": False,
            "uses_hidden_tests_as_context": False,
            "fetches_task_solutions": False,
        },
    }
    quoted_proof = shell_quote(json_dumps(proof))

    return textwrap.dedent(
        f"""
        set -euo pipefail
        mkdir -p .agentplane-harbor
        printf '%s\n' {quoted_proof} > .agentplane-harbor/proof.json
        {{
          echo "agentplane=$(agentplane --version 2>/dev/null || true)"
          echo "executor=$({executor.version_command} 2>/dev/null || true)"
          echo "node=$(node --version 2>/dev/null || true)"
          echo "npm=$(npm --version 2>/dev/null || true)"
          echo "git=$(git --version 2>/dev/null || true)"
        }} > .agentplane-harbor/versions.txt
        git status --short > .agentplane-harbor/git-status.txt 2>&1 || true
        git diff --binary > .agentplane-harbor/git-diff.patch 2>&1 || true
        """
    ).strip()
