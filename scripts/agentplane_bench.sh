#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"

ENV_OPENAI_API_KEY="${OPENAI_API_KEY:-}"
ENV_ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
ENV_BENCHMARK_ENGINE="${BENCHMARK_ENGINE:-}"
ENV_DATASET="${DATASET:-}"
ENV_LEADERBOARD_DATASET="${LEADERBOARD_DATASET:-}"
ENV_MODEL="${MODEL:-}"
ENV_N="${N:-}"
ENV_N_CONCURRENT="${N_CONCURRENT:-}"
ENV_AGENT_SETUP_TIMEOUT_MULTIPLIER="${AGENT_SETUP_TIMEOUT_MULTIPLIER:-}"
ENV_REPAIR_ATTEMPTS="${REPAIR_ATTEMPTS:-}"
ENV_HARBOR_BIN="${HARBOR_BIN:-}"
ENV_TB_BIN="${TB_BIN:-}"

if [[ -f .env.local ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi

OPENAI_API_KEY="${ENV_OPENAI_API_KEY:-${OPENAI_API_KEY:-}}"
ANTHROPIC_API_KEY="${ENV_ANTHROPIC_API_KEY:-${ANTHROPIC_API_KEY:-}}"
BENCHMARK_ENGINE="${ENV_BENCHMARK_ENGINE:-${BENCHMARK_ENGINE:-}}"
DATASET="${ENV_DATASET:-${DATASET:-}}"
LEADERBOARD_DATASET="${ENV_LEADERBOARD_DATASET:-${LEADERBOARD_DATASET:-}}"
MODEL="${ENV_MODEL:-${MODEL:-}}"
N="${ENV_N:-${N:-}}"
N_CONCURRENT="${ENV_N_CONCURRENT:-${N_CONCURRENT:-}}"
AGENT_SETUP_TIMEOUT_MULTIPLIER="${ENV_AGENT_SETUP_TIMEOUT_MULTIPLIER:-${AGENT_SETUP_TIMEOUT_MULTIPLIER:-}}"
REPAIR_ATTEMPTS="${ENV_REPAIR_ATTEMPTS:-${REPAIR_ATTEMPTS:-}}"
HARBOR_BIN="${ENV_HARBOR_BIN:-${HARBOR_BIN:-}}"
TB_BIN="${ENV_TB_BIN:-${TB_BIN:-}}"

MODEL="${MODEL:-gpt-5-nano}"
DATASET="${DATASET:-terminal-bench/terminal-bench-2}"
LEADERBOARD_DATASET="${LEADERBOARD_DATASET:-terminal-bench-core==0.1.1}"
N="${N:-1}"
N_CONCURRENT="${N_CONCURRENT:-1}"
AGENT_SETUP_TIMEOUT_MULTIPLIER="${AGENT_SETUP_TIMEOUT_MULTIPLIER:-3}"
REPAIR_ATTEMPTS="${REPAIR_ATTEMPTS:-3}"
HARBOR_BIN="${HARBOR_BIN:-harbor}"
TB_BIN="${TB_BIN:-tb}"

usage() {
  cat <<'EOF'
Usage: ./scripts/agentplane_bench.sh <command>

Commands:
  setup          Create uv venv and install this adapter with dev tools.
  preflight      Check Docker, uv, Harbor/tb commands, and required API key.
  oracle-smoke   Run one official oracle smoke through Harbor.
  smoke          Run AgentPlane + Codex through Harbor for N tasks.
  full           Run AgentPlane + Codex through Harbor for DATASET.
  leaderboard-tb Print and run a Terminal-Bench leaderboard-shaped command.
  cost           Estimate OpenAI API cost for common profiles.

Environment:
  OPENAI_API_KEY       Required for agentplane-codex.
  MODEL                Default: gpt-5-nano
  DATASET              Default: terminal-bench/terminal-bench-2
  LEADERBOARD_DATASET  Default: terminal-bench-core==0.1.1
  N                    Default: 1. Empty N means no -n flag.
  N_CONCURRENT         Default: 1.
  AGENT_SETUP_TIMEOUT_MULTIPLIER
                       Default: 3. Passed to Harbor agent setup timeout.
  REPAIR_ATTEMPTS      Default: 3. AgentPlane runner/evaluator repair attempts.
  HARBOR_BIN           Default: harbor. Can be "uvx harbor".
  TB_BIN               Default: tb. Can be "uvx terminal-bench".
EOF
}

require_openai_key() {
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "OPENAI_API_KEY is required. Put it in .env.local or export it." >&2
    exit 1
  fi
}

run_cmd() {
  echo "+ $*"
  "$@"
}

run_shell() {
  echo "+ $*"
  bash -lc "$*"
}

run_shell_redacted() {
  local redacted="$1"
  local command="$2"
  echo "+ $redacted"
  bash -lc "$command"
}

n_flag() {
  if [[ -n "${N:-}" ]]; then
    printf -- "--n-tasks %q" "$N"
  fi
}

openai_agent_env_flag() {
  printf -- "--agent-env %q" 'OPENAI_API_KEY=${OPENAI_API_KEY}'
}

repair_attempts_agent_env_flag() {
  printf -- "--agent-env AGENTPLANE_REPAIR_ATTEMPTS=%q" "$REPAIR_ATTEMPTS"
}

case "${1:-}" in
  setup)
    run_cmd uv venv
    run_cmd uv pip install -e ".[dev]"
    ;;

  preflight)
    run_cmd docker ps >/dev/null
    run_cmd uv --version
    run_shell "$HARBOR_BIN --help >/dev/null"
    if run_shell "$TB_BIN --help >/dev/null"; then
      echo "tb=available"
    else
      echo "tb=unavailable (only needed for leaderboard-tb)"
    fi
    require_openai_key
    echo "model=$MODEL"
    echo "dataset=$DATASET"
    echo "leaderboard_dataset=$LEADERBOARD_DATASET"
    echo "n_tasks=${N:-full}"
    echo "n_concurrent=$N_CONCURRENT"
    ;;

  oracle-smoke)
    run_shell "$HARBOR_BIN run -d '$DATASET' -a oracle --n-tasks 1 --n-concurrent 1 --yes"
    ;;

  smoke)
    require_openai_key
    redacted_openai_agent_env="--agent-env OPENAI_API_KEY=***"
    openai_agent_env="$(openai_agent_env_flag)"
    repair_attempts_agent_env="$(repair_attempts_agent_env_flag)"
    run_shell_redacted "$HARBOR_BIN run \
      -d '$DATASET' \
      --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
      -m '$MODEL' \
      --env-file .env.local \
      $redacted_openai_agent_env \
      --agent-env AGENTPLANE_REPAIR_ATTEMPTS='$REPAIR_ATTEMPTS' \
      --artifact /app/.agentplane-harbor \
      --agent-setup-timeout-multiplier '$AGENT_SETUP_TIMEOUT_MULTIPLIER' \
      --n-concurrent '$N_CONCURRENT' \
      $(n_flag)" "$HARBOR_BIN run \
      -d '$DATASET' \
      --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
      -m '$MODEL' \
      --env-file .env.local \
      $openai_agent_env \
      $repair_attempts_agent_env \
      --artifact /app/.agentplane-harbor \
      --agent-setup-timeout-multiplier '$AGENT_SETUP_TIMEOUT_MULTIPLIER' \
      --n-concurrent '$N_CONCURRENT' \
      $(n_flag)"
    ;;

  full)
    require_openai_key
    if [[ -n "${N:-}" ]]; then
      echo "Ignoring N='$N' for explicit full run."
    fi
    redacted_openai_agent_env="--agent-env OPENAI_API_KEY=***"
    openai_agent_env="$(openai_agent_env_flag)"
    repair_attempts_agent_env="$(repair_attempts_agent_env_flag)"
    run_shell_redacted "$HARBOR_BIN run \
      -d '$DATASET' \
      --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
      -m '$MODEL' \
      --env-file .env.local \
      $redacted_openai_agent_env \
      --agent-env AGENTPLANE_REPAIR_ATTEMPTS='$REPAIR_ATTEMPTS' \
      --artifact /app/.agentplane-harbor \
      --agent-setup-timeout-multiplier '$AGENT_SETUP_TIMEOUT_MULTIPLIER' \
      --n-concurrent '$N_CONCURRENT'" "$HARBOR_BIN run \
      -d '$DATASET' \
      --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
      -m '$MODEL' \
      --env-file .env.local \
      $openai_agent_env \
      $repair_attempts_agent_env \
      --artifact /app/.agentplane-harbor \
      --agent-setup-timeout-multiplier '$AGENT_SETUP_TIMEOUT_MULTIPLIER' \
      --n-concurrent '$N_CONCURRENT'"
    ;;

  leaderboard-tb)
    require_openai_key
    cat <<EOF
