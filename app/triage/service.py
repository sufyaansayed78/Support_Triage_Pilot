"""Orchestrates classify -> route -> retrieve -> generate. Holds no business rules itself."""
from app.classification.base import Classifier
from app.domain import Decision, Ticket, TriageResult
from app.generation.base import Generator, Retriever
from app.observability.metrics import Metrics
from app.routing.policy import RoutingOutcome, RoutingPolicy, to_citations
from app.storage.base import TicketStore


class TriageService:
    def __init__(self, classifier: Classifier, retriever: Retriever, generator: Generator,
                 policy: RoutingPolicy, tickets: TicketStore, metrics: Metrics, top_k: int = 4):
        self._classifier, self._retriever, self._generator = classifier, retriever, generator
        self._policy, self._tickets, self._metrics, self._top_k = policy, tickets, metrics, top_k

    def triage(self, ticket: Ticket) -> TriageResult:
        cls = self._policy.apply_safety_net(ticket.text, self._classifier.classify(ticket))
        reasons = [f"classified as {cls.category.value} ({cls.source}, confidence {cls.confidence:.2f})"]
        draft, citations = None, []

        outcome = self._policy.pre_draft(cls)
        if outcome is None:
            chunks = self._retriever.retrieve(ticket.text, self._top_k)
            if not self._policy.grounded(chunks):
                outcome = RoutingOutcome(Decision.HUMAN_TRIAGE, ["no knowledge-base passage is relevant enough to ground a draft"])
            else:
                draft = self._generator.generate(ticket, cls.category, chunks)
                citations = to_citations(chunks)
                if draft is None:
                    outcome = RoutingOutcome(Decision.HUMAN_TRIAGE, ["knowledge base does not answer the ticket"])
                    citations = []
                else:
                    outcome = RoutingOutcome(Decision.DRAFT_READY, ["confident and grounded in the knowledge base"])

        result = TriageResult(
            ticket_id=ticket.ticket_id, category=cls.category, confidence=cls.confidence,
            decision=outcome.decision, reasons=reasons + outcome.reasons,
            draft=draft, citations=citations, threshold=self._policy.threshold,
        )
        
        self._tickets.save_result(result)
        self._metrics.emit(
            cls.category.value,
            {
                "TicketsTriaged": 1,
                # emit every decision (0 or 1) so rollups never have gaps
                **{f"Decision{d.name.title().replace('_', '')}": float(outcome.decision is d) for d in Decision},
                "Confidence": cls.confidence,
            },
            {"Confidence": "None"},
        )
        return result
