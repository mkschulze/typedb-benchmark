import ipaddress
import json
import os
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    max_output_tokens: int = Field(default=2048, ge=128, le=8192)
    input_price_per_million: float | None = Field(default=None, ge=0)
    output_price_per_million: float | None = Field(default=None, ge=0)
    cached_input_price_per_million: float | None = Field(default=None, ge=0)
    price_date: str | None = None

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


def load_models() -> list[ModelDefinition]:
    raw = os.environ.get("MODELS_JSON")
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
    pass


class ChatProvider:
    async def complete(self, model: ModelDefinition, messages: list[dict]) -> tuple[str, dict]:
        key = os.environ.get(model.api_key_env)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        payload = {
            "model": model.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": model.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10)) as client:
                response = await client.post(
                    f"{model.base_url}/chat/completions", json=payload, headers=headers
                )
                if response.is_error:
                    raise ProviderError(
                        f"Model endpoint returned HTTP {response.status_code}. Check its server-side configuration."
                    )
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise ProviderError("Model endpoint returned no text content")
                return content, data.get("usage") or {}
        except httpx.TimeoutException as error:
            raise ProviderError("Model endpoint timed out after 90 seconds") from error
        except httpx.RequestError as error:
            raise ProviderError("Could not connect to the configured model endpoint") from error
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError("Model endpoint returned an invalid chat-completions response") from error
