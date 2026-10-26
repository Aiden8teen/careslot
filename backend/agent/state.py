"""
LangGraph State Definition for CareSlot AI Scheduling & Queue Agent.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class CareSlotAgentState(TypedDict, total=False):
    """
    Stateful graph context across Receptionist and Doctor turns.
    Tracks extracted multilingual entities, conflict checks, optimal slot suggestions,
    waitlist replacement candidates, and the Human-in-the-Loop confirmation gate.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str
    staff_role: Literal["receptionist", "doctor"]
    staff_practitioner_id: Optional[int]
    detected_language: Literal["ar", "dz", "fr", "en"]
    intent: Literal[
        "book_appointment",
        "cancel_appointment",
        "fill_cancelled_slot",
        "suggest_optimal_slots",
        "query_schedule_or_queue",
        "role_restricted",
    ]
    extracted_entities: dict[str, Any]
    missing_fields: list[str]
    conflict_report: dict[str, Any]
    suggested_slots: list[dict[str, Any]]
    waitlist_candidates: list[dict[str, Any]]
    proposed_action: Optional[dict[str, Any]]
    requires_human_confirmation: bool
    confirmed_by_staff: Optional[bool]
    execution_result: Optional[dict[str, Any]]
    reply_text: str
    ai_fallback_used: bool
