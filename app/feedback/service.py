import uuid
from datetime import timedelta
from difflib import SequenceMatcher

from app.domain import FeedbackAction, FeedbackIn, FeedbackRecord, utcnow
from app.errors import NoDraftToReview, TicketNotFound
from app.observability.metrics import Metrics
from app.storage.base import FeedbackStore, TicketStore


class FeedbackService:
    def __init__(self, tickets: TicketStore, store: FeedbackStore, metrics: Metrics):
        self._tickets, self._store, self._metrics = tickets, store, metrics

    def record(self, ticket_id: str, fb: FeedbackIn) -> FeedbackRecord:
        rec = self._tickets.get(ticket_id)
        if rec is None or rec.result is None:
            raise TicketNotFound(ticket_id)
        if rec.result.draft is None:
            raise NoDraftToReview(ticket_id)

        edit_ratio = None
        if fb.action is FeedbackAction.EDIT:
            edit_ratio = round(1 - SequenceMatcher(None, rec.result.draft, fb.edited_text or "").ratio(), 4)

        record = FeedbackRecord(
            ticket_id=ticket_id, feedback_id=f"{utcnow().isoformat()}#{uuid.uuid4().hex[:8]}",
            category=rec.result.category, confidence=rec.result.confidence, action=fb.action,
            edit_ratio=edit_ratio, edited_text=fb.edited_text if fb.action is FeedbackAction.EDIT else None,
            agent_id=fb.agent_id, reason=fb.reason,
        )
        self._store.save(record)
        self._tickets.mark_feedback_submitted(ticket_id)  # takes the ticket out of the pending queues

        # Always emit all three counters (0/1) so CloudWatch metric math never sees a missing series.
        values = {f"Feedback{a.name.title()}": float(fb.action is a) for a in FeedbackAction}
        units = {}
        if edit_ratio is not None:
            values["EditRatio"], units["EditRatio"] = edit_ratio, "None"
        self._metrics.emit(rec.result.category.value, values, units)
        return record

    def stats(self, days: int) -> dict:
        counts = self._store.counts_since(utcnow() - timedelta(days=days))

        def summarise(c: dict[FeedbackAction, int]) -> dict:
            total = sum(c.values())
            return {
                "accept": c[FeedbackAction.ACCEPT], "edit": c[FeedbackAction.EDIT], "reject": c[FeedbackAction.REJECT],
                "total": total,
                "acceptance_rate": round(c[FeedbackAction.ACCEPT] / total, 4) if total else None,
                "usable_rate": round((c[FeedbackAction.ACCEPT] + c[FeedbackAction.EDIT]) / total, 4) if total else None,
            }

        overall = {a: sum(c[a] for c in counts.values()) for a in FeedbackAction}
        return {"days": days, "overall": summarise(overall),
                "by_category": {cat.value: summarise(c) for cat, c in sorted(counts.items(), key=lambda kv: kv[0].value)}}
