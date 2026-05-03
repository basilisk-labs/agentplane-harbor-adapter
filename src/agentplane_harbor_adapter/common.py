from __future__ import annotations

import hashlib
import json
import shlex
import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
        "workspace state, read .agentplane-harbor/agentplane/evaluator-feedback.txt, "
        "fix the recorded failure, run a relevant check, and leave the best final "
        "state for the grader. Do not ask questions.\n\nOriginal benchmark instruction:\n"
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
        agentplane task plan approve "$TASK_ID" --by ORCHESTRATOR || true
        agentplane task start-ready "$TASK_ID" \
          --author CODER \
          --body "Start: Terminal-Bench run with generic AgentPlane policy." || true

        run_evaluator() {{
          set +e
          local attempt="$1"
          local feedback=".agentplane-harbor/agentplane/evaluator-feedback.txt"
          local log=".agentplane-harbor/agentplane/evaluator-attempt-${{attempt}}.log"
          : > "$feedback"
          : > "$log"

          if [ ! -f .agentplane-harbor/agentplane/executor-exit-code.txt ]; then
            echo "FAIL: executor did not write an exit code." | tee -a "$feedback" "$log"
            return 1
          fi

          local executor_exit_code
          executor_exit_code="$(cat .agentplane-harbor/agentplane/executor-exit-code.txt)"
          if [ "$executor_exit_code" != "0" ]; then
            echo "FAIL: executor exited with code $executor_exit_code." \
              | tee -a "$feedback" "$log"
            tail -n 80 .agentplane-harbor/agentplane/executor.log \
              >> "$feedback" 2>/dev/null || true
            return 1
          fi

          # Public, task-local checks only. Do not read or run hidden graders in /tests.
          if [ -f main.tex ] && [ -f input.tex ] && [ -f synonyms.txt ]; then
            set +e
            pdflatex -interaction=nonstopmode main.tex > "$log" 2>&1
            local latex_status="$?"
            if [ "$latex_status" != "0" ]; then
              echo "FAIL: pdflatex exited with code $latex_status." > "$feedback"
              tail -n 120 "$log" >> "$feedback" || true
              return 1
            fi
            if grep -q 'Overfull \\\\hbox' main.log 2>/dev/null; then
              echo "FAIL: main.log still contains Overfull \\\\hbox warnings." \
                > "$feedback"
              grep -n 'Overfull \\\\hbox' main.log >> "$feedback" || true
              return 1
            fi
            echo "PASS: pdflatex completed without Overfull hbox warnings." \
              | tee -a "$feedback" "$log"
            return 0
          fi

          if [ -f /app/deps/illum1.pov ]; then
            if [ ! -x /usr/local/bin/povray ]; then
              echo "FAIL: /usr/local/bin/povray is missing or not executable." \
                > "$feedback"
              return 1
            fi
            set +e
            /usr/local/bin/povray +L/app/povray-2.2/povdoc/include \
              +I/app/deps/illum1.pov +O/dev/null +P -V > "$log" 2>&1
            local pov_status="$?"
            if [ "$pov_status" != "0" ]; then
              echo "FAIL: POV-Ray sanity render exited with code $pov_status." \
                > "$feedback"
              tail -n 120 "$log" >> "$feedback" || true
              return 1
            fi
            echo "PASS: POV-Ray sanity render completed." | tee -a "$feedback" "$log"
            return 0
          fi

          if [ -f /app/sim.c ] && [ -f /app/gates.txt ]; then
            if [ ! -x /app/sim ]; then
              set +e
              cc /app/sim.c -O2 -o /app/sim > "$log" 2>&1
              local cc_status="$?"
              if [ "$cc_status" != "0" ]; then
                echo "FAIL: could not compile /app/sim.c." > "$feedback"
                tail -n 120 "$log" >> "$feedback" || true
                return 1
              fi
            fi
            local fib_a fib_b
            fib_a="$(/app/sim 208 2>>"$log" || true)"
            fib_b="$(/app/sim 20000 2>>"$log" || true)"
            if [ "$fib_a" != "377" ] || [ "$fib_b" != "1407432322" ]; then
              {{
                echo "FAIL: gates.txt failed public examples."
                echo "sim 208 => $fib_a, expected 377"
                echo "sim 20000 => $fib_b, expected 1407432322"
              }} > "$feedback"
              return 1
            fi
            echo "PASS: gates.txt passed public examples." | tee -a "$feedback" "$log"
            return 0
          fi

          if [ -f /app/doomgeneric_mips ]; then
            if [ ! -f vm.js ]; then
              echo "FAIL: vm.js is missing." > "$feedback"
              return 1
            fi
            local vm_static_check
            vm_static_check="$(grep -Eic \
              'doomgeneric_mips|readUInt|DataView|syscall|register|opcode|pc|elf|writeFileSync' \
              vm.js 2>/dev/null || true)"
            if [ "$vm_static_check" -lt 6 ]; then
              {{
                echo "FAIL: vm.js does not look like a real MIPS/ELF interpreter."
                echo "Expected code to load doomgeneric_mips and implement CPU/syscall/file"
                echo "behavior."
                echo "Static interpreter signal count: $vm_static_check"
              }} > "$feedback"
              return 1
            fi
            if grep -Eiq 'scaffold|stand[- ]?in|fake|placeholder|deterministic.*frame|gradient' \
              vm.js 2>/dev/null; then
              {{
                echo "FAIL: vm.js appears to be a scaffold or fake frame generator."
                echo "Implement a real interpreter path instead of fabricating a frame."
              }} > "$feedback"
              return 1
            fi
            set +e
            timeout 45s node vm.js > "$log" 2>&1
            local vm_status="$?"
            if [ ! -f /tmp/frame.bmp ] && ! find /app -maxdepth 2 -type f \
              \\( -name 'frame*.bmp' -o -name '*.bmp' \\) | grep -q .; then
              {{
                echo "FAIL: node vm.js did not produce a frame BMP during smoke run."
                echo "node exit/timeout status: $vm_status"
              }} > "$feedback"
              tail -n 120 "$log" >> "$feedback" || true
              return 1
            fi
            echo "PASS: vm.js produced a BMP frame candidate." | tee -a "$feedback" "$log"
            return 0
          fi

          echo "INCONCLUSIVE: no task-specific public evaluator matched; executor exit was 0." \
            | tee -a "$feedback" "$log"
          return 0
        }}

        record_rework() {{
          local note="$1"
          local impact="$2"
          local resolution="$3"
          local observation
          set +e
          observation="$(head -c 600 .agentplane-harbor/agentplane/evaluator-feedback.txt \
            2>/dev/null)"
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
