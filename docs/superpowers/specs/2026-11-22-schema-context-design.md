# TypeDB schema in model context

The user approved adding the schema to the model context to isolate its contribution to answer quality. Add `typedb_schema` as a fifth approach, preserving the historical `typedb_context` parity control and its completed results. Replacing that old arm would make historical and new measurements ambiguous.

The new approach supplies the exact structural `typedb/schema.tql` in the system message. Facts, source access, grading and turn limits match RAG/TypeDB context. Executable `typedb/functions.tql` and computed decisions are excluded. Both direct and CrewAI use the shared prompt builder. Record the immutable schema text, SHA-256 and effective system prompt in the run manifest, and reject continuation if they change.

Expose the fifth approach in the existing German/English controls and explanation list, retaining the current design. No new dependency or redesigned screen. After the existing CrewAI pilot finishes, run a fresh direct RAG-versus-schema comparison over the same 30 evaluation cases and three models (180 attempts), subject to the unchanged shared EUR30 cap. This remains exploratory; the legal reference is provisional.
