import json
import re
from typing import Protocol

from app.domain import Category, Classification, Ticket


class Classifier(Protocol):
    def classify(self, ticket: Ticket) -> Classification: ...


_JSON = re.compile(r"\{.*\}", re.S)


def parse_classification(raw: str) -> Classification:
    """Parse model output defensively. Anything malformed becomes OTHER@0.0 (-> human)."""
    try:
        data = json.loads(_JSON.search(raw).group(0))  # type: ignore[union-attr]
        try:
            category = Category(str(data["category"]).strip().lower())
        except ValueError:
            category = Category.OTHER
        confidence = min(1.0, max(0.0, float(data["confidence"])))
        return Classification(
            category=category,
            confidence=confidence,
            rationale=str(data.get("rationale", ""))[:500],
            source="llm",
        )
    except Exception:  # noqa: BLE001 - any parse failure is a safe fallback
        return Classification(category=Category.OTHER, confidence=0.0, rationale="unparseable model output", source="llm")
