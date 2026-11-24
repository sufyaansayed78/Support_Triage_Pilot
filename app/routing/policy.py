"""Routing policy: the ONLY place that decides what happens to a ticket.

Models propose (category, confidence, draft); this module disposes. Nothing here is
configurable at runtime except the acceptance threshold and grounding floor.
"""
import re
from dataclasses import dataclass, field

from app.domain import Category, Citation, Classification, Decision, RetrievedChunk

# Hard-coded on purpose: changing this list is a code review, not an env var.
NEVER_AUTO_RESPOND: frozenset[Category] = frozenset(
    {
        Category.LEGAL_THREAT,
        Category.SECURITY_INCIDENT,
        Category.PAYMENT_DISPUTE,
        Category.PRIVACY_REQUEST,
        Category.SAFETY_OR_HARASSMENT,
    }
)
assert len(NEVER_AUTO_RESPOND) == 5

# Deterministic safety net that runs BEFORE the model result is trusted. It exists so a
# misclassification (or a prompt-injected ticket) cannot talk its way out of escalation.
# It is intentionally over-sensitive: a false escalation costs a human a minute, a false
# auto-draft on a legal threat can cost far more.
_SAFETY_NET: dict[Category, re.Pattern[str]] = {
    Category.LEGAL_THREAT: re.compile(
        r"\b(lawyer|attorney|solicitor|legal action|lawsuit|sue (you|us|the company)|"
        r"small claims|cease and desist|take you to court)\b", re.I),
    Category.SECURITY_INCIDENT: re.compile(
        r"\b(hacked|compromised|data breach|unauthori[sz]ed (access|login)|phishing|"
        r"stolen (card|account|credentials)|vulnerability|someone (logged|got) into)\b", re.I),
    Category.PAYMENT_DISPUTE: re.compile(
        r"\b(chargeback|dispute (the |this )?(charge|payment)|charged twice|double[- ]charged|"
        r"unauthori[sz]ed (charge|transaction)|fraudulent charge|refund)\b", re.I),
    Category.PRIVACY_REQUEST: re.compile(
        r"\b(gdpr|ccpa|data subject|right to be forgotten|delete (all )?my (personal )?data|"
        r"erase my data|subject access request|dsar)\b", re.I),
    Category.SAFETY_OR_HARASSMENT: re.compile(
        r"\b(harass\w*|threaten\w*|self[- ]harm|suicid\w*|kill (myself|you)|stalk\w*|"
        r"abus(e|ed|ive)|discriminat\w+)\b", re.I),
}


def scan_safety_net(text: str) -> list[Category]:
    return [cat for cat, pat in _SAFETY_NET.items() if pat.search(text)]


@dataclass
class RoutingOutcome:
    decision: Decision
    reasons: list[str] = field(default_factory=list)


class RoutingPolicy:
    def __init__(self, acceptance_threshold: float, min_grounding_score: float):
        if not 0.0 <= acceptance_threshold <= 1.0:
            raise ValueError("acceptance_threshold must be within [0, 1]")
        self.threshold = acceptance_threshold
        self.min_grounding = min_grounding_score

    def apply_safety_net(self, text: str, cls: Classification) -> Classification:
        """Override the model if a never-auto pattern matches and it didn't already say so."""
        if cls.category in NEVER_AUTO_RESPOND:
            return cls
        hits = scan_safety_net(text)
        if not hits:
            return cls
        return Classification(
            category=hits[0],
            confidence=1.0,
            rationale=f"safety-net pattern matched ({', '.join(h.value for h in hits)}); "
            f"model said {cls.category.value}@{cls.confidence:.2f}",
            source="safety_net",
        )

    def pre_draft(self, cls: Classification) -> RoutingOutcome | None:
        """Decide before spending tokens on retrieval/generation. None = proceed to draft."""
        if cls.category in NEVER_AUTO_RESPOND:
            # Confidence is deliberately ignored here: 0.99 or 0.10, it escalates.
            return RoutingOutcome(Decision.ESCALATE, [f"{cls.category.value} is a never-auto-respond category"])
        if cls.category is Category.OTHER:
            return RoutingOutcome(Decision.HUMAN_TRIAGE, ["classifier could not place the ticket"])
        if cls.confidence < self.threshold:
            return RoutingOutcome(
                Decision.HUMAN_TRIAGE,
                [f"confidence {cls.confidence:.2f} below acceptance threshold {self.threshold:.2f}"],
            )
        return None

    def grounded(self, chunks: list[RetrievedChunk]) -> bool:
        return bool(chunks) and max(c.score for c in chunks) >= self.min_grounding


def to_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    return [
        Citation(source=c.source, chunk_id=c.chunk_id, score=round(c.score, 4), snippet=c.text[:200])
        for c in chunks
    ]
