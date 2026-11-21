"""Run the approved CrewAI pilot after the direct run, then exit.

Launch with ``python -m tax_benchmark.workflow --plan /absolute/plan.json``.
The host database is authoritative; this process never cancels or resumes runs.
"""

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import time
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .budget import ExperimentBudget
from .models import RunRequest
from .providers import ModelDefinition, is_loopback
from .runner import settlement_cost
from .storage import RunStore, utc_now

TERMINAL = {"completed", "cancelled", "failed", "interrupted"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sync_parent(path):
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    sync_parent(path)


class WorkflowError(RuntimeError):
    pass


class API:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def request(self, method, path, payload=None):
        try:
            response = httpx.request(method, self.base_url + path, json=payload, timeout=8, trust_env=False)
        except httpx.HTTPError as error:
            raise WorkflowError("Local API connection unavailable") from error
        if response.is_error:
            raise WorkflowError(f"Local API returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise WorkflowError("Local API returned invalid JSON") from error


class DockerDeployer:
    def __init__(self, project_root):
        self.project_root = project_root

    def image_id(self):
        result = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", "typedb-benchmark-app:latest"],
            cwd=self.project_root, capture_output=True, text=True, check=True, timeout=10,
        )
        return result.stdout.strip()

    def deploy(self):
        subprocess.run(
            ["docker", "compose", "up", "-d", "--no-build", "app"], cwd=self.project_root,
            capture_output=True, check=True, timeout=60,
        )


class Coordinator:
    def __init__(self, plan_path, *, api=None, deployer=None):
        self.plan_path = Path(plan_path)
        self.plan = json.loads(self.plan_path.read_text())
        for key in ("project_root", "database_path", "state_path", "audit_path"):
            if not Path(self.plan[key]).is_absolute():
                raise WorkflowError(f"{key} must be absolute")
        if not Path(self.plan["database_path"]).is_file():
            raise WorkflowError("The shared experiment database must already exist")
        if not is_loopback(self.plan["base_url"]):
            raise WorkflowError("The coordinator requires a local benchmark API")
        request = RunRequest.model_validate(self.plan["request"])
        key = request.request_key
        self.request = request.model_dump()
        if (
            request.harness != "crewai" or request.total_trials != 48
            or request.repetitions != 1 or request.max_steps != 6
            or set(request.case_ids) != {"dev-01", "dev-03", "dev-05", "dev-07"}
            or set(request.model_ids) != {"claude-sonnet", "openai-sol", "openrouter-deepseek"}
            or set(request.configurations) != {"rag", "typedb_context", "typedb_functions", "sql"}
            or not isinstance(key, str) or not key.strip()
        ):
            raise WorkflowError("The plan must contain the approved 48-trial CrewAI pilot and a stable request_key")
        self.store = RunStore(self.plan["database_path"])
        self.budget = ExperimentBudget(self.store)
        self.api = api or API(self.plan["base_url"])
        self.deployer = deployer or DockerDeployer(self.plan["project_root"])
        self.state_path = Path(self.plan["state_path"])
        identity = digest({name: value for name, value in self.plan.items() if name != "enabled"})
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            "status": "waiting", "plan_sha256": identity, "request_key": key,
        }
        if self.state.get("plan_sha256") != identity:
            raise WorkflowError("The approved plan changed; use its original contents")

    def save(self, status=None, **values):
        self.state.update(values, updated_at=utc_now(), budget=self.budget.snapshot())
        if status:
            self.state["status"] = status
        atomic_json(self.state_path, self.state)
        print(json.dumps({"status": self.state["status"], "reason": self.state.get("reason"),
                          "crew_run_id": self.state.get("crew_run_id")}), flush=True)
        return self.state["status"] in {"completed", "stopped"}

    def audit(self, record):
        path = Path(self.plan["audit_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": utc_now(), **record}, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        sync_parent(path)

    def runs(self):
        # RunStore.list is a UI page of 200; deployment must check every stored job.
        with self.store.connection() as connection:
            return [json.loads(row[0]) for row in connection.execute("SELECT payload FROM runs")]

    def reconcile(self, run):
        pricing = self.plan.get("pricing_model", {})
        source = urlsplit(self.plan.get("pricing_source", ""))
        if (
            pricing.get("id") != "openai-sol" or pricing.get("model") != "gpt-6.2-sol"
            or pricing.get("base_url") != "https://api.openai.com/v1"
            or pricing.get("protocol", "openai") != "openai" or pricing.get("service_tier") != "default"
            or [pricing.get(name) for name in ("input_price_per_million", "output_price_per_million",
                                             "cached_input_price_per_million", "cache_write_price_per_million")]
            != [2, 10, 0.1, 5] or pricing.get("price_date") != "2026-11-21"
            or source.scheme != "https" or source.hostname not in {"openai.com", "developers.openai.com", "platform.openai.com"}
        ):
            return
        try:
            model = ModelDefinition.model_validate(pricing)
        except ValueError:
            return
        trials = list(run.get("trials", [])) + ([run["active_trial"]] if run.get("active_trial") else [])
        for trial in trials:
            if trial.get("model_id") != "openai-sol":
                continue
            trace = trial.get("trace", [])
            for event in trace:
                if (event.get("kind") != "budget" or type(event.get("step")) is not int
                        or event["step"] < 1):
                    continue
                matches = [item for item in trace if item.get("step") == event.get("step")
                           and item.get("kind") in {"model", "model_error"}]
                if len(matches) != 1 or sum(item.get("kind") == "budget" and item.get("step") == event.get("step")
                                            for item in trace) != 1:
                    continue
                usage = matches[0].get("usage", {})
                if not isinstance(usage, dict):
                    continue
                metadata = usage.get("_response", {})
                details = usage.get("prompt_tokens_details", {})
                if not isinstance(metadata, dict) or not isinstance(details, dict):
                    continue
                counts = [usage.get("prompt_tokens"), usage.get("completion_tokens"), details.get("cached_tokens")]
                writes = details.get("cache_write_tokens", 0)
                if (
                    not isinstance(metadata.get("id"), str) or not metadata["id"]
                    or metadata.get("model") != "gpt-6.2-sol"
                    or metadata.get("service_tier") != "default"
                    or any(type(value) is not int or value < 0 for value in [*counts, writes])
                    or counts[0] > 272_000 or counts[2] + writes > counts[0]
                ):
                    continue
                reservation = event.get("reservation_id")
                with self.store.connection() as connection:
                    row = connection.execute(
                        "SELECT reserved_units, state, purpose FROM experiment_budget_reservations WHERE id=?",
                        (reservation,),
                    ).fetchone()
                if not row or row[1] != "unreported" or row[2] != "chat:openai-sol":
                    continue
                cost = settlement_cost(model, [usage])
                if cost is None:
                    continue
                ceiling = int((Decimal(str(cost)) / self.budget.usd_per_eur * self.budget.safety_multiplier
                               * Decimal(1_000_000_000)).to_integral_value(rounding=ROUND_CEILING))
                if ceiling > row[0]:
                    continue
                record = {"run_id": run["id"], "case_id": trial.get("case_id"), "step": event.get("step"),
                          "reservation_id": reservation, "response_id": metadata["id"], "usage_sha256": digest(usage),
                          "actual_usd": cost, "charged_units": ceiling, "previous_reserved_units": row[0],
                          "pricing": pricing, "pricing_source": self.plan["pricing_source"]}
                self.audit({"event": "settlement_proposed", **record})
                # Recheck after the durable proposal: a live worker may have settled meanwhile.
                with self.store.connection() as connection:
                    current = connection.execute(
                        "SELECT state FROM experiment_budget_reservations WHERE id=?", (reservation,),
                    ).fetchone()
                if current and current[0] == "unreported":
                    self.budget.settle(reservation, cost)
                    self.audit({"event": "settlement_applied", **record})

    def verify_inputs(self, baseline):
        manifest = baseline.get("manifest", {})
        actual = {key: manifest.get(key) for key in ("dataset_sha256", "sources_sha256", "gold_sha256")}
        prompt = manifest.get("system_prompt")
        actual["system_prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest() if isinstance(prompt, str) else None
        if actual != self.plan.get("expected_inputs") or any(value is None for value in actual.values()):
            raise WorkflowError("The completed direct run does not match the approved frozen input hashes")

    def tick(self):
        if self.state["status"] in {"completed", "stopped"}:
            return True
        if json.loads(self.plan_path.read_text()).get("enabled") is not True:
            return self.save("stopped", reason="Follow-up disabled; existing runs were left untouched")
        existing = self.store.get_request_key(self.request["request_key"])
        crew_id = self.state.get("crew_run_id") or (existing["id"] if existing else None)
        if crew_id:
            if existing and existing.get("request") != self.request:
                return self.save("stopped", reason="The saved request_key belongs to a different request")
            self.state["crew_run_id"] = crew_id
            crew = self.store.get(crew_id)
            if not crew:
                return self.save("stopped", reason="The recorded CrewAI run is missing; no replay was attempted")
            if crew.get("status") in TERMINAL:
                raw = self.state_path.parent / f"crewai-{crew_id}-export.json"
                summary = self.state_path.parent / f"crewai-{crew_id}-summary.json"
                atomic_json(raw, crew)
                atomic_json(summary, {**{key: crew.get(key) for key in
                            ("id", "status", "total_trials", "completed_trials", "summary", "comparisons")},
                            "budget": self.budget.snapshot()})
                return self.save("completed" if crew["status"] == "completed" else "stopped",
                                 reason=f"CrewAI ended: {crew['status']}; no automatic replay",
                                 crew_export_path=str(raw), crew_summary_path=str(summary), crew_status=crew["status"])
            return self.save("monitoring", reason="CrewAI is running; shared budget remains enforced")
        baseline = self.store.get(self.plan["wait_for_run_id"])
        if not baseline:
            return self.save("stopped", reason="The required direct run is missing")
        if baseline.get("status") in TERMINAL - {"completed"}:
            return self.save("stopped", reason=f"Direct run ended {baseline['status']}; follow-up was not started")
        self.reconcile(baseline)
        if baseline.get("status") != "completed":
            return self.save("waiting", reason="Waiting for the approved direct run to complete")
        if any(run.get("status") in {"queued", "running"} for run in self.runs()):
            return self.save(reason="Waiting for all queued and running jobs to drain")
        direct_export = self.state_path.parent / f"direct-{baseline['id']}-export.json"
        if not direct_export.exists():
            atomic_json(direct_export, baseline)
        self.state["direct_export_path"] = str(direct_export)
        try:
            self.verify_inputs(baseline)
        except WorkflowError as error:
            return self.save("stopped", reason=str(error))
        try:
            if self.deployer.image_id() != self.plan["approved_image_id"]:
                return self.save("stopped", reason="The app image tag changed; the approved image was not deployed")
            if self.state["status"] in {"waiting", "deploying"}:
                with self.store.connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if connection.execute(
                        "SELECT 1 FROM runs WHERE json_extract(payload, '$.status') IN ('queued', 'running') LIMIT 1"
                    ).fetchone():
                        return self.save("waiting", reason="A queued or running job appeared before deployment")
                    self.save("deploying", reason="Deploying the approved image after all jobs drained")
                    self.deployer.deploy()
                self.save("checking", reason="Waiting for CrewAI and selected models to be ready", readiness_attempts=0)
            health = self.api.request("GET", "/api/health")
            harnesses = self.api.request("GET", "/api/harnesses")
            models = self.api.request("GET", "/api/models")
            if (
                health.get("status") != "ok" or not health.get("typedb", {}).get("available")
                or not health.get("typedb", {}).get("seeded")
                or not any(item.get("id") == "crewai" and item.get("available") is True for item in harnesses)
                or not set(self.request["model_ids"]).issubset(
                    {item.get("id") for item in models if item.get("configured") is True})
            ):
                raise WorkflowError("CrewAI, TypeDB, or a selected model is not ready")
            budget = self.budget.snapshot()
            if budget["blocked"] or budget["remaining_eur"] <= 0:
                return self.save("stopped", reason="The shared experiment budget blocks the CrewAI pilot")
            if any(run.get("status") in {"queued", "running"} for run in self.runs()):
                return self.save(reason="Waiting for all queued and running jobs before enqueue")
            self.save("enqueueing", reason="Enqueueing the approved pilot with its stable request_key")
            crew = self.api.request("POST", "/api/runs", self.request)
            return self.save("monitoring", crew_run_id=crew["id"], reason="CrewAI pilot accepted")
        except (WorkflowError, subprocess.SubprocessError, OSError) as error:
            attempts = self.state.get("readiness_attempts", 0) + 1
            return self.save("stopped" if attempts >= 60 else None, readiness_attempts=attempts,
                             reason=str(error) if isinstance(error, WorkflowError) else type(error).__name__)

    def run(self, poll_seconds=5):
        if not 0 < poll_seconds <= 10:
            raise WorkflowError("The poll interval must be greater than zero and at most ten seconds")
        lock_path = self.state_path.with_name(self.state_path.name + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise WorkflowError("This follow-up coordinator is already running") from error
            while not self.tick():
                time.sleep(poll_seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        Coordinator(arguments.plan).run()
    except (WorkflowError, ValueError, KeyError, OSError):
        raise SystemExit("Coordinator stopped: invalid plan or unavailable local state; inspect the state file") from None


if __name__ == "__main__":
    main()
