import pytest
from tax_benchmark.retrieval import SourceRetriever


async def test_lexical_retrieval_returns_relevant_sources_and_declares_mode():
    retriever = SourceRetriever(
        [
            {"id": "a", "title": "Certificates", "text": "Exemption certificate withholding"},
            {"id": "b", "title": "Ownership", "text": "Holding shares"},
        ]
    )
    found = await retriever.search("certificate")
    assert found[0]["id"] == "a"
    assert found[0]["retrieval_mode"] == "lexical"


def test_embedding_endpoint_rejects_plaintext_hosted_keys(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://hosted.example/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "embeddings")
    with pytest.raises(ValueError):
        SourceRetriever([])
