from __future__ import annotations


def test_adapters_import_without_harbor_runtime() -> None:
    from agentplane_harbor_adapter import AgentPlaneClaudeCodeAgent, AgentPlaneCodexAgent

    assert AgentPlaneCodexAgent.name() == "agentplane-codex"
    assert AgentPlaneClaudeCodeAgent.name() == "agentplane-claude-code"

