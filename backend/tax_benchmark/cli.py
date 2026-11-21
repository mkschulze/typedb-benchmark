import argparse
import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def verify_dataset():
    from .domain import load_cases, load_gold, load_sources, reference_answer
    from .runner import grade_answer

    cases, sources, gold = load_cases(), load_sources(), load_gold()
    assert len({case["id"] for case in cases}) == len(cases), "Duplicate case IDs"
    assert {case["id"] for case in cases} == set(gold), "Cases and separate gold IDs differ"
    source_ids = {source["id"] for source in sources}
    for source in sources:
        raw = (ROOT / source["raw_path"]).resolve()
        assert raw.is_relative_to(ROOT / "data"), "Source snapshot path escapes data directory"
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == source["sha256"], (
            f"Source checksum mismatch: {source['id']}"
        )
    split_templates = {}
    for case in cases:
        assert case["review_status"] == "provisional"
        assert set(case["source_ids"]) <= source_ids
        assert "gold" not in case and "expected" not in case
        template = case.get("template_group", case["id"])
        assert template not in split_templates or split_templates[template] == case["split"], (
            "Scenario template leaks across splits"
        )
        split_templates[template] = case["split"]
        assert grade_answer(reference_answer(case), gold[case["id"]])["passed"], (
            f"Reference and manually authored rubric disagree: {case['id']}"
        )
    return {
        "cases": len(cases),
        "sources": len(sources),
        "legal_review": "provisional",
        "message": "Checksums, split isolation, and reference/rubric consistency verified; this is not independent legal validation",
    }


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="German dividend withholding context benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "verify", help="Verify source hashes, case splits and provisional rubric consistency"
    )
    subparsers.add_parser("seed", help="Load the dedicated benchmark database in TypeDB")
    server = subparsers.add_parser("serve", help="Start FastAPI and serve the built React frontend")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if args.command == "verify":
        print(json.dumps(verify_dataset(), indent=2))
    elif args.command == "seed":
        from .domain import load_cases
        from .typedb_store import TypeDBStore

        database = TypeDBStore()
        database.seed(load_cases())
        print(json.dumps(database.health(), indent=2))
    else:
        import uvicorn

        uvicorn.run("tax_benchmark.api:create_app", factory=True, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
