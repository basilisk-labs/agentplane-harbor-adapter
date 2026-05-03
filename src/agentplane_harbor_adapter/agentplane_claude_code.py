from __future__ import annotations

from .base import AgentPlaneInstalledAgent
from .common import ExecutorSpec


class AgentPlaneClaudeCodeAgent(AgentPlaneInstalledAgent):
    """Harbor installed-agent profile: AgentPlane + Claude Code."""

    executor = ExecutorSpec(
        agent_name="agentplane-claude-code",
        npm_package="@anthropic-ai/claude-code",
        version_command="claude --version",
        run_command_template=(
            "claude -p --bare --dangerously-skip-permissions {model_flag} {instruction}"
        ),
        model_flag="--model",
        api_key_env="ANTHROPIC_API_KEY",
    )

    @staticmethod
    def name() -> str:
        return "agentplane-claude-code"

    def version(self) -> str | None:
        return "0.1.0"
