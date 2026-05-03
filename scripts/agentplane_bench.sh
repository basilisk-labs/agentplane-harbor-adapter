#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env.local ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi

MODEL="${MODEL:-openai/gpt-5-nano}"
DATASET="${DATASET:-terminal-bench/terminal-bench-2}"
LEADERBOARD_DATASET="${LEADERBOARD_DATASET:-terminal-bench-core==0.1.1}"
N="${N:-1}"
N_CONCURRENT="${N_CONCURRENT:-1}"
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
  MODEL                Default: openai/gpt-5-nano
  DATASET              Default: terminal-bench/terminal-bench-2
  LEADERBOARD_DATASET  Default: terminal-bench-core==0.1.1
  N                    Default: 1. Empty N means no -n flag.
  N_CONCURRENT         Default: 1.
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

n_flag() {
  if [[ -n "${N:-}" ]]; then
    printf -- "-n %q" "$N"
  fi
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
    run_shell "$TB_BIN --help >/dev/null"
    require_openai_key
    echo "model=$MODEL"
    echo "dataset=$DATASET"
    echo "leaderboard_dataset=$LEADERBOARD_DATASET"
    echo "n=${N:-full}"
    ;;

  oracle-smoke)
    run_shell "$HARBOR_BIN run -d '$DATASET' -a oracle -n 1"
    ;;

  smoke)
    require_openai_key
    run_shell "$HARBOR_BIN run \
      -d '$DATASET' \
      --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
      -m '$MODEL' \
      $(n_flag)"
    ;;

  full)
    require_openai_key
    if [[ -n "${N:-}" ]]; then
      echo "Refusing full run while N is set to '$N'. Run with N= for all tasks." >&2
      exit 1
    fi
    run_shell "$HARBOR_BIN run \
      -d '$DATASET' \
      --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
      -m '$MODEL'"
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
