# Runbook

## 1. Verify tools

```bash
docker ps
uv --version
harbor --help
```

## 2. Install adapter

```bash
uv venv
uv pip install -e ".[dev]"
```

## 3. Oracle smoke

```bash
harbor run -d terminal-bench/terminal-bench-2 -a oracle -n 1
```

This proves Harbor and Docker work before testing AgentPlane.

## 4. AgentPlane smoke

```bash
export OPENAI_API_KEY="..."
harbor run \
  -d terminal-bench/terminal-bench-2 \
  --agent-import-path agentplane_harbor_adapter.agentplane_codex:AgentPlaneCodexAgent \
  -m openai/gpt-5.5 \
  -n 1
```

## 5. Inspect artifacts

Check the Harbor output directory for:

- ATIF trajectory
- task logs
- `.agentplane-harbor/proof.json`
- `.agentplane-harbor/git-diff.patch`
- `.agentplane-harbor/git-status.txt`

## 6. Matched A/B run

Run raw executor and AgentPlane executor on the same dataset slice.

Do not change timeout or grader settings.

## 7. Full run

Run the official dataset only after:

- smoke run passes
- proof bundle exists
- ATIF exists for passing trials
- no forbidden artifacts are present
- current submission route is confirmed

