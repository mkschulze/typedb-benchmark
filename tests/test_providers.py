import pytest
from tax_benchmark.providers import ModelDefinition, parse_action


def test_action_parser_rejects_non_objects_and_fenced_prose():
    assert parse_action('{"action":"case_facts"}')["action"] == "case_facts"
    with pytest.raises(ValueError):
        parse_action("[1, 2]")
    with pytest.raises(ValueError):
        parse_action('Here is my answer: {"action":"final"}')


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
