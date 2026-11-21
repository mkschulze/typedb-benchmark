import json

import httpx
import pytest
from tax_benchmark import providers
from tax_benchmark.providers import ChatProvider, ModelDefinition, ProviderError, load_models, parse_action


@pytest.fixture
def mock_http(monkeypatch):
    real_client = httpx.AsyncClient

    def install(data=None, *, status=200, content=None, error=None):
        requests = []

        def handle(request):
            requests.append(request)
            if error is not None:
                raise error("private-response-and-key", request=request)
            if content is not None:
                return httpx.Response(status, content=content)
            return httpx.Response(status, json=data)

        monkeypatch.setattr(
            "tax_benchmark.providers.httpx.AsyncClient",
            lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs),
        )
        return requests

    return install


def openai_response(content='{"action":"case_facts"}', usage=None):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": "test-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": usage,
    }


def anthropic_response(content=None, usage=None):
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-test",
        "content": [{"type": "text", "text": '{"action":"case_facts"}'}] if content is None else content,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": usage,
    }


def test_action_parser_rejects_non_objects_and_fenced_prose():
    assert parse_action('{"action":"case_facts"}')["action"] == "case_facts"
    with pytest.raises(ValueError):
        parse_action("[1, 2]")
    with pytest.raises(ValueError):
        parse_action('Here is my answer: {"action":"final"}')


@pytest.mark.parametrize("price", [0, 2.5, 4, 5])
def test_model_accepts_a_verified_cache_write_price_ceiling(price):
    model = ModelDefinition(
        id="priced", name="Priced", model="test", cache_write_price_per_million=price,
    )

    assert model.cache_write_price_per_million == price


@pytest.mark.parametrize("price", [-1, float("nan"), float("inf"), -float("inf")])
def test_model_rejects_invalid_cache_write_prices(price):
    with pytest.raises(ValueError):
        ModelDefinition(id="priced", name="Priced", model="test", cache_write_price_per_million=price)


def test_model_leaves_unverified_cache_write_pricing_unknown():
    model = ModelDefinition(id="unpriced", name="Unpriced", model="test")

    assert model.cache_write_price_per_million is None


def test_hosted_models_require_a_key_and_loopback_models_do_not(monkeypatch):
    monkeypatch.delenv("BENCHMARK_TEST_KEY", raising=False)
    remote = ModelDefinition(
        id="r", name="Remote", model="m", base_url="https://example.com/v1", api_key_env="BENCHMARK_TEST_KEY"
    )
    local = ModelDefinition(
        id="l",
        name="Local",
        model="m",
        base_url="http://localhost:11434/v1",
        api_key_env="BENCHMARK_TEST_KEY",
    )
    assert not remote.configured
    assert local.configured
    with pytest.raises(ValueError):
        ModelDefinition(id="secret", name="Bad", model="m", base_url="https://user:password@example.com/v1")


async def test_anthropic_uses_native_endpoint_and_separates_system_prompts(monkeypatch, mock_http):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "stub-anthropic-key")
    requests = mock_http(anthropic_response())
    model = ModelDefinition(id="claude", name="Claude", model="claude-test", protocol="anthropic")
    messages = [
        {"role": "system", "content": "Return only JSON."},
        {"role": "system", "content": "Use the action protocol."},
        {"role": "user", "content": "Start."},
        {"role": "assistant", "content": '{"action":"case_facts"}'},
        {"role": "user", "content": '{"case":"test"}'},
    ]

    content, usage = await ChatProvider().complete(model, messages)

    assert parse_action(content) == {"action": "case_facts"}
    assert usage == {"_response": {"id": "msg_test", "model": "claude-test", "stop_reason": "end_turn"}}
    assert len(requests) == 1
    assert str(requests[0].url) == "https://api.anthropic.com/v1/messages"
    assert requests[0].headers["authorization"] == "Bearer stub-anthropic-key"
    assert requests[0].headers["anthropic-version"] == "2026-10-21"
    assert json.loads(requests[0].content) == {
        "model": "claude-test",
        "system": "Return only JSON.\n\nUse the action protocol.",
        "messages": messages[2:],
        "max_tokens": 2048,
    }
    assert messages[0] == {"role": "system", "content": "Return only JSON."}
    assert model.generation_settings() == {
        "protocol": "anthropic",
        "max_output_tokens": 2048,
        "token_parameter": "max_tokens",
        "temperature": None,
        "json_mode": False,
        "anthropic_version": "2026-10-21",
    }
    assert "api_key_env" not in model.public()


