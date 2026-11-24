from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.container import Container
from app.routing.policy import NEVER_AUTO_RESPOND

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/v1/policy")
def policy(c: Container = Depends(get_container)) -> dict:
    return {
        "acceptance_threshold": c.policy.threshold,
        "min_grounding_score": c.policy.min_grounding,
        "never_auto_respond": sorted(cat.value for cat in NEVER_AUTO_RESPOND),
    }
