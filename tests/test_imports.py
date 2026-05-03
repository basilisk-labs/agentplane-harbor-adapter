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