async def test_anthropic_concatenates_text_and_counts_all_input_token_categories(mock_http):
    mock_http(
        anthropic_response(
            content=[
                {"type": "thinking", "thinking": "private reasoning", "signature": "test"},
                {"type": "text", "text": '{"action":'},
                {"type": "text", "text": '"case_facts"}'},
            ],
            usage={
                "input_tokens": 12,
                "output_tokens": 7,
                "cache_read_input_tokens": 20,
                "cache_creation_input_tokens": 30,
                "cache_creation": {"ephemeral_5m_input_tokens": 10, "ephemeral_1h_input_tokens": 20},
                "output_tokens_details": {"thinking_tokens": 3},
            },
        )
    )
    model = ModelDefinition(id="c", name="Claude", model="claude-test", protocol="anthropic")

    content, usage = await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert content == '{"action":"case_facts"}'
    assert usage == {
        "prompt_tokens": 62,
        "completion_tokens": 7,
        "prompt_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 30},
        "cache_creation_input_tokens": 30,
        "cache_creation": {"ephemeral_5m_input_tokens": 10, "ephemeral_1h_input_tokens": 20},
        "completion_tokens_details": {"reasoning_tokens": 3},
        "_response": {"id": "msg_test", "model": "claude-test", "stop_reason": "end_turn"},
    }


async def test_openrouter_keeps_openai_bearer_auth_and_json_payload(monkeypatch, mock_http):
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub-router-key")
    requests = mock_http(openai_response(usage={"prompt_tokens": 5, "completion_tokens": 2}))
    model = ModelDefinition(
        id="router", name="Router", model="vendor/model", provider="OpenRouter",
        base_url="https://openrouter.ai/api/v1", api_key_env="OPENROUTER_API_KEY",
    )

    content, usage = await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert content == '{"action":"case_facts"}'
    assert usage == {
        "prompt_tokens": 5, "completion_tokens": 2,
        "_response": {"id": "chatcmpl-test", "model": "test-model", "stop_reason": "stop"},
    }
    assert str(requests[0].url) == "https://openrouter.ai/api/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer stub-router-key"
    assert "anthropic-version" not in requests[0].headers
    assert json.loads(requests[0].content) == {
        "model": "vendor/model", "messages": [{"role": "user", "content": "JSON please"}],
        "temperature": 0, "max_tokens": 2048, "response_format": {"type": "json_object"},
    }


async def test_openrouter_enforces_configured_dollar_per_million_price_ceiling(mock_http):
    requests = mock_http(openai_response())
    model = ModelDefinition(
        id="router", name="Router", model="vendor/model", base_url="https://openrouter.ai/api/v1",
        input_price_per_million=0.3, output_price_per_million=1.2,
    )

    await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert json.loads(requests[0].content)["provider"] == {
        "max_price": {"prompt": 0.3, "completion": 1.2}, "require_parameters": True,
    }


async def test_openai_explicitly_requests_the_configured_standard_service_tier(mock_http):
    requests = mock_http(openai_response())
    model = ModelDefinition(id="standard", name="Standard", model="gpt-6.2-sol").model_copy(
        update={"service_tier": "default"}
    )

    await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert json.loads(requests[0].content).get("service_tier") == "default"
    assert model.generation_settings().get("service_tier") == "default"


@pytest.mark.parametrize("cost,preserved", [
    (0, True), (2, True), (0.00123, True), (None, False), (True, False), ("0.00123", False),
    (-1, False), (float("inf"), False), (float("nan"), False),
])
async def test_reported_cost_preserves_only_finite_nonnegative_json_numbers(mock_http, cost, preserved):
    data = openai_response(usage={"cost": cost})
    mock_http(content=json.dumps(data).encode())
    model = ModelDefinition(id="m", name="Model", model="test")

    _, usage = await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    if preserved:
        assert usage["cost"] == cost
    else:
        assert "cost" not in usage


