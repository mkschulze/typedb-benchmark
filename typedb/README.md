# Real TypeDB backend

Validated with Python `typedb-driver==3.15.0` from `uv.lock` and the published `typedb/typedb:3.15.0` server image. No Python or SQLite fallback is used by the TypeDB adapter.

The dedicated test container was started with:

```sh
docker run -d --name dividend-benchmark-typedb \
  -p 127.0.0.1:1730:1729 -p 127.0.0.1:8002:8000 typedb/typedb:3.15.0
```

The root Compose configuration is the normal project startup path. Do not start both on the same host ports. Existing unrelated TypeDB containers were left untouched.

`TypeDBStore` reads `TYPEDB_ADDRESS` (default `localhost:1730`), `TYPEDB_USERNAME` (`admin`), `TYPEDB_PASSWORD` (`password`) and `TYPEDB_DATABASE` (`dividend_benchmark`). Each operation opens and closes its own connection; worker threads do not share transactions. Database creation and seeding are explicit. Idempotent reseeding replaces only changed benchmark cases and their linked documents, without dropping the database.

`schema.tql` models dividend cases, typed qualifications and ownership facts, evidence documents and exemption certificates. Tri-state facts are `yes`, `no` or `unknown`; an absent ownership date and `-1` participation sentinel represent unknown inputs. Calendar dates are stored as midnight datetimes because this TypeDB version supports duration addition to datetimes. Functions calculate twelve-month and 365-day boundaries in the server.

`functions.tql` contains reusable scope, certificate, qualification, anti-abuse, holding-period, treaty-cap and money functions. Decision codes are presentation-neutral database results; Python maps them to the common answer contract. Context reads typed graph attributes and linked evidence without calling decision functions. Evaluation queries server functions and returns source/evidence IDs read from the graph.

```sh
typeql-check < typedb/schema.tql
typeql-check < typedb/functions.tql
PYTHONPATH=backend .venv/bin/python -m tax_benchmark.cli seed
RUN_TYPEDB_INTEGRATION=1 .venv/bin/pytest -q tests/test_typedb.py
```

The integration test checks all 40 cases against the separately specified provisional gold and SQLite control. Unavailable or unseeded TypeDB fails explicitly; application browsing can remain available.
