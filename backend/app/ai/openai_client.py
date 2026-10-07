"""OpenAI client service and adapter wrapping the multi-provider LLM engine."""
from __future__ import annotations

from typing import Any, Optional

from .llm_client import (
    BaseLLMProvider,
    LLMConfigError,
    LLMServiceError,
    get_llm_provider,
)

# Backward-compatibility error aliases
OpenAIConfigError = LLMConfigError
OpenAIServiceError = LLMServiceError


class OpenAIClient:
    """Multi-provider client adapter maintaining the OpenAIClient contract."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        self._provider_name = provider
        self._explicit_key = api_key
        self._explicit_model = model

    def _get_provider(self, provider_override: Optional[str] = None) -> BaseLLMProvider:
        p_name = provider_override or self._provider_name
        return get_llm_provider(
            provider_name=p_name,
            api_key=self._explicit_key,
            model=self._explicit_model,
        )

    def is_configured(self, provider_override: Optional[str] = None) -> bool:
        provider = self._get_provider(provider_override)
        return provider.is_configured()

    def generate_structured_query(
        self,
        dataset_context: dict[str, Any],
        question: str,
        previous_plan: Optional[dict[str, Any]] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
        provider: Optional[str] = None,
    ) -> dict[str, Any]:
        p = self._get_provider(provider)
        return p.generate_structured_query(
            dataset_context=dataset_context,
            question=question,
            previous_plan=previous_plan,
            conversation_history=conversation_history,
        )

    def generate_insight(
        self,
        question: str,
        query_plan: dict[str, Any],
        execution_result: dict[str, Any],
        provider: Optional[str] = None,
    ) -> str:
        p = self._get_provider(provider)
        return p.generate_insight(
            question=question,
            query_plan=query_plan,
            execution_result=execution_result,
        )

    def generate_ai_suggestions(
        self,
        dataset_context: dict[str, Any],
        provider: Optional[str] = None,
    ) -> list[str]:
        p = self._get_provider(provider)
        return p.generate_ai_suggestions(dataset_context=dataset_context)


# Global singleton instance
openai_service = OpenAIClient()
