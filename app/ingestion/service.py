"""Ingestion layer: validate, normalise and persist a ticket. Knows nothing about models or routing."""
import re
import uuid

from app.domain import Ticket, TicketIn
from app.storage.base import TicketStore

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLANKS = re.compile(r"\n{3,}")


def _clean(text: str) -> str:
    text = _CONTROL.sub("", text.replace("\r\n", "\n")).strip()
    return _BLANKS.sub("\n\n", text)


class IngestionService:
    def __init__(self, tickets: TicketStore):
        self._tickets = tickets

    def ingest(self, payload: TicketIn) -> Ticket:
        ticket = Ticket(
            ticket_id=uuid.uuid4().hex,
            subject=_clean(payload.subject),
            body=_clean(payload.body),
            customer_id=payload.customer_id,
            channel=payload.channel,
            external_id=payload.external_id,
        )
        self._tickets.save_ticket(ticket)
        return ticket
