#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-openai/gpt-5.5}"
DATASET="${DATASET:-terminal-bench/terminal-bench-2}"
N="${N:-1}"

harbor run \
  -d "$DATASET" \
  --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
  -m "$MODEL" \
  -n "$N"

