"""Generic Multi-Provider LLM Client supporting OpenAI, Anthropic, Gemini, Groq, and custom endpoints."""
from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from .prompts import (
    ANALYST_SYSTEM_PROMPT,
    build_insight_prompt,
    build_user_prompt,
)

logger = logging.getLogger(__name__)


class LLMConfigError(ValueError):
    """Raised when an API key or configuration is missing for a requested provider."""
    pass


class LLMServiceError(RuntimeError):
    """Raised when the LLM service is unreachable or fails."""
    pass


# Backward compatibility aliases
OpenAIConfigError = LLMConfigError
OpenAIServiceError = LLMServiceError


def _extract_json(text: str) -> dict[str, Any]:
    """Robustly extracts JSON from an LLM response string."""
    clean = text.strip()
    # Strip markdown fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
    if match:
        clean = match.group(1).strip()
    try:
        return json.loads(clean)
    except Exception:
        # Fallback: search for first '{' and last '}'
        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(clean[start : end + 1])
        raise ValueError(f"Could not parse valid JSON from response: {text[:200]}")


class BaseLLMProvider(ABC):
    """Abstract interface implemented by all LLM providers."""

    provider_id: str
    display_name: str
    default_model: str

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def generate_structured_query(
        self,
        dataset_context: dict[str, Any],
        question: str,
        previous_plan: Optional[dict[str, Any]] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def generate_insight(
        self,
        question: str,
        query_plan: dict[str, Any],
        execution_result: dict[str, Any],
    ) -> str:
        pass

    @abstractmethod
    def generate_ai_suggestions(
        self,
        dataset_context: dict[str, Any],
    ) -> list[str]:
        pass

    @abstractmethod
    def generate_business_explanation(
        self,
        explanation_type: str,
        evidence: dict[str, Any],
        max_tokens: int = 650,
        corrective_feedback: Optional[str] = None,
    ) -> dict[str, Any]:
        pass



class OpenAICompatibleProvider(BaseLLMProvider):
    """Generic provider using OpenAI Python SDK with customizable base_url and api_key.
    Powers OpenAI, Groq, Gemini, and Custom OpenAI-compatible endpoints (Ollama, DeepSeek, vLLM).
    """

    def __init__(
        self,
        provider_id: str,
        display_name: str,
        default_model: str,
        env_key_name: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, model=model)
        self.provider_id = provider_id
        self.display_name = display_name
        self.default_model = default_model
        self.env_key_name = env_key_name
        self.base_url = base_url

    def _get_key(self) -> str:
        key = self.api_key or os.environ.get(self.env_key_name, "").strip()
        if not key and self.provider_id not in ("custom", "ollama"):
            raise LLMConfigError(f"{self.display_name} API key is not configured ({self.env_key_name}).")
        return key or "dummy_key"

    def _get_model(self) -> str:
        return (
            self.model
            or os.environ.get(f"{self.provider_id.upper()}_MODEL")
            or os.environ.get("LLM_MODEL")
            or self.default_model
        ).strip()

    def is_configured(self) -> bool:
        if self.provider_id == "ollama":
            return True  # Local Ollama uses default localhost:11434/v1 unless overridden
        if self.provider_id == "custom":
            return bool(os.environ.get("LLM_BASE_URL", "").strip() or self.base_url)
        return bool(self.api_key or os.environ.get(self.env_key_name, "").strip())

    def _get_timeout(self, default: float = 30.0) -> float:
        env_val = os.environ.get("LLM_TIMEOUT", "").strip()
        if env_val:
            try:
                return float(env_val)
            except ValueError:
                pass
        # Local / custom models need more time (e.g. Ollama model loading)
        if self.provider_id in ("custom", "ollama"):
            return max(default, 60.0)
        return default

    def _get_client(self, timeout: Optional[float] = None):
        from openai import OpenAI
        actual_timeout = timeout if timeout is not None else self._get_timeout()
        kwargs: dict[str, Any] = {
            "api_key": self._get_key(),
            "timeout": actual_timeout,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return OpenAI(**kwargs)

    def generate_structured_query(
        self,
        dataset_context: dict[str, Any],
        question: str,
        previous_plan: Optional[dict[str, Any]] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        try:
            timeout_val = self._get_timeout(default=60.0 if self.provider_id == "custom" else 30.0)
            client = self._get_client(timeout=timeout_val)
            user_prompt = build_user_prompt(
                question=question,
                context=dataset_context,
                previous_plan=previous_plan,
                conversation_history=conversation_history,
            )

            kwargs: dict[str, Any] = {
                "model": self._get_model(),
                "messages": [
                    {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0,
            }
            # Most providers support JSON response format
            try:
                kwargs["response_format"] = {"type": "json_object"}
                resp = client.chat.completions.create(**kwargs)
            except Exception:
                # If provider rejects json_object response_format, retry without it
                kwargs.pop("response_format", None)
                resp = client.chat.completions.create(**kwargs)

            raw = resp.choices[0].message.content or "{}"
            return _extract_json(raw)
        except LLMConfigError:
            raise
        except Exception as e:
            logger.error("%s query generation failed: %s", self.display_name, e, exc_info=True)
            err_str = str(e).lower()
            if "api key" in err_str or "unauthorized" in err_str or "authentication" in err_str:
                raise LLMConfigError(f"{self.display_name} API key is not configured or is invalid.")
            raise LLMServiceError(f"{self.display_name} AI service is currently unavailable: {e}")

    def generate_insight(
        self,
        question: str,
        query_plan: dict[str, Any],
        execution_result: dict[str, Any],
    ) -> str:
        if not self.is_configured():
            return ""
        try:
            timeout_val = self._get_timeout(default=45.0 if self.provider_id == "custom" else 20.0)
            client = self._get_client(timeout=timeout_val)
            prompt = build_insight_prompt(question, query_plan, execution_result)
            resp = client.chat.completions.create(
                model=self._get_model(),
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior data analyst. Provide concise, clear, and factual business insights based strictly on provided data results.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=250,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning("%s insight generation failed: %s", self.display_name, e)
            return ""

    def generate_ai_suggestions(
        self,
        dataset_context: dict[str, Any],
    ) -> list[str]:
        if not self.is_configured():
            return []
        timeout_val = self._get_timeout(default=40.0 if self.provider_id == "custom" else 20.0)
        try:
            client = self._get_client(timeout=timeout_val)
            compact_cols = []
            for t in dataset_context.get("tables", []):
                for c in t.get("columns", [])[:15]:
                    compact_cols.append(f"{c['name']} ({c.get('semantic_type', 'UNKNOWN')})")

            prompt = f"""Given the following dataset schema:
Dataset: {dataset_context.get('dataset_name')}
Columns: {', '.join(compact_cols)}

Generate 5 to 6 varied, insightful, analytical business questions that can be answered from this dataset.
Return ONLY a JSON object: {{"suggestions": ["question 1", "question 2"]}}
"""
            resp = client.chat.completions.create(
                model=self._get_model(),
                messages=[
                    {"role": "system", "content": "You are an analytical assistant generating exploratory questions."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content or "{}"
            parsed = _extract_json(raw)
            suggestions = parsed.get("suggestions", [])
            return [s.strip() for s in suggestions if isinstance(s, str) and s.strip()]
        except Exception as e:
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                logger.info("%s suggestions generation timed out after %.1fs. Using instant schema suggestions.", self.display_name, timeout_val)
            else:
                logger.warning("%s suggestions generation failed: %s", self.display_name, e)
            return []

    def generate_business_explanation(
        self,
        explanation_type: str,
        evidence: dict[str, Any],
        max_tokens: int = 650,
        corrective_feedback: Optional[str] = None,
    ) -> dict[str, Any]:
        from .explanation_prompts import (
            EXPLANATION_SYSTEM_PROMPT,
            build_prediction_prompt,
            build_forecast_prompt,
        )

        user_prompt = (
            build_prediction_prompt(evidence, corrective_feedback=corrective_feedback)
            if explanation_type == "prediction"
            else build_forecast_prompt(evidence, corrective_feedback=corrective_feedback)
        )


        timeout_val = self._get_timeout(default=60.0 if self.provider_id in ("custom", "ollama") else 35.0)
        client = self._get_client(timeout=timeout_val)

        kwargs: dict[str, Any] = {
            "model": self._get_model(),
            "messages": [
                {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }

        try:
            try:
                kwargs["response_format"] = {"type": "json_object"}
                resp = client.chat.completions.create(**kwargs)
            except Exception:
                kwargs.pop("response_format", None)
                resp = client.chat.completions.create(**kwargs)

            raw = resp.choices[0].message.content or "{}"
            return _extract_json(raw)
        except LLMConfigError:
            raise
        except Exception as e:
            err_msg = str(e).lower()
            logger.error("%s explanation generation failed: %s", self.display_name, e)
            if "connection refused" in err_msg or "cannot connect" in err_msg or "failed to connect" in err_msg or "target machine actively refused" in err_msg:
                raise LLMServiceError(
                    f"{self.display_name} server is unreachable at {self.base_url or 'default endpoint'}. "
                    "Ensure Ollama/local server is running (`ollama serve`)."
                )
            if "not found" in err_msg and "model" in err_msg:
                raise LLMConfigError(
                    f"Model '{self._get_model()}' not found in {self.display_name}. "
                    f"Ensure model is pulled (`ollama pull {self._get_model()}`)."
                )
            if "timeout" in err_msg or "timed out" in err_msg:
                raise LLMServiceError(f"{self.display_name} request timed out after {timeout_val}s.")
            if "api key" in err_msg or "unauthorized" in err_msg or "401" in err_msg:
                raise LLMConfigError(f"{self.display_name} API key is invalid or unauthorized.")
            if "rate limit" in err_msg or "429" in err_msg:
                raise LLMServiceError(f"{self.display_name} rate limit reached. Please retry in a few moments.")
            raise LLMServiceError(f"{self.display_name} error: {e}")


class AnthropicProvider(BaseLLMProvider):
    """Native Anthropic Claude provider using direct HTTP Messages API."""

    provider_id = "anthropic"
    display_name = "Anthropic Claude"
    default_model = "claude-3-5-sonnet-20241022"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(api_key=api_key, model=model)

    def _get_timeout(self, default: float = 30.0) -> float:
        env_val = os.environ.get("LLM_TIMEOUT", "").strip()
        if env_val:
            try:
                return float(env_val)
            except ValueError:
                pass
        return default

    def _get_key(self) -> str:
        key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise LLMConfigError("Anthropic API key is not configured (ANTHROPIC_API_KEY).")
        return key

    def _get_model(self) -> str:
        return (
            self.model
            or os.environ.get("ANTHROPIC_MODEL")
            or os.environ.get("LLM_MODEL")
            or self.default_model
        ).strip()

    def is_configured(self) -> bool:
        return bool(self.api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip())

    def _call_messages(self, system: str, user_content: str, max_tokens: int = 1000) -> str:
        headers = {
            "x-api-key": self._get_key(),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self._get_model(),
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_content}],
            "temperature": 0.0,
        }
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
                if resp.status_code == 401:
                    raise LLMConfigError("Anthropic API key is invalid or unauthorized.")
                resp.raise_for_status()
                data = resp.json()
                content_blocks = data.get("content", [])
                text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
                return "".join(text_parts)
        except LLMConfigError:
            raise
        except Exception as e:
            raise LLMServiceError(f"Anthropic service failed: {e}")

    def generate_structured_query(
        self,
        dataset_context: dict[str, Any],
        question: str,
        previous_plan: Optional[dict[str, Any]] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        user_prompt = build_user_prompt(
            question=question,
            context=dataset_context,
            previous_plan=previous_plan,
            conversation_history=conversation_history,
        )
        system_instruction = ANALYST_SYSTEM_PROMPT + "\nIMPORTANT: Return ONLY raw JSON without any markdown formatting or commentary."
        raw_text = self._call_messages(system=system_instruction, user_content=user_prompt)
        return _extract_json(raw_text)

    def generate_insight(
        self,
        question: str,
        query_plan: dict[str, Any],
        execution_result: dict[str, Any],
    ) -> str:
        if not self.is_configured():
            return ""
        try:
            prompt = build_insight_prompt(question, query_plan, execution_result)
            return self._call_messages(
                system="You are a senior data analyst providing factual business insights.",
                user_content=prompt,
                max_tokens=250,
            ).strip()
        except Exception as e:
            logger.warning("Anthropic insight generation failed: %s", e)
            return ""

    def generate_ai_suggestions(
        self,
        dataset_context: dict[str, Any],
    ) -> list[str]:
        if not self.is_configured():
            return []
        try:
            compact_cols = [
                f"{c['name']} ({c.get('semantic_type', 'UNKNOWN')})"
                for t in dataset_context.get("tables", [])
                for c in t.get("columns", [])
            ]
            prompt = f"""Dataset: {dataset_context.get('dataset_name')}
Columns: {', '.join(compact_cols)}
Generate 5 analytical questions for this data. Return JSON ONLY: {{"suggestions": ["q1", "q2"]}}"""
            raw = self._call_messages(
                system="You are an analytical assistant. Return raw JSON only.",
                user_content=prompt,
                max_tokens=250,
            )
            parsed = _extract_json(raw)
            return [s.strip() for s in parsed.get("suggestions", []) if isinstance(s, str) and s.strip()]
        except Exception as e:
            logger.warning("Anthropic suggestions generation failed: %s", e)
            return []

    def generate_business_explanation(
        self,
        explanation_type: str,
        evidence: dict[str, Any],
        max_tokens: int = 650,
        corrective_feedback: Optional[str] = None,
    ) -> dict[str, Any]:
        from .explanation_prompts import (
            EXPLANATION_SYSTEM_PROMPT,
            build_prediction_prompt,
            build_forecast_prompt,
        )

        user_prompt = (
            build_prediction_prompt(evidence, corrective_feedback=corrective_feedback)
            if explanation_type == "prediction"
            else build_forecast_prompt(evidence, corrective_feedback=corrective_feedback)
        )

        system_instruction = (
            EXPLANATION_SYSTEM_PROMPT
            + "\nIMPORTANT: Return ONLY raw JSON without markdown code block fences (no ```json)."
        )
        raw = self._call_messages(
            system=system_instruction,
            user_content=user_prompt,
            max_tokens=max_tokens,
        )
        return _extract_json(raw)


# Provider Registry
def get_llm_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseLLMProvider:
    """Factory creating an LLM provider based on provider name or environment configuration."""
    name = (provider_name or os.environ.get("LLM_PROVIDER", "")).strip().lower()

    # Auto-detect if name not specified
    if not name:
        if os.environ.get("OPENAI_API_KEY", "").strip():
            name = "openai"
        elif os.environ.get("GROQ_API_KEY", "").strip():
            name = "groq"
        elif os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip():
            name = "gemini"
        elif os.environ.get("ANTHROPIC_API_KEY", "").strip():
            name = "anthropic"
        elif os.environ.get("LLM_BASE_URL", "").strip():
            name = "custom"
        else:
            name = "openai"  # default fallback provider

    if name in ("groq",):
        return OpenAICompatibleProvider(
            provider_id="groq",
            display_name="Groq",
            default_model="llama-3.3-70b-versatile",
            env_key_name="GROQ_API_KEY",
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
            model=model,
        )

    if name in ("gemini", "google"):
        return OpenAICompatibleProvider(
            provider_id="gemini",
            display_name="Google Gemini",
            default_model="gemini-1.5-flash",
            env_key_name="GEMINI_API_KEY" if os.environ.get("GEMINI_API_KEY") else "GOOGLE_API_KEY",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=api_key,
            model=model,
        )

    if name in ("anthropic", "claude"):
        return AnthropicProvider(api_key=api_key, model=model)

    if name in ("ollama", "local_ollama"):
        ollama_base = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
        if not ollama_base.endswith("/v1") and not ollama_base.endswith("/v1/"):
            ollama_base = ollama_base.rstrip("/") + "/v1"
        return OpenAICompatibleProvider(
            provider_id="ollama",
            display_name="Ollama (Local)",
            default_model="llama3.2",
            env_key_name="OLLAMA_API_KEY",
            base_url=ollama_base,
            api_key=api_key or "ollama",
            model=model or os.environ.get("OLLAMA_MODEL", "llama3.2"),
        )

    if name in ("custom", "deepseek", "vllm", "local"):
        custom_base = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
        return OpenAICompatibleProvider(
            provider_id="custom",
            display_name="Custom / OpenAI-Compatible",
            default_model="default",
            env_key_name="LLM_API_KEY",
            base_url=custom_base,
            api_key=api_key,
            model=model,
        )

    # Default: OpenAI
    return OpenAICompatibleProvider(
        provider_id="openai",
        display_name="OpenAI",
        default_model="gpt-4o-mini",
        env_key_name="OPENAI_API_KEY",
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
        api_key=api_key,
        model=model,
    )


def list_available_providers() -> list[dict[str, Any]]:
    """Lists supported LLM providers and their configuration status."""
    providers_def = [
        {
            "id": "openai",
            "name": "OpenAI",
            "env_key": "OPENAI_API_KEY",
            "default_model": "gpt-4o-mini",
            "models": ["gpt-4o-mini", "gpt-4o", "o3-mini"],
        },
        {
            "id": "ollama",
            "name": "Ollama (Local)",
            "env_key": "OLLAMA_BASE_URL",
            "default_model": "llama3.2",
            "models": ["llama3.2", "mistral", "qwen2.5", "phi3", "llama3.1:8b"],
        },
        {
            "id": "groq",
            "name": "Groq",
            "env_key": "GROQ_API_KEY",
            "default_model": "llama-3.3-70b-versatile",
            "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "env_key": "GEMINI_API_KEY",
            "default_model": "gemini-1.5-flash",
            "models": ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"],
        },
        {
            "id": "anthropic",
            "name": "Anthropic Claude",
            "env_key": "ANTHROPIC_API_KEY",
            "default_model": "claude-3-5-sonnet-20241022",
            "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        },
        {
            "id": "custom",
            "name": "Custom / OpenAI-Compatible (DeepSeek, vLLM)",
            "env_key": "LLM_BASE_URL",
            "default_model": "default",
            "models": ["deepseek-chat", "llama3.2", "mistral"],
        },
    ]

    out = []
    for p in providers_def:
        if p["id"] == "ollama":
            # Local Ollama is ready out-of-the-box on localhost:11434/v1
            configured = True
        else:
            env_val = os.environ.get(p["env_key"], "").strip()
            if p["id"] == "gemini" and not env_val:
                env_val = os.environ.get("GOOGLE_API_KEY", "").strip()
            configured = bool(env_val)
        out.append({
            "id": p["id"],
            "name": p["name"],
            "configured": configured,
            "default_model": p["default_model"],
            "models": p["models"],
        })
    return out