@pytest.mark.parametrize("protocol,malformed", [
    ("openai", False), ("openai", True), ("anthropic", False), ("anthropic", True),
])
async def test_invalid_text_preserves_billed_usage_and_response_metadata(mock_http, protocol, malformed):
    if protocol == "anthropic":
        data = anthropic_response(
            content=[{"type": "text", "text": 42}] if malformed else [],
            usage={"input_tokens": 10, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                   "output_tokens": 3, "cost": 0.001},
        )
        expected = {
            "prompt_tokens": 10, "completion_tokens": 3, "cost": 0.001,
            "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "cache_creation_input_tokens": 0,
            "_response": {"id": "msg_test", "model": "claude-test", "stop_reason": "end_turn"},
        }
    else:
        data = openai_response(
            content=42 if malformed else "", usage={"prompt_tokens": 10, "completion_tokens": 3, "cost": 0.001},
        )
        expected = {
            "prompt_tokens": 10, "completion_tokens": 3, "cost": 0.001,
            "_response": {"id": "chatcmpl-test", "model": "test-model", "stop_reason": "stop"},
        }
    mock_http(data)
    model = ModelDefinition(id="m", name="Model", model="test", protocol=protocol)

    with pytest.raises(ProviderError) as error:
        await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert error.value.usage == expected


async def test_reasoning_model_can_omit_unsupported_temperature_and_json_mode(mock_http):
    requests = mock_http(openai_response())
    model = ModelDefinition(
        id="reasoning", name="Reasoning", model="reasoning-model", token_parameter="max_completion_tokens",
        send_temperature=False, json_mode=False, max_output_tokens=1024,
    )

    await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert json.loads(requests[0].content) == {
        "model": "reasoning-model", "messages": [{"role": "user", "content": "JSON please"}],
        "max_completion_tokens": 1024,
    }
    assert model.generation_settings() == {
        "protocol": "openai", "max_output_tokens": 1024, "token_parameter": "max_completion_tokens",
        "temperature": None, "json_mode": False,
    }


