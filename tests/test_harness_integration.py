import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from tax_benchmark.api import create_app
from tax_benchmark.models import RunRequest
from test_budget_integration import priced
from test_runner import ANSWER, CASE, service_for


class SequenceProvider:
    def __init__(self, invalid=False):
        self.calls=0
        self.messages=[]
        self.invalid=invalid

    async def complete(self,model,messages):
        self.calls+=1
        self.messages.append(messages)
        actions=[{'action':'case_facts'},{'action':'read_source','source_id':'law'},
                 {'action':'final','answer':ANSWER}]
        return ('invalid' if self.invalid else json.dumps(actions[min(self.calls-1,2)])), {
            'prompt_tokens':10,'completion_tokens':5,'prompt_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}}


@pytest.mark.parametrize('harness',['direct','crewai'])
async def test_harnesses_share_tools_grading_and_durable_model_messages(tmp_path,harness):
    provider=SequenceProvider()
    service=service_for(tmp_path,provider)
    trial=await service.trial('missing',CASE,service.models['local'],'rag',1,3,harness=harness)
    assert trial['passed']
    assert trial['harness']==harness
    assert provider.calls==3
    assert trial['metrics']['tool_calls']==2
    assert len([e for e in trial['trace'] if e['kind']=='model_request'])==3
    assert trial['metrics']['input_tokens']==30


async def test_crewai_cannot_make_more_paid_calls_than_request_cap(tmp_path):
    provider=SequenceProvider(invalid=True)
    service=service_for(tmp_path,provider)
    trial=await service.trial('missing',CASE,service.models['local'],'rag',1,2,harness='crewai')
    assert trial['status']=='failed'
    assert provider.calls==2
    assert trial['metrics']['input_tokens']==20


async def test_crewai_uses_same_budget_gate_before_network(tmp_path):
    provider=SequenceProvider()
    service=service_for(tmp_path,provider)
    priced(service)
    service.models['local']=service.models['local'].model_copy(update={'price_date':'2000-01-01'})
    service.enforce_budget=True
    trial=await service.trial('missing',CASE,service.models['local'],'rag',1,3,harness='crewai')
    assert trial['status']=='interrupted'
    assert not trial['attempted']
    assert provider.calls==0


async def test_crewai_cancel_records_inflight_response_without_following_tool(tmp_path):
    started,release=asyncio.Event(),asyncio.Event()
    class Blocking:
        async def complete(self,model,messages):
            started.set()
            await release.wait()
            return '{"action":"case_facts"}',{'prompt_tokens':10,'completion_tokens':5}
    service=service_for(tmp_path,Blocking())
    service.start()
    try:
        run=await service.enqueue(RunRequest(case_ids=['case'],model_ids=['local'],configurations=['rag'],harness='crewai'))
        await asyncio.wait_for(started.wait(),10)
        service.cancel(run['id'])
        release.set()
        await asyncio.wait_for(service.queue.join(),10)
        result=service.store.get(run['id'])
        assert result['status']=='cancelled'
        assert result['trials'][0]['metrics']['input_tokens']==10
        assert result['trials'][0]['metrics']['tool_calls']==0
    finally:
        await service.stop()


def test_harness_readiness_and_missing_dependency_fail_before_work(tmp_path,monkeypatch):
    import tax_benchmark.api as api
    choices=[{'id':'direct','available':True},{'id':'crewai','available':False}]
    monkeypatch.setattr(api,'available_harnesses',lambda:choices)
    local=[{'id':'local','name':'Local','model':'test','base_url':'http://localhost:1234/v1'}]
    with TestClient(create_app(database_path=tmp_path/'test.sqlite',model_definitions=local)) as client:
        assert client.get('/api/harnesses').json()==choices
        case=client.get('/api/cases').json()[0]['id']
        response=client.post('/api/runs',json={'case_ids':[case],'model_ids':['local'],'configurations':['rag'],'harness':'crewai'})
        assert response.status_code==503
        assert client.get('/api/runs').json()==[]
    assert RunRequest(case_ids=['case'],model_ids=['model'],configurations=['rag']).harness=='direct'


@pytest.mark.parametrize('harness',['direct','crewai'])
async def test_invalid_final_can_be_repaired_with_remaining_calls_in_both_harnesses(tmp_path,harness):
    class Repairing(SequenceProvider):
        async def complete(self,model,messages):
            if self.calls==0:
                self.calls+=1
                return '{"action":"final","answer":{"status":"determined"}}',{'prompt_tokens':10,'completion_tokens':5}
            offset=self.calls
            self.calls-=1
            result=await super().complete(model,messages)
            self.calls=offset+1
            return result
    provider=Repairing()
    service=service_for(tmp_path,provider)
    trial=await service.trial('missing',CASE,service.models['local'],'rag',1,6,harness=harness)
    assert trial['passed']
    assert provider.calls==4
    assert len([e for e in trial['trace'] if e['kind']=='repair'])>=1
