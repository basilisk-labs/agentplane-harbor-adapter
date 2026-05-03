# Terminal-Bench / Harbor Submission Plan

## Objective

Publish an AgentPlane harness profile on Terminal-Bench/Harbor and produce
evidence that AgentPlane adds useful control-plane behavior around the same
underlying coding agent.

## Submission target

Preferred path: Harbor, because Harbor is the official harness for
Terminal-Bench 2.0 and supports custom installed agents.

Before a full run, re-check:

- current dataset identifier
- current leaderboard submission repository
- ATIF trajectory requirements
- default timeout policy
- allowed network policy

## A/B design

Run at least two matched pairs:

1. `codex-cli + model`
2. `agentplane-codex + same model`

Optional second pair:

1. `claude-code + model`
2. `agentplane-claude-code + same model`

Keep identical:

- model
- dataset version
- timeout
- concurrency
- provider
- benchmark harness version
- container image or environment backend

## Proof metrics

Terminal-Bench metrics:

- pass rate
- passed tasks
- failed tasks
- trials
- official logs
- ATIF trajectories

AgentPlane sidecar metrics:

- task artifact completeness
- verify artifact completeness
- final diff availability
- final git status
- policy hash
- version capture
- failure classification readiness
- wall-clock overhead when Harbor exposes timing

## Claim threshold

Strong claim:

- AgentPlane improves pass rate or reduces invalid failures with acceptable
  overhead.

Minimum defensible claim:

- AgentPlane preserves benchmark validity and adds reproducible lifecycle
  evidence, auditability, and failure analysis to the same executor/model setup.

Invalid claim:

- "AgentPlane is a better model."
- "AgentPlane alone solves Terminal-Bench."
- "AgentPlane guarantees better score on all tasks."

## Integrity checklist

- No modified benchmark timeout.
- No hidden tests exposed to the agent.
- No oracle solution in the adapter image.
- No task-specific prompt injection.
- No internet lookup for task solutions.
- Passing trials have ATIF trajectories.
- Adapter commit is public and pinned.
- AgentPlane policy hash is stable across tasks.

