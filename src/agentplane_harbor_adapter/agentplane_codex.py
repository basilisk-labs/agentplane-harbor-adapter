from __future__ import annotations

from .base import AgentPlaneInstalledAgent
from .common import ExecutorSpec


class AgentPlaneCodexAgent(AgentPlaneInstalledAgent):
    """Harbor installed-agent profile: AgentPlane + Codex CLI."""

    executor = ExecutorSpec(
        agent_name="agentplane-codex",
        npm_package="@openai/codex",
        version_command="codex --version",
        run_command_template=(
            "codex exec --dangerously-bypass-approvals-and-sandbox "
            "--skip-git-repo-check {model_flag} {instruction}"
        ),
        model_flag="-m",
        api_key_env="OPENAI_API_KEY",
    )

    @staticmethod
    def name() -> str:
        return "agentplane-codex"

    def version(self) -> str | None:
        return "0.1.0"
