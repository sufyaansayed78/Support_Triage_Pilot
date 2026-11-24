"""Keyword classifier used by the local backend and as a model-free baseline in tests."""
from app.domain import Category, Classification, Ticket

_KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.PASSWORD_RESET: ("password", "reset", "forgot", "locked out", "can't log in", "cannot log in"),
    Category.SHIPPING_STATUS: ("shipping", "delivery", "tracking", "package", "order status", "where is my order"),
    Category.ACCOUNT_SETTINGS: ("change email", "update email", "profile", "notification", "settings", "username"),
    Category.PRODUCT_HOWTO: ("how do i", "how to", "getting started", "set up", "tutorial", "integrate"),
}


class HeuristicClassifier:
    def classify(self, ticket: Ticket) -> Classification:
        text = ticket.text.lower()
        scored = [(sum(k in text for k in kws), cat) for cat, kws in _KEYWORDS.items()]
        hits, category = max(scored, key=lambda s: s[0])
        if hits == 0:
            return Classification(category=Category.OTHER, confidence=0.3, rationale="no keyword match", source="heuristic")
        return Classification(
            category=category,
            confidence=min(0.95, 0.5 + 0.15 * hits),
            rationale=f"{hits} keyword hit(s)",
            source="heuristic",
        )
