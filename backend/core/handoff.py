"""
IRIS AI Office System — Cross-Team Handoff System
Enables DEV ↔ MARKETING collaboration via structured handoff events.

Handoff scenarios:
  - MARKETING needs a technical implementation → hands off to DEV
  - DEV needs copy/brand content → hands off to MARKETING
  - Cross-team retrospectives and aligned deliverables

The handoff creates a new task in the receiving team's queue and
emits a HANDOFF event visible on the canvas (agents walking between zones).
"""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from backend.core.event_bus import event_bus
from backend.core.event_types import AgentRole, EventType, OfficialEvent, TeamType

logger = logging.getLogger(__name__)


@dataclass
class HandoffRequest:
    """Structured cross-team handoff request."""
    from_team: str                   # 'dev' | 'marketing'
    to_team: str                     # 'dev' | 'marketing'
    from_agent_id: str               # Agent initiating the handoff
    context: str                     # Why the handoff is needed
    deliverable_needed: str          # What the receiving team must produce
    priority: int = 1                # 1 (normal) → 3 (urgent)
    original_task_id: Optional[str] = None  # Source task that triggered the handoff
    handoff_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "handoff_id": self.handoff_id,
            "from_team": self.from_team,
            "to_team": self.to_team,
            "from_agent_id": self.from_agent_id,
            "context": self.context,
            "deliverable_needed": self.deliverable_needed,
            "priority": self.priority,
            "original_task_id": self.original_task_id,
            "created_at": self.created_at,
        }


# In-memory handoff registry (persisted via API response; Supabase optional)
_pending_handoffs: list[HandoffRequest] = []


async def create_handoff(
    from_team: str,
    to_team: str,
    from_agent_id: str,
    context: str,
    deliverable_needed: str,
    priority: int = 1,
    original_task_id: Optional[str] = None,
) -> HandoffRequest:
    """
    Creates a cross-team handoff and emits HANDOFF event to the canvas.

    The Visual Engine will animate the requesting agent walking toward
    the other team's zone, simulating real collaboration.
    """
    handoff = HandoffRequest(
        from_team=from_team,
        to_team=to_team,
        from_agent_id=from_agent_id,
        context=context,
        deliverable_needed=deliverable_needed,
        priority=priority,
        original_task_id=original_task_id,
    )
    _pending_handoffs.append(handoff)

    # Emit HANDOFF event — canvas animates agent movement between zones
    team_enum = TeamType.DEV if from_team == "dev" else TeamType.MARKETING
    await event_bus.emit(
        OfficialEvent(
            event_type=EventType.HANDOFF,
            team=team_enum,
            agent_id=from_agent_id,
            agent_role=AgentRole.ORCHESTRATOR,
            task_id=original_task_id,
            payload={
                "handoff_id": handoff.handoff_id,
                "from_team": from_team,
                "to_team": to_team,
                "deliverable_needed": deliverable_needed[:200],
                "priority": priority,
            },
        )
    )

    logger.info(
        "[Handoff] %s → %s: '%s' (id=%s)",
        from_team, to_team, deliverable_needed[:80], handoff.handoff_id,
    )
    return handoff


def get_pending_handoffs(team: Optional[str] = None) -> list[HandoffRequest]:
    """Returns pending handoffs, optionally filtered by receiving team."""
    if team:
        return [h for h in _pending_handoffs if h.to_team == team]
    return list(_pending_handoffs)


def resolve_handoff(handoff_id: str) -> bool:
    """Marks a handoff as resolved (removes from pending queue)."""
    global _pending_handoffs
    before = len(_pending_handoffs)
    _pending_handoffs = [h for h in _pending_handoffs if h.handoff_id != handoff_id]
    return len(_pending_handoffs) < before
