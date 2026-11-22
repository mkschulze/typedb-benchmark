import fcntl
import hashlib
import json
import sqlite3
from copy import deepcopy
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import pytest
from tax_benchmark.budget import ExperimentBudget
from tax_benchmark.storage import RunStore
from tax_benchmark.workflow import API, Coordinator, WorkflowError


class FakeDeployer:
    def __init__(self, store):
        self.store = store
        self.image = "sha256:approved"
        self.deployments = 0
        self.inspections = 0

    def image_id(self):
        self.inspections += 1
        return self.image

    def deploy(self):
        assert not any(run["status"] in {"queued", "running"} for run in self.store.list())
        self.deployments += 1


class FakeAPI:
    def __init__(self, store):
        self.store = store
        self.posts = []
        self.ready = True
        self.configured = True
        self.crash_after_post = False

    def request(self, method, path, payload=None):
        if path == "/api/health":
            return {"status": "ok", "typedb": {"available": True, "seeded": True}}
        if path == "/api/harnesses":
            return [{"id": "crewai", "available": self.ready}]
        if path == "/api/models":
            return [{"id": key, "configured": self.configured}
                    for key in ("claude-sonnet", "openai-sol", "openrouter-deepseek")]
        assert (method, path) == ("POST", "/api/runs")
        self.posts.append(deepcopy(payload))
        prior = self.store.get_request_key(payload["request_key"])
        if prior:
            return prior
        run = {"id": "crew", "status": "queued", "request": payload, "trials": [], "total_trials": 48}
        self.store.save(run)
        if self.crash_after_post:
            raise WorkflowError("Local API connection unavailable")
        return run


