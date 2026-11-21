import math
import os
import re
from collections import Counter

import httpx

from .providers import ModelDefinition


def tokens(text: str):
    return re.findall(r"[\w§]+", text.casefold())


class SourceRetriever:
    def __init__(self, sources: list[dict]):
        self.sources = sources
        self.lexical = [
            Counter(tokens(f"{source['title']} {source.get('locator', '')} {source['text']}"))
            for source in sources
        ]
        self.embedding_url = os.environ.get("EMBEDDING_BASE_URL", "").rstrip("/")
        self.embedding_model = os.environ.get("EMBEDDING_MODEL", "")
        if bool(self.embedding_url) != bool(self.embedding_model):
            raise ValueError("Configure both EMBEDDING_BASE_URL and EMBEDDING_MODEL, or leave both unset")
        if self.embedding_url:
            self.embedding_url = ModelDefinition(
                id="embedding",
                name="Embedding endpoint",
                model=self.embedding_model,
                base_url=self.embedding_url,
            ).base_url
        self.vectors = None
        self.usage_records = []

    @property
    def mode(self):
        return "hybrid" if self.embedding_url and self.embedding_model else "lexical"

    async def embed(self, texts: list[str], purpose: str = "query") -> list[list[float]]:
        key = os.environ.get("EMBEDDING_API_KEY")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.embedding_url}/embeddings",
                headers=headers,
                json={"model": self.embedding_model, "input": texts},
            )
            response.raise_for_status()
            body = response.json()
            self.usage_records.append(
                {
                    "purpose": purpose,
                    "model": self.embedding_model,
                    "usage": body.get("usage") if isinstance(body.get("usage"), dict) else None,
                }
            )
            data = sorted(body["data"], key=lambda item: item["index"])
            if len(data) != len(texts):
                raise ValueError("Embedding endpoint returned an incorrect vector count")
            vectors = [item["embedding"] for item in data]
            if not vectors or any(
                not vector or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vector)
                for vector in vectors
            ):
                raise ValueError("Embedding endpoint returned invalid vectors")
            if len({len(vector) for vector in vectors}) != 1:
                raise ValueError("Embedding dimensions do not match")
            return vectors

    async def prepare(self):
        if self.mode == "hybrid" and self.vectors is None:
            self.vectors = await self.embed(
                [f"{source['title']}\n{source['text']}" for source in self.sources], purpose="source_index"
            )

    async def search(self, query: str, limit: int = 5):
        query_tokens = tokens(query)
        scores = []
        count = len(self.sources)
        average_length = sum(sum(row.values()) for row in self.lexical) / max(count, 1)
        for document in self.lexical:
            score = 0.0
            for token in set(query_tokens):
                frequency = document[token]
                document_count = sum(token in row for row in self.lexical)
                inverse_frequency = math.log(1 + (count - document_count + 0.5) / (document_count + 0.5))
                score += (
                    inverse_frequency
                    * frequency
                    * 2.5
                    / (frequency + 1.5 * (0.25 + 0.75 * sum(document.values()) / max(average_length, 1)))
                )
            scores.append(score)
        lexical_order = sorted(range(count), key=lambda index: scores[index], reverse=True)
        if self.mode == "hybrid":
            await self.prepare()
            query_vector = (await self.embed([query]))[0]
            if any(len(vector) != len(query_vector) for vector in self.vectors):
                raise ValueError("Query embedding dimensions do not match the source index")

            def similarity(vector):
                denominator = math.sqrt(sum(v * v for v in vector) * sum(v * v for v in query_vector))
                return sum(a * b for a, b in zip(vector, query_vector)) / denominator if denominator else 0

            dense_order = sorted(
                range(count), key=lambda index: similarity(self.vectors[index]), reverse=True
            )
            fused = {
                index: 1 / (60 + lexical_order.index(index) + 1) + 1 / (60 + dense_order.index(index) + 1)
                for index in range(count)
            }
            lexical_order = sorted(fused, key=fused.get, reverse=True)
        return [{**self.sources[index], "retrieval_mode": self.mode} for index in lexical_order[:limit]]
