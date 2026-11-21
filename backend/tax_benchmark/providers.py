import ipaddress
import json
import math
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def is_loopback(url: str) -> bool:
    hostname = urlsplit(url).hostname or ""
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


class ModelDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    name: str = Field(min_length=1, max_length=150)
    model: str = Field(min_length=1, max_length=200)
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = Field(default="OPENAI_API_KEY", pattern=r"^[A-Z][A-Z0-9_]*$")
    provider: str = "OpenAI-compatible"
    protocol: Literal["openai", "anthropic"] = "openai"
    max_output_tokens: int = Field(default=2048, ge=128, le=8192)
    token_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    send_temperature: bool = True
    json_mode: bool = True
    anthropic_version: str = Field(default="2026-10-21", pattern=r"^\d{4}-\d{2}-\d{2}$")
    input_price_per_million: float | None = Field(default=None, ge=0)
    output_price_per_million: float | None = Field(default=None, ge=0)
    cached_input_price_per_million: float | None = Field(default=None, ge=0)
    price_date: str | None = None

    @model_validator(mode="before")
    @classmethod
    def protocol_defaults(cls, value):
        if isinstance(value, dict) and value.get("protocol") == "anthropic":
            return {
                "base_url": "https://api.anthropic.com/v1",
                "api_key_env": "ANTHROPIC_API_KEY",
                **value,
            }
        return value

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value):
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Model base_url must be an HTTP(S) URL without embedded credentials or query parameters"
            )
        if parsed.scheme != "https" and not is_loopback(value):
            raise ValueError("Hosted model endpoints must use HTTPS")
        return value.rstrip("/")

    @property
    def configured(self):
        return self.model != "set-a-model-id" and (
            bool(os.environ.get(self.api_key_env)) or is_loopback(self.base_url)
        )

    def public(self):
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "configured": self.configured,
            "model": self.model,
        }

    def generation_settings(self) -> dict:
        native_claude = self.protocol == "anthropic"
        settings = {
            "protocol": self.protocol,
            "max_output_tokens": self.max_output_tokens,
            "token_parameter": "max_tokens" if native_claude else self.token_parameter,
            "temperature": 0 if self.send_temperature and not native_claude else None,
            "json_mode": self.json_mode and not native_claude,
        }
        if native_claude:
            settings["anthropic_version"] = self.anthropic_version
        return settings


def load_models() -> list[ModelDefinition]:
    raw = os.environ.get("MODELS_JSON")
    catalogue = Path(__file__).resolve().parents[2] / "config" / "models.json"
    if not raw and catalogue.is_file():
        raw = catalogue.read_text(encoding="utf-8")
    if not raw:
        return [
            ModelDefinition(id="configure-model", name="Configure an LLM endpoint", model="set-a-model-id")
        ]
    definitions = [ModelDefinition.model_validate(item) for item in json.loads(raw)]
    if len({model.id for model in definitions}) != len(definitions):
        raise ValueError("MODELS_JSON model IDs must be unique")
    return definitions


def parse_action(content: str) -> dict:
    # Strict JSON keeps repair attempts visible rather than silently guessing an answer.
    parsed = json.loads(content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("action"), str):
        raise ValueError("Model must return a JSON object with an action")
    return parsed


class ProviderError(RuntimeError):
    def __init__(self, message: str, usage: dict | None = None):
        super().__init__(message)
        self.usage = usage


def _token_counts(value, names: tuple[str, ...]) -> dict:
    if not isinstance(value, dict):
        return {}
    return {name: value[name] for name in names if type(value.get(name)) is int and value[name] >= 0}