@pytest.fixture
def setup(tmp_path):
    store = RunStore(tmp_path / "benchmark.sqlite3")
    budget = ExperimentBudget(store)
    baseline = {"id": "direct", "status": "running", "request": {"harness": "direct"}, "trials": [],
                "manifest": {"dataset_sha256": "data", "sources_sha256": "sources", "gold_sha256": "gold",
                             "system_prompt": "frozen prompt"}}
    store.save(baseline)
    plan = {
        "enabled": True, "project_root": str(tmp_path), "database_path": str(store.path),
        "base_url": "http://127.0.0.1:8001", "wait_for_run_id": "direct",
        "state_path": str(tmp_path / "state.json"), "audit_path": str(tmp_path / "audit.jsonl"),
        "approved_image_id": "sha256:approved",
        "request": {"harness": "crewai", "case_ids": ["dev-01", "dev-03", "dev-05", "dev-07"],
                    "model_ids": ["claude-sonnet", "openai-sol", "openrouter-deepseek"],
                    "configurations": ["rag", "typedb_context", "typedb_functions", "sql"],
                    "repetitions": 1, "max_steps": 6, "request_key": "approved-crew-48"},
        "expected_inputs": {"dataset_sha256": "data", "sources_sha256": "sources", "gold_sha256": "gold",
                            "system_prompt_sha256": hashlib.sha256(b"frozen prompt").hexdigest()},
        "pricing_model": {"id": "openai-sol", "name": "OpenAI Sol", "model": "gpt-6.2-sol",
                          "base_url": "https://api.openai.com/v1", "service_tier": "default",
                          "input_price_per_million": 2, "output_price_per_million": 10,
                          "cached_input_price_per_million": 0.1, "cache_write_price_per_million": 5,
                          "price_date": "2026-11-21"},
        "pricing_source": "https://developers.openai.com/api/docs/models/gpt-6.2-sol",
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    api, deployer = FakeAPI(store), FakeDeployer(store)
    coordinator = Coordinator(path, api=api, deployer=deployer)
    return coordinator, store, budget, baseline, plan, path, api, deployer


def complete(store, run):
    run["status"] = "completed"
    store.save(run)


def test_active_direct_waits_without_deployment_or_paid_enqueue(setup):
    coordinator, _, _, _, _, _, api, deployer = setup
    assert not coordinator.tick()
    assert coordinator.state["status"] == "waiting"
    assert not api.posts and deployer.inspections == deployer.deployments == 0


@pytest.mark.parametrize("status", ["cancelled", "failed", "interrupted"])
def test_unsuccessful_direct_stops_without_replay(setup, status):
    coordinator, store, _, baseline, _, _, api, deployer = setup
    baseline["status"] = status
    store.save(baseline)
    assert coordinator.tick()
    assert status in coordinator.state["reason"]
    assert not api.posts and not deployer.deployments


def test_disabled_plan_stops_only_the_followup(setup):
    coordinator, store, _, baseline, plan, path, api, deployer = setup
    plan["enabled"] = False
    path.write_text(json.dumps(plan))
    assert coordinator.tick()
    assert store.get("direct") == baseline
    assert not api.posts and not deployer.deployments


def test_completed_direct_waits_for_every_stored_pending_job(setup):
    coordinator, store, _, baseline, _, _, api, deployer = setup
    complete(store, baseline)
    store.save({"id": "old-active", "status": "running"})
    for number in range(201):
        store.save({"id": f"history-{number}", "status": "completed"})
    assert not coordinator.tick()
    assert not deployer.deployments and not api.posts
    assert "drain" in coordinator.state["reason"]


def test_drain_deploys_approved_image_and_submits_exact_stable_48_request(setup):
    coordinator, store, _, baseline, plan, _, api, deployer = setup
    complete(store, baseline)
    assert not coordinator.tick()
    assert deployer.deployments == 1
    assert api.posts == [plan["request"]]
    assert coordinator.state["crew_run_id"] == "crew"
    assert json.loads(open(coordinator.state["direct_export_path"]).read()) == baseline
    assert "spent_eur" in coordinator.state["budget"]


@pytest.mark.parametrize("gate", ["harness", "models"])
def test_unavailable_harness_or_model_never_enqueues(setup, gate):
    coordinator, store, _, baseline, _, _, api, deployer = setup
    complete(store, baseline)
    if gate == "harness":
        api.ready = False
    else:
        api.configured = False
    assert not coordinator.tick()
    assert coordinator.state["status"] == "checking"
    assert deployer.deployments == 1 and not api.posts
    api.ready = api.configured = True
    coordinator.tick()
    assert deployer.deployments == 1 and len(api.posts) == 1


@pytest.mark.parametrize("gate", ["source", "image", "prompt", "gold", "dataset"])
def test_hash_or_image_mismatch_stops_without_deployment(setup, gate):
    coordinator, store, _, baseline, _, _, api, deployer = setup
    if gate == "image":
        deployer.image = "sha256:changed"
    else:
        field = {"source": "sources_sha256", "prompt": "system_prompt", "gold": "gold_sha256",
                 "dataset": "dataset_sha256"}[gate]
        baseline["manifest"][field] = "changed"
    complete(store, baseline)
    assert coordinator.tick()
    assert coordinator.state["status"] == "stopped"
    assert not deployer.deployments and not api.posts


def test_image_change_during_readiness_stops_without_redeploy(setup):
    coordinator, store, _, baseline, _, _, api, deployer = setup
    complete(store, baseline)
    api.ready = False
    coordinator.tick()
    deployer.image = "sha256:changed"
    assert coordinator.tick()
    assert deployer.deployments == 1 and not api.posts


def test_restart_adopts_accepted_request_after_lost_post_response(setup):
    coordinator, store, _, baseline, _, path, api, deployer = setup
    complete(store, baseline)
    api.crash_after_post = True
    coordinator.tick()
    assert store.get("crew")["status"] == "queued"
    restarted = Coordinator(path, api=api, deployer=deployer)
    assert not restarted.tick()
    assert restarted.state["crew_run_id"] == "crew"
    assert len(api.posts) == 1 and deployer.deployments == 1
    crew = store.get("crew")
    crew.update(status="interrupted", active_trial={"status": "interrupted"})
    store.save(crew)
    assert restarted.tick()
    assert restarted.state["crew_status"] == "interrupted"
    assert json.loads(open(restarted.state["crew_export_path"]).read()) == crew
    assert Coordinator(path, api=api, deployer=deployer).tick()
    assert len(api.posts) == 1


def add_usage(store, budget, baseline, *, pending=False, kind="model", active=False, **usage_changes):
    reservation = budget.reserve_usd(Decimal("1"), "chat:openai-sol")
    if not pending:
        budget.settle(reservation)
    usage = {"prompt_tokens": 1000, "completion_tokens": 100, "prompt_tokens_details": {"cached_tokens": 100},
             "completion_tokens_details": {"reasoning_tokens": 80},
             "_response": {"id": "chatcmpl-verified", "model": "gpt-6.2-sol", "service_tier": "default"}}
    usage.update(usage_changes)
    trial = {"case_id": "dev-01", "model_id": "openai-sol", "trace": [
        {"kind": "budget", "step": 1, "reservation_id": reservation},
        {"kind": kind, "step": 1, "usage": usage}]}
    if active:
        baseline["active_trial"] = trial
    else:
        baseline["trials"].append(trial)
    store.save(baseline)
    return reservation, usage


@pytest.mark.parametrize("kind,active", [("model", False), ("model_error", True)])
def test_known_native_standard_usage_reconciles_once_with_durable_audit(setup, kind, active):
    coordinator, store, budget, baseline, plan, _, _, _ = setup
    reservation, usage = add_usage(store, budget, baseline, kind=kind, active=active)
    assert not coordinator.tick()
    assert not coordinator.tick()
    with store.connection() as connection:
        charged, state = connection.execute(
            "SELECT charged_units, state FROM experiment_budget_reservations WHERE id=?", (reservation,)).fetchone()
    usd = Decimal("0.00281")  # 900 uncached, 100 cached, 100 output (includes reasoning).
    assert charged == int((usd / budget.usd_per_eur * budget.safety_multiplier * 10**9)
                          .to_integral_value(rounding=ROUND_CEILING))
    assert state == "settled"
    records = [json.loads(line) for line in open(plan["audit_path"])]
    assert [record["event"] for record in records] == ["settlement_proposed", "settlement_applied"]
    assert records[0]["reservation_id"] == reservation
    assert records[0]["pricing_source"] == plan["pricing_source"]
    assert records[0]["usage_sha256"] and "content" not in records[0]
    assert coordinator.state["budget"] == budget.snapshot()


@pytest.mark.parametrize("change,pending", [
    ({"_response": {}}, False),
    ({"_response": {"id": "x", "model": "gpt-6.2-sol", "service_tier": "priority"}}, False),
    ({"_response": {"id": "x", "model": "other", "service_tier": "default"}}, False),
    ({"prompt_tokens": 272001}, False),
    ({"completion_tokens": None}, False),
    ({"prompt_tokens_details": {}}, False),
    ({"completion_tokens": 1000000}, False),  # Proven cost exceeds the reserved ceiling.
    ({}, True),
])
def test_unknown_nonstandard_incomplete_over_ceiling_or_pending_fees_stay_reserved(setup, change, pending):
    coordinator, store, budget, baseline, plan, _, _, _ = setup
    reservation, _ = add_usage(store, budget, baseline, pending=pending, **change)
    before = budget.snapshot()
    coordinator.tick()
    assert budget.snapshot() == before
    with store.connection() as connection:
        assert connection.execute("SELECT state FROM experiment_budget_reservations WHERE id=?",
                                  (reservation,)).fetchone()[0] == ("reserved" if pending else "unreported")
    assert not Path(plan["audit_path"]).exists()


def test_verified_write_ceiling_prices_reported_cache_writes(setup):
    coordinator, store, budget, baseline, _, _, _, _ = setup
    add_usage(store, budget, baseline, prompt_tokens_details={"cached_tokens": 100, "cache_write_tokens": 50})
    coordinator.tick()
    assert budget.snapshot()["unreported_reservations"] == 0
    assert budget.snapshot()["spent_eur"] > 0.003


def test_audit_failure_does_not_release_reservation(setup, monkeypatch):
    coordinator, store, budget, baseline, _, _, _, _ = setup
    add_usage(store, budget, baseline)
    before = budget.snapshot()
    def fail(record):
        raise OSError("disk unavailable")
    monkeypatch.setattr(coordinator, "audit", fail)
    with pytest.raises(OSError):
        coordinator.tick()
    assert budget.snapshot() == before


def test_api_errors_expose_status_without_response_body(monkeypatch):
    class Response:
        is_error = True
        status_code = 503
        text = "secret provider credential"
    monkeypatch.setattr("tax_benchmark.workflow.httpx.request", lambda *args, **kwargs: Response())
    with pytest.raises(WorkflowError, match="HTTP 503") as failure:
        API("http://127.0.0.1:8001").request("POST", "/api/runs", {})
    assert "secret" not in str(failure.value)


def test_only_one_coordinator_can_hold_the_plan_lock(setup):
    coordinator, _, _, _, _, _, api, deployer = setup
    lock_path = coordinator.state_path.with_name(coordinator.state_path.name + ".lock")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(WorkflowError, match="already running"):
            coordinator.run()
    assert not api.posts and not deployer.deployments


def test_readiness_failure_eventually_exits_without_a_paid_request(setup):
    coordinator, store, _, baseline, _, _, api, deployer = setup
    complete(store, baseline)
    api.ready = False
    coordinator.tick()
    coordinator.state["readiness_attempts"] = 59
    assert coordinator.tick()
    assert coordinator.state["status"] == "stopped"
    assert deployer.deployments == 1 and not api.posts


@pytest.mark.parametrize("field,value", [("cache_write_price_per_million", None),
                                         ("service_tier", "priority"),
                                         ("base_url", "https://openrouter.ai/api/v1")])
def test_unverified_pricing_cannot_release_existing_fees(setup, field, value):
    coordinator, store, budget, baseline, _, _, _, _ = setup
    add_usage(store, budget, baseline)
    before = budget.snapshot()
    coordinator.plan["pricing_model"][field] = value
    coordinator.tick()
    assert budget.snapshot() == before


def test_completed_settlement_is_never_rewritten(setup):
    coordinator, store, budget, baseline, plan, _, _, _ = setup
    reservation, _ = add_usage(store, budget, baseline)
    budget.settle(reservation, Decimal("0.5"))
    before = budget.snapshot()
    coordinator.tick()
    assert budget.snapshot() == before
    assert not Path(plan["audit_path"]).exists()


def test_ambiguous_reservation_to_response_mapping_keeps_both_fees_reserved(setup):
    coordinator, store, budget, baseline, _, _, _, _ = setup
    add_usage(store, budget, baseline)
    second = budget.reserve_usd(Decimal("1"), "chat:openai-sol")
    budget.settle(second)
    baseline["trials"][0]["trace"].append({"kind": "budget", "step": 1, "reservation_id": second})
    store.save(baseline)
    before = budget.snapshot()
    coordinator.tick()
    assert budget.snapshot() == before


def test_deployment_holds_the_database_write_gate_until_compose_returns(setup, monkeypatch):
    coordinator, store, _, baseline, _, _, api, deployer = setup
    complete(store, baseline)
    def deploy():
        with sqlite3.connect(store.path, timeout=0) as concurrent:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                concurrent.execute("INSERT INTO runs VALUES ('concurrent', '{}')")
    monkeypatch.setattr(deployer, "deploy", deploy)
    coordinator.tick()
    assert len(api.posts) == 1
    assert store.get("concurrent") is None


def test_new_job_between_initial_drain_and_deploy_is_preserved(setup, monkeypatch):
    coordinator, store, _, baseline, _, _, api, deployer = setup
    complete(store, baseline)
    def image_id():
        store.save({"id": "new-user-job", "status": "queued"})
        return "sha256:approved"
    monkeypatch.setattr(deployer, "image_id", image_id)
    assert not coordinator.tick()
    assert store.get("new-user-job")["status"] == "queued"
    assert not deployer.deployments and not api.posts
