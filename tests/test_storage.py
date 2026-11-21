from tax_benchmark.storage import RunStore


def test_restart_marks_pending_work_interrupted(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite")
    store.save({"id": "pending", "status": "running", "trials": [{"passed": True}]})
    store.save({"id": "done", "status": "completed", "trials": []})
    store.interrupt_pending()
    assert store.get("pending")["status"] == "interrupted"
    assert store.get("pending")["trials"] == [{"passed": True}]
    assert store.get("done")["status"] == "completed"


def test_request_key_index_preserves_legacy_runs_and_prevents_duplicate_jobs(tmp_path):
    import sqlite3

    import pytest
    store=RunStore(tmp_path/'runs.sqlite')
    store.save({'id':'legacy','status':'completed'})
    store.save({'id':'one','request':{'request_key':'unique'},'status':'queued'})
    assert store.get_request_key('unique')['id']=='one'
    with pytest.raises(sqlite3.IntegrityError):
        store.save({'id':'two','request':{'request_key':'unique'},'status':'queued'})
    assert store.get('legacy')['status']=='completed'
