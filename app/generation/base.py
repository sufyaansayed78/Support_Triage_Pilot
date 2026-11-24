from typing import Protocol

from app.domain import Category, RetrievedChunk, Ticket


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class Retriever(Protocol):
    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]: ...


class Generator(Protocol):
    def generate(self, ticket: Ticket, category: Category, chunks: list[RetrievedChunk]) -> str | None:
        """Return a draft grounded in `chunks`, or None if the context cannot answer the ticket."""
