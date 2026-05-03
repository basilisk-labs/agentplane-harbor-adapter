#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-anthropic/claude-sonnet-4-5}"
DATASET="${DATASET:-terminal-bench/terminal-bench-2}"
N="${N:-1}"

harbor run \
  -d "$DATASET" \
  --agent-import-path agentplane_harbor_adapter.agentplane_claude_code:AgentPlaneClaudeCodeAgent \
  -m "$MODEL" \
  -n "$N"

