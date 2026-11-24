"""Shared domain types. Every layer depends on this module; none depends on another layer."""
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Category(str, Enum):
    # --- may receive a drafted reply ---
    PASSWORD_RESET = "password_reset"
    SHIPPING_STATUS = "shipping_status"
    PRODUCT_HOWTO = "product_how_to"
    ACCOUNT_SETTINGS = "account_settings"
    GENERAL_INQUIRY = "general_inquiry"
    # --- NEVER auto-respond: always escalated to a human (see routing/policy.py) ---
    LEGAL_THREAT = "legal_threat"
    SECURITY_INCIDENT = "security_incident"
    PAYMENT_DISPUTE = "payment_dispute"
    PRIVACY_REQUEST = "privacy_request"
    SAFETY_OR_HARASSMENT = "safety_or_harassment"
    # --- classifier could not place it ---
    OTHER = "other"


class Decision(str, Enum):
    ESCALATE = "escalate"  # hard rule: human only, no draft is generated
    DRAFT_READY = "draft_ready"  # confident + grounded: draft offered to the agent
    HUMAN_TRIAGE = "human_triage"  # low confidence / ungrounded: normal human queue, no draft


class FeedbackAction(str, Enum):
    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"


class TicketIn(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20_000)
    customer_id: str | None = Field(default=None, max_length=128)
    channel: Literal["email", "chat", "web", "api"] = "api"
    external_id: str | None = Field(default=None, max_length=128)



class TicketStatus(str, Enum):
    PENDING = "Pending"  # no agent feedback yet
    SUBMITTED = "Submitted"  # an agent accepted / edited / rejected the draft

class Ticket(BaseModel):
    ticket_id: str = Field(default_factory=lambda: uuid4().hex)
    subject: str
    body: str
    customer_id: str | None = None
    channel: str = "api"
    external_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    feedback_status: TicketStatus = TicketStatus.PENDING

    @property
    def text(self) -> str:
        return f"{self.subject}\n\n{self.body}"


class Classification(BaseModel):
    category: Category = Field(...,description="The Category of the Ticket")
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    source: Literal["llm", "heuristic", "safety_net"] = "llm"


class RetrievedChunk(BaseModel):
    source: str
    chunk_id: str
    text: str
    score: float  # cosine similarity, higher is better


class Citation(BaseModel):
    source: str
    chunk_id: str
    score: float
    snippet: str


class TriageResult(BaseModel):
    ticket_id: str
    category: Category
    confidence: float
    decision: Decision
    reasons: list[str]
    draft: str | None = None
    citations: list[Citation] = []
    threshold: float
    created_at: datetime = Field(default_factory=utcnow)


class TicketRecord(BaseModel):
    ticket: Ticket
    result: TriageResult | None = None


class FeedbackIn(BaseModel):
    action: FeedbackAction
    edited_text: str | None = Field(default=None, max_length=20_000)
    agent_id: str | None = Field(default=None, max_length=128)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _edit_needs_text(self) -> "FeedbackIn":
        if self.action is FeedbackAction.EDIT and not (self.edited_text or "").strip():
            raise ValueError("edited_text is required when action is 'edit'")
        return self


class FeedbackRecord(BaseModel):
    ticket_id: str
    feedback_id: str
    category: Category
    confidence: float
    action: FeedbackAction
    edit_ratio: float | None = None  # 0 = identical to draft, 1 = fully rewritten
    edited_text: str | None = None
    agent_id: str | None = None
    reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
