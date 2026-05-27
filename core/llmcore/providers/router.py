"""Multi-provider router.

Resolves a model id to a ready backend. Today every hosted model is served by
the OpenRouter gateway (one key, many vendors) and the self-hosted OSS model by
the "oss" gateway; the registry is built so adding a direct provider later is a
config change, not a code change.
"""

from __future__ import annotations

from ..catalog import CATALOG, ModelInfo, get_model
from ..config import CoreSettings, settings as default_settings
from .openai_compatible import OpenAICompatibleBackend


class Router:
    def __init__(self, settings: CoreSettings | None = None) -> None:
        self.settings = settings or default_settings

    def available_models(self) -> list[ModelInfo]:
        """Models we can actually reach given the configured credentials."""
        out: list[ModelInfo] = []
        for info in CATALOG.values():
            if info.gateway == "openrouter" and self.settings.openrouter_api_key:
                out.append(info)
            elif info.gateway == "oss" and self.settings.oss_space_url:
                out.append(info)
        return out

    def backend_for(self, model_id: str) -> OpenAICompatibleBackend:
        info = get_model(model_id)
        if info is None:
            # Unknown id: assume it's an OpenRouter slug, infer provider from prefix.
            provider = model_id.split("/", 1)[0] if "/" in model_id else "openrouter"
            info = ModelInfo(id=model_id, label=model_id, provider=provider, gateway="openrouter")

        if info.gateway == "openrouter":
            return OpenAICompatibleBackend(
                provider=info.provider,
                model=info.id,
                base_url=self.settings.openrouter_base_url,
                api_key=self.settings.openrouter_api_key,
                default_headers={
                    "HTTP-Referer": self.settings.app_referer,
                    "X-Title": self.settings.app_title,
                },
            )
        if info.gateway == "oss":
            # The HF Space exposes an OpenAI-compatible shim (see beacon/underwriter
            # wiring); if it does not, an HFSpaceBackend adapter is swapped in here.
            return OpenAICompatibleBackend(
                provider="oss",
                model=info.id,
                base_url=self.settings.oss_space_url,
                api_key="EMPTY",
            )
        raise ValueError(f"no gateway configured for model {model_id!r}")
