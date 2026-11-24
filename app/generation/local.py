"""Local backend: bag-of-words retrieval over ./kb and a template 'generator'. No AWS needed."""
import math
import re
from collections import Counter
from pathlib import Path

from app.domain import Category, RetrievedChunk, Ticket
from app.kb.chunking import chunk_markdown

_STOP = frozenset("a an and are as at be by can do for from have how i if in is it me my of on or our so that the this to was we what when where with you your".split())
_TOKEN = re.compile(r"[a-z0-9']+")


def _vec(text: str) -> Counter:
    return Counter(t for t in _TOKEN.findall(text.lower()) if t not in _STOP)


def _cos(a: Counter, b: Counter) -> float:
    dot = sum(a[t] * b[t] for t in a.keys() & b.keys())
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class LocalRetriever:
    def __init__(self, kb_dir: str):
        self._chunks: list[tuple[RetrievedChunk, Counter]] = []
        for path in sorted(Path(kb_dir).glob("**/*.md")):
            for i, text in enumerate(chunk_markdown(path.read_text(encoding="utf-8"))):
                chunk = RetrievedChunk(source=path.name, chunk_id=f"{path.name}#{i}", text=text, score=0.0)
                self._chunks.append((chunk, _vec(text)))

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        q = _vec(query)
        scored = [(c.model_copy(update={"score": _cos(q, v)}), v) for c, v in self._chunks]
        scored.sort(key=lambda s: s[0].score, reverse=True)
        return [c for c, _ in scored[:k] if c.score > 0]


class TemplateGenerator:
    def generate(self, ticket: Ticket, category: Category, chunks: list[RetrievedChunk]) -> str | None:
        if not chunks:
            return None
        return f"Hi,\n\nThanks for getting in touch. Here's what should help:\n\n{chunks[0].text}\n\nLet us know if anything is unclear.\n\nBest,\nSupport"
