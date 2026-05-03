# Runbook

## 1. Verify tools

```bash
docker ps
uv --version
uv tool install harbor
$HOME/.local/bin/harbor --help
```

## 2. Install adapter

```bash
uv venv
uv pip install -e ".[dev]"
```

If another `harbor` binary is first on `PATH`, put this in `.env.local`:

```bash
HARBOR_BIN=$HOME/.local/bin/harbor
```

## 3. Oracle smoke

```bash
./scripts/agentplane_bench.sh oracle-smoke
```

This proves Harbor and Docker work before testing AgentPlane.

## 4. AgentPlane smoke

```bash
./scripts/agentplane_bench.sh smoke
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