def _normalize_usage(usage, protocol: str) -> dict:
    if not isinstance(usage, dict):
        return {}
    normalized = {}
    cost = usage.get("cost")
    if (type(cost) is int and cost >= 0) or (type(cost) is float and math.isfinite(cost) and cost >= 0):
        normalized["cost"] = cost
    if protocol == "openai":
        normalized.update(_token_counts(usage, ("prompt_tokens", "completion_tokens", "total_tokens")))
        for name, counters in (
            ("prompt_tokens_details", ("cached_tokens", "cache_write_tokens", "audio_tokens", "image_tokens", "text_tokens")),
            ("completion_tokens_details", ("reasoning_tokens", "audio_tokens", "accepted_prediction_tokens", "rejected_prediction_tokens")),
        ):
            details = _token_counts(usage.get(name), counters)
            if details:
                normalized[name] = details
        return normalized

    counts = _token_counts(
        usage, ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    )
    if all(name in counts for name in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")):
        # Claude's input_tokens excludes both cache reads and cache writes.
        normalized["prompt_tokens"] = (
            counts["input_tokens"] + counts["cache_read_input_tokens"] + counts["cache_creation_input_tokens"]
        )
    if "output_tokens" in counts:
        normalized["completion_tokens"] = counts["output_tokens"]
    details = {}
    if "cache_read_input_tokens" in counts:
        details["cached_tokens"] = counts["cache_read_input_tokens"]
    if "cache_creation_input_tokens" in counts:
        details["cache_write_tokens"] = counts["cache_creation_input_tokens"]
        normalized["cache_creation_input_tokens"] = counts["cache_creation_input_tokens"]
    if details:
        normalized["prompt_tokens_details"] = details
    creation = _token_counts(usage.get("cache_creation"), ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens"))
    if creation:
        normalized["cache_creation"] = creation
    thinking = _token_counts(usage.get("output_tokens_details"), ("thinking_tokens",))
    if thinking:
        normalized["completion_tokens_details"] = {"reasoning_tokens": thinking["thinking_tokens"]}
    return normalized


def _anthropic_text(data: dict) -> str:
    blocks = data["content"]
    if not isinstance(blocks, list):
        raise ValueError("Invalid content blocks")
    texts = []
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("type"), str):
            raise ValueError("Invalid content block")
        if block["type"] == "text":
            if not isinstance(block.get("text"), str):
                raise ValueError("Invalid text block")
            texts.append(block["text"])
    return "".join(texts)


class ChatProvider:
    async def complete(self, model: ModelDefinition, messages: list[dict]) -> tuple[str, dict]:
        key = os.environ.get(model.api_key_env)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        settings = model.generation_settings()
        payload = {"model": model.model, "messages": messages, settings["token_parameter"]: model.max_output_tokens}
        endpoint = "chat/completions"
        if model.protocol == "anthropic":
            endpoint = "messages"
            headers["anthropic-version"] = model.anthropic_version
            payload["messages"] = [message for message in messages if message["role"] != "system"]
            system = [message["content"] for message in messages if message["role"] == "system"]
            if system:
                payload["system"] = "\n\n".join(system)
            # API version 2026-10-21 rejects temperature, top_p and top_k.
        else:
            if settings["temperature"] is not None:
                payload["temperature"] = settings["temperature"]
            if settings["json_mode"]:
                payload["response_format"] = {"type": "json_object"}
        if (
            urlsplit(model.base_url).hostname == "openrouter.ai"
            and model.input_price_per_million is not None
            and model.output_price_per_million is not None
        ):
            payload["provider"] = {
                "max_price": {
                    "prompt": model.input_price_per_million,
                    "completion": model.output_price_per_million,
                },
                "require_parameters": True,
            }
        usage = None
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10)) as client:
                response = await client.post(
                    f"{model.base_url}/{endpoint}", json=payload, headers=headers
                )
                if response.is_error:
                    raise ProviderError(
                        f"Model endpoint returned HTTP {response.status_code}. Check its server-side configuration."
                    )
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Invalid completion response")
                usage = _normalize_usage(data.get("usage"), model.protocol)
                metadata = {
                    name: data[name] for name in ("id", "model", "provider", "service_tier")
                    if isinstance(data.get(name), str)
                }
                if metadata:
                    usage["_response"] = metadata
                content = _anthropic_text(data) if model.protocol == "anthropic" else data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ProviderError("Model endpoint returned no text content", usage=usage)
                return content, usage
        except httpx.TimeoutException:
            raise ProviderError("Model endpoint timed out after 90 seconds") from None
        except httpx.RequestError:
            raise ProviderError("Could not connect to the configured model endpoint") from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("Model endpoint returned an invalid completion response", usage=usage) from None
