import io
import json

import pytest

from app.classification.base import parse_classification
from app.domain import Category
from app.generation.retriever_opensearch import l2_score_to_cosine
from app.kb.chunking import chunk_markdown
from app.observability.metrics import EmfMetrics


def test_parse_classification_happy_path():
    c = parse_classification('Sure! {"category": "shipping_status", "confidence": 0.91, "rationale": "tracking"}')
    assert c.category is Category.SHIPPING_STATUS and c.confidence == 0.91


@pytest.mark.parametrize("raw", ["not json", "{}", '{"category": "x", "confidence": "high"}'])
def test_parse_classification_failures_are_safe(raw):
    c = parse_classification(raw)
    assert c.category is Category.OTHER and c.confidence == 0.0


def test_parse_classification_clamps_and_maps_unknown_category():
    c = parse_classification('{"category": "weather", "confidence": 7}')
    assert c.category is Category.OTHER and c.confidence == 1.0


def test_l2_score_conversion():
    assert l2_score_to_cosine(1.0) == pytest.approx(1.0)       # identical vectors
    assert l2_score_to_cosine(1 / 3) == pytest.approx(0.0)     # orthogonal unit vectors (d^2 = 2)


def test_chunker_keeps_heading_and_respects_size():
    chunks = chunk_markdown("# A\n\n" + "\n\n".join(["x" * 300] * 4))
    assert all(c.startswith("A") for c in chunks) and len(chunks) >= 2


def test_emf_record_shape():
    buf = io.StringIO()
    EmfMetrics("SupportTriage", buf).emit("password_reset", {"FeedbackAccept": 1.0, "FeedbackEdit": 0.0})
    rec = json.loads(buf.getvalue())
    cw = rec["_aws"]["CloudWatchMetrics"][0]
    assert cw["Namespace"] == "SupportTriage" and cw["Dimensions"] == [["Category"], []]
    assert rec["Category"] == "password_reset" and rec["FeedbackAccept"] == 1.0
    assert {m["Name"] for m in cw["Metrics"]} == {"FeedbackAccept", "FeedbackEdit"}
