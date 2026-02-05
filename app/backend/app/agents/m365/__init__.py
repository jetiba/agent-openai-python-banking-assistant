"""M365 Agent SDK integration for Teams and Copilot channels."""

from .banking_activity_handler import BankingActivityHandler
from .m365_events_handler import M365EventsHandler

__all__ = [
    "BankingActivityHandler",
    "M365EventsHandler",
]
