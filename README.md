# AgentPlane Harbor Adapter

Harbor installed-agent adapters for benchmarking AgentPlane as a control-plane
wrapper around coding agents on Terminal-Bench.

AgentPlane is not submitted as a model. It is submitted as a harness profile:

- `agentplane-codex`: AgentPlane + Codex CLI
- `agentplane-claude-code`: AgentPlane + Claude Code

The goal is to measure whether AgentPlane improves reproducibility,
traceability, recovery, and failure analysis while preserving the same
underlying model and benchmark constraints.

## Status

Experimental scaffold. Use the smoke run first. Do not submit leaderboard
results until the generated proof bundle and ATIF trajectories have been
reviewed for Terminal-Bench integrity compliance.

## Requirements

- Docker running locally
- `uv`
- Harbor benchmark framework installed with `uv tool install harbor`
- Provider API key for the selected executor/model
- No benchmark-specific hints, oracle files, test folders, or modified timeouts

Codex CLI is authenticated inside the benchmark container with
`codex login --with-api-key`; the key is passed through Harbor agent env and is
not printed by the run wrapper.

If Homebrew's Harbor registry CLI is also installed, set this in `.env.local`:

```bash
HARBOR_BIN=$HOME/.local/bin/harbor
```

## Install for local development

```bash
uv venv
uv pip install -e ".[dev]"
```

## One-command local path

Copy the local environment template and add your API key:

```bash
cp .env.example .env.local
$EDITOR .env.local
```

Then run:

```bash
uv tool install harbor
./scripts/agentplane_bench.sh setup
./scripts/agentplane_bench.sh preflight
./scripts/agentplane_bench.sh oracle-smoke
./scripts/agentplane_bench.sh smoke
```

For a full Harbor run:

```bash
N= ./scripts/agentplane_bench.sh full
```

For a Terminal-Bench leaderboard-shaped run using the legacy `tb` CLI:

```bash
./scripts/agentplane_bench.sh leaderboard-tb
```

Estimate API cost before a full run:

```bash
./scripts/estimate_cost.py --model gpt-5-nano --tasks 80 --profile mid
```

## Run a smoke task

Codex:

```bash
export OPENAI_API_KEY="..."
harbor run \
  -d terminal-bench/terminal-bench-2 \
  --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
  -m gpt-5-nano \
  -n 1
```

Claude Code:

```bash
export ANTHROPIC_API_KEY="..."
harbor run \
  -d terminal-bench/terminal-bench-2 \
  --agent-import-path agentplane_harbor_adapter.agentplane_claude_code:AgentPlaneClaudeCodeAgent \
  -m anthropic/claude-sonnet-4-5 \
  -n 1
```

## Leaderboard run

Use the current Terminal-Bench/Harbor submission instructions before running a
full submission. As of the last checked public docs, leaderboard submissions
must use the official Terminal-Bench dataset, default agent timeout, default
test timeout, and ATIF trajectories for passing trials.

Example Harbor run shape:

```bash
harbor run \
  -d terminal-bench/terminal-bench-2 \
  --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
  -m gpt-5-nano
```

If the active submission route still requires the legacy Terminal-Bench CLI,
use the official dataset form:

```bash
tb run \
  --agent <published-agentplane-agent-name> \
  --model <model> \
  --dataset terminal-bench-core==0.1.1
```

See [docs/cost.md](docs/cost.md) before running a full dataset. A full run can
cost hundreds of dollars on frontier models if tasks require many turns.

## Proof bundle

Each adapter run writes AgentPlane sidecar artifacts under:

```text
.agentplane-harbor/
  proof.json
  versions.json
  git-diff.patch
  git-status.txt
  agentplane/
```

The proof bundle records:

- AgentPlane version
- executor version
- model name
- dataset/task metadata when Harbor exposes it
- generic policy hash
- run start/end timestamps
- final git status
- final diff
- AgentPlane task artifacts when available

## Integrity rules

The adapter must not:

- modify benchmark timeouts
- expose oracle solutions or hidden tests to the agent
- fetch task solutions from the internet
- change the grader or reward pipeline
- inject task-specific hints into AgentPlane policy
- store encrypted or obfuscated solutions in the adapter image

Reward hacking or cheating can invalidate the submission. Keep all AgentPlane
policy generic and publish the exact adapter commit used for the run.

## Interpreting results

Primary benchmark score:

- Terminal-Bench success rate
- passed tasks / total trials
- official logs and ATIF trajectories

AgentPlane-specific proof:

- evidence completeness
- reproducible lifecycle artifacts
- failed-run diagnosis quality
- dirty-state prevention
- overhead in wall time and artifacts

The adapter also writes local evaluator artifacts for each AgentPlane attempt:

- `.agentplane-harbor/agentplane/evaluator-report.json`
- `.agentplane-harbor/agentplane/evaluator-feedback.txt`
- `.agentplane-harbor/agentplane/evaluator-attempt-<n>.log`
- `.agentplane-harbor/agentplane/executor-attempt-<n>.log`

The evaluator uses only public task-local signals and treats the official
Harbor verifier as the scoring truth. A failed local evaluator triggers
AgentPlane rework, but the agent command exits successfully so Harbor can
record a normal trial and let the official verifier assign reward.

The minimum useful claim is not "AgentPlane always scores higher". It is:

> With the same executor and model, AgentPlane preserves benchmark validity and
> adds auditable task lifecycle evidence, reproducible artifacts, and clearer
> failure analysis.
