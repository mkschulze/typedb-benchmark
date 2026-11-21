import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import CONFIGURATIONS, RunRequest
from .providers import ModelDefinition, load_models
from .runner import RunService
from .storage import RunStore

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def create_app(database_path=None, model_definitions=None, provider=None, typedb_store=None):
    from .domain import load_cases, load_gold, load_sources, reference_answer, sql_answer
    from .typedb_store import TypeDBStore

    cases = load_cases()
    sources = load_sources()
    gold = load_gold()
    case_index = {case["id"]: case for case in cases}
    definitions = (
        load_models()
        if model_definitions is None
        else [
            item if isinstance(item, ModelDefinition) else ModelDefinition.model_validate(item)
            for item in model_definitions
        ]
    )
    if len({model.id for model in definitions}) != len(definitions):
        raise ValueError("Model IDs must be unique")
    store = RunStore(
        database_path or os.environ.get("BENCHMARK_DB_PATH", ROOT / ".runtime/benchmark.sqlite3")
    )
    typedb = typedb_store or TypeDBStore()
    service = RunService(store, cases, sources, gold, definitions, typedb, sql_answer, provider)

    @asynccontextmanager
    async def lifespan(app):
        service.start()
        try:
            yield
        finally:
            await service.stop()

    app = FastAPI(title="Tax Context Benchmark", version="0.1.0", lifespan=lifespan)
    app.state.service = service

    def case_or_404(case_id):
        case = case_index.get(case_id)
        if case is None:
            raise HTTPException(404, "Case not found")
        return case

    def run_or_404(run_id):
        run = store.get(run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        return run

    async def database_health():
        try:
            return await asyncio.wait_for(asyncio.to_thread(typedb.health), timeout=4)
        except Exception:
            return {
                "available": False,
                "seeded": False,
                "message": "TypeDB is unavailable; start the database and seed the case corpus",
            }

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "typedb": await database_health(),
            "legal_review": "provisional",
            "retrieval_mode": service.retriever.mode,
        }

    @app.get("/api/cases")
    def get_cases():
        return cases

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str):
        return case_or_404(case_id)

    @app.get("/api/cases/{case_id}/reference")
    def get_reference(case_id: str):
        return {
            "answer": reference_answer(case_or_404(case_id)),
            "kind": "reference",
            "review_status": "provisional",
        }

    @app.get("/api/sources")
    def get_sources():
        return sources

    @app.get("/api/models")
    def get_models():
        return [model.public() for model in definitions]

    @app.get("/api/configurations")
    def configurations():
        return CONFIGURATIONS

    @app.get("/api/runs")
    def get_runs():
        return store.list()

    @app.post("/api/runs", status_code=202)
    async def create_run(request: RunRequest):
        unknown_cases = set(request.case_ids) - case_index.keys()
        if unknown_cases:
            raise HTTPException(422, "One or more selected cases do not exist")
        unknown_models = set(request.model_ids) - service.models.keys()
        if unknown_models:
            raise HTTPException(422, "One or more selected models do not exist")
        if any(not service.models[model_id].configured for model_id in request.model_ids):
            raise HTTPException(
                422, "Configure the selected model endpoint and its server-side API key before starting a run"
            )
        if any(configuration.startswith("typedb_") for configuration in request.configurations):
            result = await database_health()
            if not result.get("available") or not result.get("seeded"):
                raise HTTPException(
                    503, "TypeDB is not ready. Start the database and run the seed command first"
                )
        try:
            return await service.enqueue(request)
        except ValueError as error:
            raise HTTPException(429, str(error)) from error

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        return run_or_404(run_id)

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str):
        run_or_404(run_id)
        return service.cancel(run_id)

    @app.get("/api/runs/{run_id}/export")
    def export_run(run_id: str):
        return JSONResponse(
            run_or_404(run_id),
            headers={"Content-Disposition": f'attachment; filename="benchmark-{run_id}.json"'},
        )

    frontend = ROOT / "frontend/dist"
    if (frontend / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend_page(path: str):
        if path.startswith("api/") or path == "api":
            raise HTTPException(404, "Not found")
        asset = (frontend / path).resolve()
        if asset.is_relative_to(frontend.resolve()) and asset.is_file():
            return FileResponse(asset)
        if Path(path).suffix:
            raise HTTPException(404, "Not found")
        index = frontend / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {
                "message": "Frontend is not built yet. Run npm run build in frontend/, or start Vite on port 5173."
            }
        )

    return app
