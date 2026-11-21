from fastapi.testclient import TestClient
from tax_benchmark.api import create_app


def test_case_catalogue_and_unknown_case(tmp_path):
    with TestClient(create_app(database_path=tmp_path / "test.sqlite")) as client:
        cases = client.get("/api/cases").json()
        assert len(cases) >= 10
        assert cases[0]["review_status"] == "provisional"
        assert "gold" not in cases[0]
        assert client.get("/api/cases/not-a-case").status_code == 404


def test_unconfigured_model_rejected_before_work(tmp_path, monkeypatch):
    monkeypatch.delenv("BENCHMARK_TEST_KEY", raising=False)
    models = [
        {
            "id": "hosted",
            "name": "Hosted",
            "model": "example",
            "base_url": "https://example.com/v1",
            "api_key_env": "BENCHMARK_TEST_KEY",
        }
    ]
    with TestClient(create_app(database_path=tmp_path / "test.sqlite", model_definitions=models)) as client:
        case_id = client.get("/api/cases").json()[0]["id"]
        response = client.post(
            "/api/runs", json={"case_ids": [case_id], "model_ids": ["hosted"], "configurations": ["rag"]}
        )
        assert response.status_code == 422
        assert client.get("/api/runs").json() == []
        assert "BENCHMARK_TEST_KEY" not in client.get("/api/models").text


def test_invalid_selections_and_missing_database(tmp_path):
    class UnavailableDatabase:
        def health(self):
            return {"available": False, "seeded": False}

    local = [{"id": "local", "name": "Local", "model": "example", "base_url": "http://localhost:11434/v1"}]
    with TestClient(
        create_app(
            database_path=tmp_path / "test.sqlite",
            model_definitions=local,
            typedb_store=UnavailableDatabase(),
        )
    ) as client:
        case_id = client.get("/api/cases").json()[0]["id"]
        base = {"case_ids": [case_id], "model_ids": ["local"], "configurations": ["rag"]}
        assert client.post("/api/runs", json={**base, "case_ids": ["missing"]}).status_code == 422
        assert client.post("/api/runs", json={**base, "case_ids": [case_id, case_id]}).status_code == 422
        assert client.post("/api/runs", json={**base, "repetitions": 0}).status_code == 422
        assert (
            client.post("/api/runs", json={**base, "configurations": ["typedb_functions"]}).status_code == 503
        )
        assert client.get("/api/runs/unknown/export").status_code == 404
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.post("/api/runs", json={**base, "model_ids": ["missing"]}).status_code == 422
        assert client.get("/api/runs").json() == []


def test_production_frontend_serves_self_hosted_fonts(tmp_path, monkeypatch):
    import tax_benchmark.api as api

    frontend = tmp_path / "frontend/dist"
    (frontend / "fonts").mkdir(parents=True)
    (frontend / "index.html").write_text("<html>Application</html>")
    (frontend / "fonts/open-sans.ttf").write_bytes(b"font-data")
    monkeypatch.setattr(api, "ROOT", tmp_path)
    with TestClient(create_app(database_path=tmp_path / "test.sqlite")) as client:
        assert client.get("/").status_code == 200
        assert client.get("/fonts/open-sans.ttf").content == b"font-data"
        assert client.get("/api/unknown").status_code == 404


def test_request_retries_are_idempotent_and_explicit_continuation_does_not_replay(tmp_path):
    from tax_benchmark.providers import ProviderError

    class Offline:
        calls = 0

        async def complete(self, model, messages):
            self.calls += 1
            raise ProviderError("Offline test")

    provider = Offline()
    models = [{"id": "local", "name": "Local", "model": "test", "base_url": "http://localhost:1234/v1"}]
    app = create_app(database_path=tmp_path / "runs.sqlite", model_definitions=models, provider=provider)
    with TestClient(app) as client:
        case = client.get("/api/cases").json()[0]["id"]
        request = {
            "case_ids": [case],
            "model_ids": ["local"],
            "configurations": ["rag"],
            "request_key": "stable-workflow",
        }
        first = client.post("/api/runs", json=request)
        again = client.post("/api/runs", json=request)
        assert first.status_code == again.status_code == 202
        assert first.json()["id"] == again.json()["id"]
        assert client.post("/api/runs", json={**request, "max_steps": 1}).status_code == 409
        client.portal.call(app.state.service.queue.join)
        run = app.state.service.store.get(first.json()["id"])
        run["status"] = "interrupted"
        app.state.service.store.save(run)
        resumed = client.post("/api/runs/" + run["id"] + "/resume")
        assert resumed.status_code == 202
        client.portal.call(app.state.service.queue.join)
        assert provider.calls == 1
        assert client.post("/api/runs/" + run["id"] + "/resume").status_code == 409
        assert client.get("/api/health").json()["worker"]["available"]
