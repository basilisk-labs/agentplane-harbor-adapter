from __future__ import annotations

from typing import Any

from .common import ExecutorSpec, render_agentplane_command, render_proof_collection_command

try:
    from harbor.agents.installed.base import (  # type: ignore[import-not-found]
        BaseInstalledAgent,
        with_prompt_template,
    )
except Exception:  # pragma: no cover - Harbor is provided by the benchmark runtime.
    BaseInstalledAgent = object  # type: ignore[assignment]

    def with_prompt_template(func: Any) -> Any:
        return func


class AgentPlaneInstalledAgent(BaseInstalledAgent):  # type: ignore[misc,valid-type]
    executor: ExecutorSpec
    codex_optional_dependency = "@openai/codex-linux-x64"
    node_setup_command = (
        "set -euo pipefail; "
        "if command -v node >/dev/null 2>&1 && "
        "node -e 'process.exit(Number(process.versions.node.split(`.`)[0]) >= 20 ? 0 : 1)'; "
        "then exit 0; fi; "
        "apt-get update; "
        "apt-get install -y ca-certificates curl gnupg git; "
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -; "
        "apt-get install -y nodejs git ca-certificates"
    )

    def __init__(self, *args: Any, model_name: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.model_name = model_name

    async def install(self, environment: Any) -> None:
        await self.exec_as_root(environment, command=self.node_setup_command)
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                "git config --global user.name 'AgentPlane Harbor'; "
                "git config --global user.email 'agentplane-harbor@example.invalid'; "
                f"npm install -g --include=optional agentplane {self.executor.npm_package}; "
                "if [ "
                f"\"{self.executor.npm_package}\" = \"@openai/codex\" "
                "] && ! node -e "
                "\"import('@openai/codex-linux-x64')"
                ".then(()=>process.exit(0))"
                ".catch(()=>process.exit(1))\"; "
                "then "
                f"npm install -g {self.codex_optional_dependency}; "
                "fi; "
                f"test -n \"${{{self.executor.api_key_env}:-}}\"; "
                f"printenv {self.executor.api_key_env} | codex login --with-api-key; "
                "agentplane --version"
            ),
        )

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: Any,
        context: Any,
    ) -> None:
        model = self.model_name or getattr(context, "model", None)
        started_at = None
        if hasattr(context, "metadata") and isinstance(context.metadata, dict):
            context.metadata["agentplane_adapter"] = self.executor.agent_name
            context.metadata["agentplane_profile"] = f"agentplane + {self.executor.agent_name}"
            started_at = context.metadata.get("started_at")

        await self.exec_as_agent(
            environment,
            command=render_agentplane_command(
                instruction,
                self.executor,
                str(model) if model else None,
            ),
        )
        await self.exec_as_agent(
            environment,
            command=render_proof_collection_command(self.executor, str(model) if model else None),
        )

        if hasattr(context, "metadata") and isinstance(context.metadata, dict):
            context.metadata["agentplane_started_at"] = started_at
            context.metadata["agentplane_proof_path"] = ".agentplane-harbor/proof.json"
            context.metadata["agentplane_artifact_dir"] = ".agentplane-harbor"

    def populate_context_post_run(self, context: Any) -> None:
        if hasattr(context, "metadata") and isinstance(context.metadata, dict):
            context.metadata.setdefault("agentplane_proof_path", ".agentplane-harbor/proof.json")
            context.metadata.setdefault("agentplane_artifact_dir", ".agentplane-harbor")
