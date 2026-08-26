"""Career discovery — the "uncertain goal" branch of goal intelligence.

The gap engine needs a target; a learner who says "I don't know what I want"
has none. This endpoint turns their signals into ranked career directions,
each carrying the target-skill vector the path generator plans from.

The ranking is agentic — the LLM reasons over the learner's signals and the
real catalogue — behind a validating, grounding seam, with a deterministic
engine as fallback (see `services/discovery_service.py`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, SessionDep, get_llm_provider_dep
from app.llm.base import LLMProvider
from app.schemas.discovery import CareerDiscoveryRequest, CareerDiscoveryResponse
from app.services.discovery_service import CareerDiscoveryService

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/careers", response_model=CareerDiscoveryResponse)
async def discover_careers(
    payload: CareerDiscoveryRequest,
    session: SessionDep,
    current_user: CurrentUser,
    provider: LLMProvider = Depends(get_llm_provider_dep),
) -> CareerDiscoveryResponse:
    careers = await CareerDiscoveryService(session, provider).discover(
        current_user.id,
        interests=payload.interests,
        free_text=payload.free_text,
        top_k=payload.top_k,
    )
    return CareerDiscoveryResponse(count=len(careers), careers=careers)
