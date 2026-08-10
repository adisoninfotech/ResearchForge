"""Credit / accounting abstraction — no billing provider wired yet."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import AIOperation
from app.models.user import User

OPERATION_COST: dict[AIOperation, int] = {
    AIOperation.OUTLINE: 1,
    AIOperation.SECTION_QUESTIONS: 1,
    AIOperation.DRAFT_SECTION: 3,
    AIOperation.REWRITE_CLARITY: 1,
    AIOperation.SHORTEN: 1,
    AIOperation.EXPAND_WITH_EVIDENCE: 2,
    AIOperation.MISSING_INFORMATION: 1,
    AIOperation.GENERATE_ABSTRACT: 2,
    AIOperation.GENERATE_LIMITATIONS: 1,
    AIOperation.CONSISTENCY_REVIEW: 2,
}


@dataclass
class CreditReservation:
    user_id: str
    operation: AIOperation
    amount: int
    status: str = "reserved"


def cost_for(operation: AIOperation) -> int:
    return OPERATION_COST.get(operation, 1)


def reserve_credits(user: User, operation: AIOperation) -> CreditReservation:
    """Abstract reservation — always succeeds for now; marks eligibility only."""
    return CreditReservation(
        user_id=str(user.id),
        operation=operation,
        amount=cost_for(operation),
        status="reserved",
    )


def settle_credits(reservation: CreditReservation, *, success: bool) -> CreditReservation:
    reservation.status = "settled" if success else "released"
    return reservation
