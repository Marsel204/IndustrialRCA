"""DeepSeek transport adapter with native tool calls and explicit failure results.

Simulation belongs in injected test clients, never in a live provider fallback.
"""

import logging
import os
from collections.abc import Generator
from typing import Any
from weakref import WeakSet

from dotenv import load_dotenv
from openai import OpenAI

from industrial_rca.config import ENV_FILE

logger = logging.getLogger(__name__)
_ACTIVE_CLIENTS: WeakSet = WeakSet()


def get_active_deepseek_clients() -> list["DeepSeekClient"]:
    return list(_ACTIVE_CLIENTS)


def reconfigure_all_deepseek_clients(
    api_key=None, base_url=None, default_model=None
) -> None:
    for client in get_active_deepseek_clients():
        client.reconfigure(api_key, base_url, default_model)


class DeepSeekClient:
    """Small provider boundary shared by the diagnostic agent and copilot."""

    def __init__(
        self, api_key=None, base_url=None, default_model=None, register_active=True
    ):
        if ENV_FILE.exists():
            load_dotenv(ENV_FILE, override=False)
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        )
        self.default_model = default_model or os.getenv(
            "DEEPSEEK_MODEL", "deepseek-chat"
        )
        self._init_client()
        if register_active:
            _ACTIVE_CLIENTS.add(self)

    def _init_client(self) -> None:
        old_client = getattr(self, "client", None)
        self.client = None
        self.is_live = False
        self.initialization_error = (
            "DeepSeek is unavailable: configure a valid API key."
        )
        if old_client is not None:
            old_client.close()
        key = (self.api_key or "").strip()
        if not key or key.lower() in {
            "mock",
            "test",
            "dummy",
            "your_deepseek_api_key_here",
        }:
            return
        try:
            self.client = OpenAI(
                api_key=key, base_url=self.base_url, timeout=30.0, max_retries=0
            )
            self.is_live = True
            self.initialization_error = ""
        except Exception as exc:
            self.initialization_error = f"DeepSeek initialization failed: {exc}"
            logger.warning(self.initialization_error)

    def reconfigure(self, api_key=None, base_url=None, default_model=None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY")
        if base_url is not None:
            self.base_url = base_url
        if default_model is not None:
            self.default_model = default_model
        self._init_client()

    @staticmethod
    def _failure(model: str, error: str) -> dict[str, Any]:
        return {
            "success": False,
            "is_mock": False,
            "model": model,
            "error": error,
            "content": "",
            "reasoning_content": "",
            "tool_calls": [],
            "usage": {},
        }

    def _request(self, messages, model, temperature, max_tokens, **options):
        params = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            **options,
        }
        if "reasoner" not in model:
            params["temperature"] = temperature
        return self.client.chat.completions.create(**params)

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
    ) -> dict[str, Any]:
        target_model = model or self.default_model
        if not self.is_live or self.client is None:
            return self._failure(target_model, self.initialization_error)
        options = {}
        if response_format is not None:
            options["response_format"] = response_format
        if tools is not None:
            options["tools"] = tools
            options["tool_choice"] = tool_choice or "auto"
        try:
            response = self._request(
                messages, target_model, temperature, max_tokens, **options
            )
            message = response.choices[0].message
            usage = response.usage
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            details = getattr(usage, "prompt_tokens_details", None)
            cached = (
                getattr(details, "cached_tokens", 0)
                or getattr(usage, "prompt_cache_hit_tokens", 0)
                or 0
            )
            return {
                "success": True,
                "is_mock": False,
                "model": target_model,
                "content": message.content or "",
                "reasoning_content": getattr(message, "reasoning_content", None) or "",
                "tool_calls": [
                    call.model_dump(exclude_none=True)
                    for call in (getattr(message, "tool_calls", None) or [])
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                    "prompt_cache_hit_tokens": cached,
                    "prompt_cache_miss_tokens": max(0, prompt_tokens - cached),
                },
            }
        except Exception as exc:
            logger.warning("DeepSeek completion failed: %s", exc)
            return self._failure(target_model, str(exc))

    def chat(self, messages, model=None) -> str:
        result = self.chat_completion(messages, model=model)
        return (
            result.get("content", "")
            if result["success"]
            else f"AI unavailable: {result['error']}"
        )

    def chat_completion_stream(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Generator[dict[str, str], None, None]:
        target_model = model or self.default_model
        if not self.is_live or self.client is None:
            yield {
                "error": self.initialization_error,
                "content": "",
                "reasoning_content": "",
            }
            return
        response = None
        try:
            response = self._request(
                messages, target_model, temperature, max_tokens, stream=True
            )
            for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None) or ""
                reasoning = getattr(delta, "reasoning_content", None) or ""
                if content or reasoning:
                    yield {"content": content, "reasoning_content": reasoning}
        except Exception as exc:
            logger.warning("DeepSeek stream failed: %s", exc)
            yield {"error": str(exc), "content": "", "reasoning_content": ""}
        finally:
            if response is not None and hasattr(response, "close"):
                response.close()

    def test_connection(self) -> dict[str, Any]:
        result = self.chat_completion(
            [{"role": "user", "content": "Respond with DEEPSEEK_ONLINE."}],
            max_tokens=20,
        )
        return {
            "status": "ONLINE" if result["success"] else "UNAVAILABLE",
            "is_live": self.is_live and result["success"],
            "model": result["model"],
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "response": result["content"].strip(),
            "error": result.get("error"),
            "reasoning_sample": None,
            "usage": result["usage"],
        }