@pytest.mark.parametrize("protocol,raw,expected", [
    ("openai", None, {}),
    ("openai", [], {}),
    ("openai", {"prompt_tokens": True, "completion_tokens": -2, "prompt_tokens_details": {"cached_tokens": "0"}}, {}),
    ("openai", {"prompt_tokens": 10, "completion_tokens": 3, "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 2}, "completion_tokens_details": {"reasoning_tokens": 1}},
     {"prompt_tokens": 10, "completion_tokens": 3, "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 2}, "completion_tokens_details": {"reasoning_tokens": 1}}),
    ("anthropic", None, {}),
    ("anthropic", "invalid", {}),
    ("anthropic", {"input_tokens": 12, "output_tokens": 7}, {"completion_tokens": 7}),
    ("anthropic", {"input_tokens": 12, "output_tokens": 7, "cache_read_input_tokens": -1, "cache_creation_input_tokens": 0},
     {"completion_tokens": 7, "cache_creation_input_tokens": 0, "prompt_tokens_details": {"cache_write_tokens": 0}}),
    ("anthropic", {"input_tokens": 12, "output_tokens": 7, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
     {"prompt_tokens": 12, "completion_tokens": 7, "cache_creation_input_tokens": 0, "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}}),
])
async def test_usage_normalization_preserves_unknown_counters(mock_http, protocol, raw, expected):
    mock_http(anthropic_response(usage=raw) if protocol == "anthropic" else openai_response(usage=raw))
    model = ModelDefinition(id="m", name="Model", model="test", protocol=protocol)

    _, usage = await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    metadata = (
        {"id": "msg_test", "model": "claude-test", "stop_reason": "end_turn"}
        if protocol == "anthropic" else {"id": "chatcmpl-test", "model": "test-model", "stop_reason": "stop"}
    )
    assert usage == {**expected, "_response": metadata}


@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
async def test_response_metadata_preserves_actual_model_and_routing_without_response_body(mock_http, protocol):
    data = anthropic_response() if protocol == "anthropic" else openai_response()
    data.update({
        "id": "generation-123", "model": "actual-versioned-model", "provider": "Actual host",
        "service_tier": "standard", "private": "must not be copied",
    })
    mock_http(data)
    model = ModelDefinition(id="m", name="Model", model="requested-alias", protocol=protocol)

    _, usage = await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert usage == {"_response": {
        "id": "generation-123", "model": "actual-versioned-model", "provider": "Actual host",
        "service_tier": "standard", "stop_reason": "end_turn" if protocol == "anthropic" else "stop",
    }}


@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
@pytest.mark.parametrize("status", [401, 429, 500])
async def test_http_errors_hide_response_body_and_do_not_retry(mock_http, protocol, status):
    requests = mock_http({"error": {"message": "private-response-and-key"}}, status=status)
    model = ModelDefinition(id="m", name="Model", model="test", protocol=protocol)

    with pytest.raises(ProviderError, match=f"HTTP {status}") as error:
        await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert "private-response-and-key" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize("error_class", [httpx.ReadTimeout, httpx.ConnectError])
async def test_network_errors_hide_transport_details_and_do_not_retry(mock_http, error_class):
    requests = mock_http(error=error_class)
    model = ModelDefinition(id="m", name="Model", model="test")

    with pytest.raises(ProviderError) as error:
        await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert "private-response-and-key" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize("protocol,data", [
    ("openai", []),
    ("openai", {"choices": []}),
    ("openai", openai_response(None)),
    ("openai", openai_response("")),
    ("openai", openai_response("  ")),
    ("anthropic", {"content": "invalid"}),
    ("anthropic", anthropic_response(content=[])),
    ("anthropic", anthropic_response(content=[{"type": "text", "text": 42}])),
    ("anthropic", anthropic_response(content=[{"type": "text", "text": "  "}])),
    ("anthropic", anthropic_response(content=[None])),
    ("anthropic", anthropic_response(content=[{"type": "thinking", "thinking": "private"}])),
])
async def test_empty_or_malformed_response_has_a_safe_provider_error(mock_http, protocol, data):
    mock_http(data)
    model = ModelDefinition(id="m", name="Model", model="test", protocol=protocol)

    with pytest.raises(ProviderError) as error:
        await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert "private" not in str(error.value)


async def test_non_json_response_has_a_safe_provider_error(mock_http):
    mock_http(content=b"private-response-and-key")
    model = ModelDefinition(id="m", name="Model", model="test")

    with pytest.raises(ProviderError) as error:
        await ChatProvider().complete(model, [{"role": "user", "content": "JSON please"}])

    assert "private-response-and-key" not in str(error.value)


@pytest.mark.parametrize("override", [None, ""])
def test_load_models_uses_repository_catalogue_without_env_override(tmp_path, monkeypatch, override):
    monkeypatch.setattr(providers, "__file__", str(tmp_path / "backend" / "tax_benchmark" / "providers.py"))
    if override is None:
        monkeypatch.delenv("MODELS_JSON", raising=False)
    else:
        monkeypatch.setenv("MODELS_JSON", override)
    config = tmp_path / "config"
    config.mkdir()
    (config / "models.json").write_text(json.dumps([
        {"id": "claude", "name": "Claude", "model": "claude-test", "protocol": "anthropic"}
    ]))

    models = load_models()

    assert [model.id for model in models] == ["claude"]
    assert models[0].api_key_env == "ANTHROPIC_API_KEY"


def test_load_models_env_override_precedes_catalogue_and_missing_catalogue_keeps_placeholder(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "__file__", str(tmp_path / "backend" / "tax_benchmark" / "providers.py"))
    monkeypatch.setenv("MODELS_JSON", '[{"id":"override","name":"Override","model":"test"}]')
    assert [model.id for model in load_models()] == ["override"]
    monkeypatch.delenv("MODELS_JSON")
    assert [model.id for model in load_models()] == ["configure-model"]


@pytest.mark.parametrize('protocol,reason', [('openai','length'),('anthropic','max_tokens')])
async def test_empty_billed_response_keeps_stop_reason_for_diagnosis(mock_http,protocol,reason):
    if protocol=='openai':
        data=openai_response(content='')
        data['choices'][0]['finish_reason']=reason
    else:
        data=anthropic_response(content=[])
        data['stop_reason']=reason
    mock_http(data)
    model=ModelDefinition(id='diagnostic',name='Diagnostic',model='test',protocol=protocol)
    with pytest.raises(ProviderError) as error:
        await ChatProvider().complete(model,[{'role':'user','content':'Return JSON'}])
    assert error.value.usage['_response']['stop_reason']==reason


@pytest.mark.parametrize('protocol',['openai','anthropic'])
async def test_framework_cache_metadata_is_not_sent_as_provider_message_fields(mock_http,protocol):
    requests=mock_http(anthropic_response() if protocol=='anthropic' else openai_response())
    model=ModelDefinition(id='framework',name='Framework',model='test',protocol=protocol)
    messages=[{'role':'system','content':'Return JSON','cache_breakpoint':True},
              {'role':'user','content':'Case facts','cache_breakpoint':True}]
    await ChatProvider().complete(model,messages)
    payload=json.loads(requests[0].content)
    assert payload['messages']==([{'role':'user','content':'Case facts'}] if protocol=='anthropic' else [
        {'role':'system','content':'Return JSON'},{'role':'user','content':'Case facts'}])
    assert messages[1]['cache_breakpoint'] is True
