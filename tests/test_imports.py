from __future__ import annotations


def test_adapters_import_without_harbor_runtime() -> None:
    from agentplane_harbor_adapter import AgentPlaneClaudeCodeAgent, AgentPlaneCodexAgent

    assert AgentPlaneCodexAgent.name() == "agentplane-codex"
    assert AgentPlaneClaudeCodeAgent.name() == "agentplane-claude-code"


def test_codex_adapter_installs_curl_before_nodesource() -> None:
    from agentplane_harbor_adapter import AgentPlaneCodexAgent

    command = AgentPlaneCodexAgent.node_setup_command

    assert "apt-get install -y ca-certificates curl gnupg git" in command
    assert command.index("apt-get install -y ca-certificates curl") < command.index(
        "curl -fsSL https://deb.nodesource.com/setup_20.x"
    )


def test_codex_adapter_repairs_missing_linux_optional_dependency() -> None:
    from agentplane_harbor_adapter import AgentPlaneCodexAgent

    agent = AgentPlaneCodexAgent(model_name="gpt-5-nano")
    command = (
        "set -euo pipefail; "
        "git config --global user.name 'AgentPlane Harbor'; "
        "git config --global user.email 'agentplane-harbor@example.invalid'; "
        f"npm install -g --include=optional agentplane {agent.executor.npm_package}; "
        "if [ "
        f"\"{agent.executor.npm_package}\" = \"@openai/codex\" "
        "] && ! node -e "
        "\"import('@openai/codex-linux-x64')"
        ".then(()=>process.exit(0))"
        ".catch(()=>process.exit(1))\"; "
        "then "
        f"npm install -g {agent.codex_optional_dependency}; "
        "fi; "
    )

    assert "--include=optional" in command
    assert "@openai/codex-linux-x64" in command
    assert agent.codex_optional_dependency == "@openai/codex-linux-x64"
