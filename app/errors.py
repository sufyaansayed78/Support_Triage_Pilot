class TicketNotFound(Exception):
    pass


class NoDraftToReview(Exception):
    """Feedback was sent for a ticket that never had a draft (escalated / human triage)."""
