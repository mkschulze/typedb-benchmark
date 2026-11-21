from tax_benchmark.storage import RunStore


def test_restart_marks_pending_work_interrupted(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite")
    store.save({"id": "pending", "status": "running", "trials": [{"passed": True}]})
    store.save({"id": "done", "status": "completed", "trials": []})
    store.interrupt_pending()
    assert store.get("pending")["status"] == "interrupted"
    assert store.get("pending")["trials"] == [{"passed": True}]
    assert store.get("done")["status"] == "completed"
