from __future__ import annotations

import hashlib
import json
import shlex
import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

GENERIC_AGENTPLANE_POLICY = textwrap.dedent(
    """
    # AgentPlane Terminal-Bench Policy

    You are running inside an official benchmark sandbox.

    Rules:
    - Solve only the user-provided benchmark instruction.
    - Do not look up task solutions on the internet.
    - Do not inspect oracle solutions or hidden graders.
    - Do not modify benchmark timeouts, grader scripts, or reward files.
    - Keep changes scoped to the task workspace.
    - Run reasonable local verification when available.
    - Leave a clear final state for the benchmark grader.
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
    quoted_instruction = shell_quote(instruction)
    quoted_policy = shell_quote(GENERIC_AGENTPLANE_POLICY)
    model_flag = f"{executor.model_flag} {shell_quote(model)}" if model else ""
    executor_command = executor.run_command_template.format(
        instruction=quoted_instruction,
        model_flag=model_flag,
    )

    return textwrap.dedent(
        f"""
        set -euo pipefail
        mkdir -p .agentplane-harbor/agentplane
        printf '%s\n' {quoted_policy} > AGENTS.md

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
        agentplane task start-ready "$TASK_ID" \
          --author CODER \
          --body "Start: Terminal-Bench run with generic AgentPlane policy." || true

        {executor_command}

        agentplane verify "$TASK_ID" \
          --ok \
          --by CODER \
          --note "Benchmark executor finished; the official grader remains scoring truth." \
          --local-only || true
        agentplane task show "$TASK_ID" > .agentplane-harbor/agentplane/task-show.txt 2>&1 || true
        agentplane task verify-show "$TASK_ID" \
          > .agentplane-harbor/agentplane/verify-show.txt 2>&1 || true
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
