import pytest

from app.domain import Category, Classification, Decision
from app.routing.policy import NEVER_AUTO_RESPOND, RoutingPolicy, scan_safety_net

policy = RoutingPolicy(acceptance_threshold=0.75, min_grounding_score=0.35)


def cls(cat: Category, conf: float) -> Classification:
    return Classification(category=cat, confidence=conf)


def test_exactly_five_never_auto_categories():
    assert len(NEVER_AUTO_RESPOND) == 5


@pytest.mark.parametrize("category", sorted(NEVER_AUTO_RESPOND, key=lambda c: c.value))
@pytest.mark.parametrize("confidence", [0.0, 0.5, 0.99, 1.0])
def test_never_auto_always_escalates_regardless_of_confidence(category, confidence):
    assert policy.pre_draft(cls(category, confidence)).decision is Decision.ESCALATE


def test_below_threshold_goes_to_human_triage():
    out = policy.pre_draft(cls(Category.PASSWORD_RESET, 0.74))
    assert out.decision is Decision.HUMAN_TRIAGE


def test_at_threshold_proceeds_to_draft():
    assert policy.pre_draft(cls(Category.PASSWORD_RESET, 0.75)) is None


def test_other_category_never_drafts():
    assert policy.pre_draft(cls(Category.OTHER, 0.99)).decision is Decision.HUMAN_TRIAGE


def test_safety_net_overrides_confident_misclassification():
    c = policy.apply_safety_net("my lawyer will contact you about this", cls(Category.GENERAL_INQUIRY, 0.97))
    assert c.category is Category.LEGAL_THREAT and c.source == "safety_net"
    assert policy.pre_draft(c).decision is Decision.ESCALATE


def test_safety_net_leaves_benign_text_alone():
    c = cls(Category.PASSWORD_RESET, 0.9)
    assert policy.apply_safety_net("how do I reset my password?", c) is c


@pytest.mark.parametrize("text,expected", [
    ("I was charged twice for my order", Category.PAYMENT_DISPUTE),
    ("please delete all my personal data under GDPR", Category.PRIVACY_REQUEST),
    ("I think my account was hacked", Category.SECURITY_INCIDENT),
    ("this is harassment", Category.SAFETY_OR_HARASSMENT),
])
def test_safety_net_patterns(text, expected):
    assert expected in scan_safety_net(text)


def test_invalid_threshold_rejected():
    with pytest.raises(ValueError):
        RoutingPolicy(1.5, 0.3)
