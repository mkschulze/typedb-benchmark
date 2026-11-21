import asyncio
import json
from datetime import date

import pytest
from tax_benchmark.budget import ExperimentBudget
from tax_benchmark.models import RunRequest
from tax_benchmark.providers import ProviderError
from tax_benchmark.runner import measured_cost, usage_totals
from tax_benchmark.storage import RunStore
from test_runner import CASE, service_for


def priced(service):
    model = service.models['local'].model_copy(update={
        'input_price_per_million': 2, 'output_price_per_million': 10,
        'cached_input_price_per_million': 0.1, 'price_date': date.today().isoformat(),
    })
    service.models['local'] = model
    return model


async def test_total_cap_stops_before_network_and_excludes_unattempted_trials(tmp_path):
    class NeverCall:
        async def complete(self, model, messages):
            pytest.fail('Budget guard must run before a paid request')
    service = service_for(tmp_path, NeverCall())
    priced(service)
    service.budget = ExperimentBudget(RunStore(tmp_path / 'zero.sqlite'), limit_eur=0)
    service.enforce_budget = True
    service.start()
    try:
        run = await service.enqueue(RunRequest(case_ids=['case'], model_ids=['local'], configurations=['rag']))
        await asyncio.wait_for(service.queue.join(), 2)
        result = service.store.get(run['id'])
        assert result['status'] == 'interrupted'
        assert result['trials'] == []
        assert result['summary'] == []
        assert 'budget' in result['error'].lower()
    finally:
        await service.stop()


async def test_failed_paid_request_keeps_its_full_reservation(tmp_path):
    class Failing:
        async def complete(self, model, messages):
            raise ProviderError('No response')
    service = service_for(tmp_path, Failing())
    priced(service)
    service.budget = ExperimentBudget(service.store)
    service.enforce_budget = True
    trial = await service.trial('missing', CASE, service.models['local'], 'rag', 1, 2)
    snapshot = service.budget.snapshot()
    assert trial['status'] == 'failed'
    assert snapshot['reserved_eur'] > 0
    assert snapshot['unreported_reservations'] == 1
    assert trial['trace'][0]['reservation_id']


async def test_known_usage_settles_reservation_and_manifest_records_effective_settings(tmp_path):
    class Invalid:
        async def complete(self, model, messages):
            return json.dumps({'action': 'unavailable'}), {
                'prompt_tokens': 100, 'completion_tokens': 10,
                'prompt_tokens_details': {'cached_tokens': 0},
            }
    service = service_for(tmp_path, Invalid())
    model = priced(service)
    service.budget = ExperimentBudget(service.store)
    service.enforce_budget = True
    trial = await service.trial('missing', CASE, model, 'rag', 1, 1)
    snapshot = service.budget.snapshot()
    assert snapshot['spent_eur'] > 0
    assert snapshot['reserved_eur'] == 0
    assert trial['metrics']['cost_usd'] == pytest.approx(0.0003)
    request = RunRequest(case_ids=['case'],model_ids=['local'],configurations=['rag'])
    assert service.manifest(request)['models'][0]['generation_settings'] == model.generation_settings()


def test_cache_writes_do_not_use_plain_input_pricing(tmp_path):
    model = priced(service_for(tmp_path))
    metrics = usage_totals([{'prompt_tokens': 100, 'completion_tokens': 10,
                            'prompt_tokens_details': {'cached_tokens': 0,'cache_write_tokens': 50}}])
    assert measured_cost(model, metrics) is None


def test_reported_provider_cost_cannot_be_released_below_catalogue(tmp_path):
    from tax_benchmark.runner import settlement_cost
    model=priced(service_for(tmp_path))
    usage={'prompt_tokens':100,'completion_tokens':10,'prompt_tokens_details':{'cached_tokens':0},'cost':0.5}
    assert settlement_cost(model,[usage]) == 0.5
    usage['cost']=0.00001
    assert settlement_cost(model,[usage]) == pytest.approx(0.0003)


async def test_embedding_setup_failure_keeps_reported_usage_in_export(tmp_path,monkeypatch):
    import httpx
    import tax_benchmark.retrieval as retrieval
    monkeypatch.setenv('EMBEDDING_BASE_URL','https://example.com/v1')
    monkeypatch.setenv('EMBEDDING_MODEL','embed')
    monkeypatch.setenv('EMBEDDING_INPUT_PRICE_PER_MILLION','1')
    monkeypatch.setenv('EMBEDDING_PRICE_DATE',date.today().isoformat())
    original=httpx.AsyncClient
    def handle(request):
        return httpx.Response(200,json={'data':[], 'usage':{'prompt_tokens':20}})
    monkeypatch.setattr(retrieval.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    service=service_for(tmp_path)
    service.start()
    try:
        run=await service.enqueue(RunRequest(case_ids=['case'],model_ids=['local'],configurations=['rag']))
        await asyncio.wait_for(service.queue.join(),2)
        result=service.store.get(run['id'])
        assert result['status']=='failed'
        assert result['embedding_events'][0]['usage']=={'prompt_tokens':20}
        assert result['embedding_events'][0]['reservation_id']
        assert result['manifest']['retrieval_setup']['embedding_usage'][0]['status']=='failed'
    finally:
        await service.stop()


async def test_billed_empty_response_records_usage_and_settles_charge(tmp_path):
    class EmptyResponse:
        async def complete(self, model, messages):
            raise ProviderError('Model endpoint returned no text content', usage={
                'prompt_tokens':100,'completion_tokens':10,
                'prompt_tokens_details':{'cached_tokens':0},'cost':0.01,
                '_response':{'id':'billable-response'},
            })
    service=service_for(tmp_path,EmptyResponse())
    priced(service)
    service.enforce_budget=True
    trial=await service.trial('missing',CASE,service.models['local'],'rag',1,2)
    assert trial['status']=='failed'
    assert trial['metrics']['input_tokens']==100
    assert trial['trace'][-1]['usage']['_response']['id']=='billable-response'
    assert service.budget.snapshot()['reserved_eur']==0
    assert service.budget.snapshot()['spent_eur'] > 0.01


def test_unreported_cache_write_count_stays_unknown():
    assert usage_totals([{}])['cache_write_tokens'] is None
    assert usage_totals([{'prompt_tokens_details':{'cached_tokens':1}}])['cache_write_tokens'] is None