About to run legacy Terminal-Bench leaderboard-shaped command.
Confirm the official submission route before using this result for leaderboard submission.
EOF
    run_shell "$TB_BIN run \
      -d '$LEADERBOARD_DATASET' \
      -a terminus \
      -m '$MODEL' \
      --n-concurrent '$N_CONCURRENT'"
    ;;

  cost)
    run_cmd ./scripts/estimate_cost.py --model gpt-5-nano --tasks 80 --profile low
    run_cmd ./scripts/estimate_cost.py --model gpt-5-nano --tasks 80 --profile mid
    run_cmd ./scripts/estimate_cost.py --model gpt-5-nano --tasks 80 --profile high
    run_cmd ./scripts/estimate_cost.py --model gpt-5.4-nano --tasks 80 --profile low
    run_cmd ./scripts/estimate_cost.py --model gpt-5.4-nano --tasks 80 --profile mid
    run_cmd ./scripts/estimate_cost.py --model gpt-5.4-nano --tasks 80 --profile high
    run_cmd ./scripts/estimate_cost.py --model gpt-5.5 --tasks 80 --profile low
    run_cmd ./scripts/estimate_cost.py --model gpt-5.5 --tasks 80 --profile mid
    run_cmd ./scripts/estimate_cost.py --model gpt-5.5 --tasks 80 --profile high
    ;;

  -h|--help|help|"")
    usage
    ;;

  *)
    echo "Unknown command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
