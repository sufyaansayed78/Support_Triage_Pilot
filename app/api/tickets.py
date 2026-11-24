from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_container
from app.container import Container
from app.domain import Decision, TicketIn, TicketRecord, TriageResult

router = APIRouter(prefix="/v1/tickets", tags=["tickets"])


@router.post("", response_model=TriageResult, status_code=201)
def create_ticket(payload: TicketIn, c: Container = Depends(get_container)) -> TriageResult:
    """Ingest a ticket, triage it, and return the routing decision (plus a draft when one is warranted)."""
    ticket = c.ingestion.ingest(payload)
    return c.triage.triage(ticket)


@router.get("", response_model=list[TicketRecord])
@router.get("/", response_model=list[TicketRecord], include_in_schema=False)
def get_all_tickets(c: Container = Depends(get_container)) -> list[TicketRecord]:
    """Every ticket, newest first."""
    return c.tickets.get_all()



@router.get("/AI_drafted_tickets", response_model=list[TicketRecord])
def get_ai_drafted_tickets(c: Container = Depends(get_container)) -> list[TicketRecord]:
    """Tickets with a draft ready that no agent has reviewed yet."""
    return c.tickets.list_by_decisions([Decision.DRAFT_READY], pending_only=True)


@router.get("/Escalated_tickets", response_model=list[TicketRecord])
def get_escalated_tickets(c: Container = Depends(get_container)) -> list[TicketRecord]:
    """Tickets a human must handle (escalated, or low confidence / ungrounded) that have no feedback yet."""
    return c.tickets.list_by_decisions([Decision.ESCALATE, Decision.HUMAN_TRIAGE], pending_only=True)


@router.get("/{ticket_id}", response_model=TicketRecord)
def get_ticket(ticket_id: str, c: Container = Depends(get_container)) -> TicketRecord:
    rec = c.tickets.get(ticket_id)
    if rec is None:
        raise HTTPException(404, "ticket not found")
    return rec
