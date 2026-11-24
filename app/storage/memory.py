from collections import defaultdict
from datetime import datetime
from threading import Lock

from app.domain import (Category, Decision, FeedbackAction, FeedbackRecord, Ticket, TicketRecord, TicketStatus,
                        TriageResult)


class MemoryTicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._results: dict[str, TriageResult] = {}
        self._lock = Lock()

    def save_ticket(self, ticket: Ticket) -> None:
        with self._lock:
            self._tickets[ticket.ticket_id] = ticket

    def save_result(self, result: TriageResult) -> None:
        with self._lock:
            self._results[result.ticket_id] = result

    def get(self, ticket_id: str) -> TicketRecord | None:
        t = self._tickets.get(ticket_id)
        return TicketRecord(ticket=t, result=self._results.get(ticket_id)) if t else None

    def get_all(self) -> list[TicketRecord]:
        with self._lock:
            records = [TicketRecord(ticket=t, result=self._results.get(tid)) for tid, t in self._tickets.items()]
        return sorted(records, key=lambda r: r.ticket.created_at, reverse=True)

    def list_by_decisions(self, decisions: list[Decision], pending_only: bool = True) -> list[TicketRecord]:
        wanted = set(decisions)
        return [
            r for r in self.get_all()
            if r.result is not None and r.result.decision in wanted
            and (not pending_only or r.ticket.feedback_status is TicketStatus.PENDING)
        ]

    def mark_feedback_submitted(self, ticket_id: str) -> bool:
        with self._lock:
            t = self._tickets.get(ticket_id)
            if t is None or t.feedback_status is TicketStatus.SUBMITTED:
                return False
            self._tickets[ticket_id] = t.model_copy(update={"feedback_status": TicketStatus.SUBMITTED})
            return True


class MemoryFeedbackStore:
    def __init__(self) -> None:
        self._records: list[FeedbackRecord] = []
        self._lock = Lock()

    def save(self, record: FeedbackRecord) -> None:
        with self._lock:
            self._records.append(record)

    def counts_since(self, since: datetime) -> dict[Category, dict[FeedbackAction, int]]:
        out: dict[Category, dict[FeedbackAction, int]] = defaultdict(lambda: {a: 0 for a in FeedbackAction})
        for r in self._records:
            if r.created_at >= since:
                out[r.category][r.action] += 1
        return dict(out)
