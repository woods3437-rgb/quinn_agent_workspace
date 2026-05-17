from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

import httpx


class LLMResult(dict):
    @property
    def text(self) -> str:
        return str(self.get("text", ""))


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def generate(self, system: str, prompt: str, metadata: dict[str, Any] | None = None) -> LLMResult:
        raise NotImplementedError


class DeterministicProvider(LLMProvider):
    name = "deterministic"

    def generate(self, system: str, prompt: str, metadata: dict[str, Any] | None = None) -> LLMResult:
        return LLMResult(
            text=f"{system}\n\n{prompt}",
            provider=self.name,
            model="deterministic-template",
            fallback=False,
        )


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("CTO_OS_MODEL", "gpt-4.1-mini")

    def generate(self, system: str, prompt: str, metadata: dict[str, Any] | None = None) -> LLMResult:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return LLMResult(text=data["choices"][0]["message"]["content"], provider=self.name, model=self.model, raw=data)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = os.getenv("CTO_OS_MODEL", "claude-3-5-sonnet-latest")

    def generate(self, system: str, prompt: str, metadata: dict[str, Any] | None = None) -> LLMResult:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4000,
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        text = "\n".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        return LLMResult(text=text, provider=self.name, model=self.model, raw=data)


class LLMService:
    def __init__(self) -> None:
        self.fallback = DeterministicProvider()

    def provider(self) -> LLMProvider:
        configured = os.getenv("CTO_OS_LLM_PROVIDER", "deterministic").lower()
        if configured == "openai":
            return OpenAIProvider()
        if configured == "anthropic":
            return AnthropicProvider()
        return self.fallback

    def generate(self, system: str, prompt: str, metadata: dict[str, Any] | None = None) -> LLMResult:
        provider = self.provider()
        try:
            result = provider.generate(system, prompt, metadata)
            result["fallback"] = False
            return result
        except Exception as exc:
            result = self.fallback.generate(system, prompt, metadata)
            result["fallback"] = True
            result["fallback_reason"] = str(exc)
            result["requested_provider"] = provider.name
            return result
