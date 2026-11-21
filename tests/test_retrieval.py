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


async def test_hybrid_cannot_call_network_without_dated_budget_prices(monkeypatch):
    from tax_benchmark.budget import BudgetError
    monkeypatch.setenv('EMBEDDING_BASE_URL', 'https://example.com/v1')
    monkeypatch.setenv('EMBEDDING_MODEL', 'embed')
    retriever = SourceRetriever([])
    with pytest.raises(BudgetError):
        await retriever.embed(['source'])


async def test_embedding_cost_is_reserved_before_network_and_settled(monkeypatch,tmp_path):
    from datetime import date

    import httpx
    import tax_benchmark.retrieval as retrieval
    from tax_benchmark.budget import ExperimentBudget
    from tax_benchmark.storage import RunStore
    monkeypatch.setenv('EMBEDDING_BASE_URL','https://example.com/v1')
    monkeypatch.setenv('EMBEDDING_MODEL','embed')
    monkeypatch.setenv('EMBEDDING_INPUT_PRICE_PER_MILLION','1')
    monkeypatch.setenv('EMBEDDING_PRICE_DATE',date.today().isoformat())
    budget=ExperimentBudget(RunStore(tmp_path/'budget.sqlite'))
    original=httpx.AsyncClient
    def handle(request):
        assert budget.snapshot()['reserved_eur'] > 0
        return httpx.Response(200,json={'data':[{'index':0,'embedding':[1.0,0.5]}], 'usage':{'prompt_tokens':20}})
    monkeypatch.setattr(retrieval.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    retriever=SourceRetriever([],budget=budget)
    assert await retriever.embed(['source']) == [[1.0,0.5]]
    assert budget.snapshot()['reserved_eur'] == 0
    assert budget.snapshot()['spent_eur'] > 0
    assert retriever.usage_records[0]['reservation_id']


async def test_embedding_reported_cost_above_reservation_blocks_more_spending(monkeypatch,tmp_path):
    from datetime import date

    import httpx
    import tax_benchmark.retrieval as retrieval
    from tax_benchmark.budget import ExperimentBudget
    from tax_benchmark.storage import RunStore
    monkeypatch.setenv('EMBEDDING_BASE_URL','https://example.com/v1')
    monkeypatch.setenv('EMBEDDING_MODEL','embed')
    monkeypatch.setenv('EMBEDDING_INPUT_PRICE_PER_MILLION','1')
    monkeypatch.setenv('EMBEDDING_PRICE_DATE',date.today().isoformat())
    budget=ExperimentBudget(RunStore(tmp_path/'budget.sqlite'))
    original=httpx.AsyncClient
    def handle(request):
        return httpx.Response(200,json={'data':[{'index':0,'embedding':[1.0]}], 'usage':{'prompt_tokens':20,'cost':0.5}})
    monkeypatch.setattr(retrieval.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    retriever=SourceRetriever([],budget=budget)
    await retriever.embed(['source'])
    assert budget.snapshot()['spent_eur'] > 0.5
    assert budget.snapshot()['blocked']
    assert retriever.usage_records[0]['provider_reported_cost_usd']==0.5
