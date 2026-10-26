"""
Pydantic v2 Schemas for CareSlot Full-Stack REST Endpoints & LangChain/LangGraph Structured Outputs.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LangGraph / Gemini 2.0 Flash Structured Extraction Schemas
# ---------------------------------------------------------------------------


class NaturalLanguageIntentSchema(BaseModel):
    """Structured extraction produced by Gemini 2.0 Flash from Receptionist or Doctor input."""

    detected_language: Literal["ar", "dz", "fr", "en"] = Field(
        default="fr",
        description="Language of the user request: 'ar' (Arabic), 'dz' (Algerian Darja), 'fr' (French), or 'en' (English).",
    )
    intent: Literal[
        "book_appointment",
        "cancel_appointment",
        "fill_cancelled_slot",
        "suggest_optimal_slots",
        "query_schedule_or_queue",
    ] = Field(
        description="Primary scheduling action requested by the clinic staff member."
    )
    patient_name: Optional[str] = Field(
        default=None,
        description="Extracted patient full name (in Arabic or Latin script) if mentioned.",
    )
    patient_phone: Optional[str] = Field(
        default=None,
        description="Extracted Algerian phone number (05/06/07...) if mentioned.",
    )
    practitioner_query: Optional[str] = Field(
        default=None,
        description="Doctor name or specialty mentioned (e.g., 'Dr. Amrani', 'Cardiologue', 'عمراني').",
    )
    target_date_iso: Optional[str] = Field(
        default=None,
        description="Resolved ISO date (YYYY-MM-DD) if a date or relative day ('today', 'demain', 'ghodwa', 'Tuesday') was specified.",
    )
    target_time_hhmm: Optional[str] = Field(
        default=None,
        description="Resolved 24h start time (HH:MM) if an exact hour was specified. Leave None if only 'morning'/'afternoon' or no time was given.",
    )
    preferred_window: Optional[Literal["MORNING", "AFTERNOON", "ANY"]] = Field(
        default="ANY",
        description="Preferred shift window if mentioned ('sba7'/'matin'/'morning' -> MORNING, '3chiya'/'après-midi'/'afternoon' -> AFTERNOON).",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional administrative note or reason for visit.",
    )


# ---------------------------------------------------------------------------
# Auth & Staff Schemas
# ---------------------------------------------------------------------------


class StaffLoginRequest(BaseModel):
    username: str = Field(..., min_length=2)


# ---------------------------------------------------------------------------
# Appointment & Queue Schemas
# ---------------------------------------------------------------------------


class AppointmentCreateRequest(BaseModel):
    patient_name: str = Field(..., min_length=2)
    patient_phone: str = Field(..., min_length=8)
    practitioner_id: int
    appointment_date: date
    start_time: time
    duration_min: Optional[int] = Field(default=None, ge=5, le=180)
    consultation_type: Optional[str] = "STANDARD"
    is_walk_in: bool = False
    assign_arrival_immediately: bool = False
    force_daily_cap_override: bool = False
    notes: Optional[str] = None


class AppointmentUpdateRequest(BaseModel):
    """Edit, move, or reschedule an existing appointment."""
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    practitioner_id: Optional[int] = None
    appointment_date: Optional[date] = None
    start_time: Optional[time] = None
    duration_min: Optional[int] = Field(default=None, ge=5, le=180)
    consultation_type: Optional[str] = None
    notes: Optional[str] = None
    force_daily_cap_override: bool = False


class ArrivalNumberUpdateRequest(BaseModel):
    new_arrival_number: int = Field(..., ge=1)


# ---------------------------------------------------------------------------
# Practitioner & Room Management Schemas
# ---------------------------------------------------------------------------


class PractitionerUpdateRequest(BaseModel):
    full_name_lat: Optional[str] = None
    full_name_ar: Optional[str] = None
    specialty: Optional[str] = None
    current_room_id: Optional[int] = None
    slot_duration_min: Optional[int] = Field(default=None, ge=10, le=120)
    max_daily_appointments: Optional[int] = Field(default=None, ge=1, le=100)
    working_hours_json: Optional[str] = None
    color_hex: Optional[str] = None


class RoomCreateRequest(BaseModel):
    name: str = Field(..., min_length=2)
    floor: str = Field(default="Rez-de-chaussée")


class RoomUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2)
    floor: Optional[str] = None


class RoomAssignRequest(BaseModel):
    room_id: int


# ---------------------------------------------------------------------------
# Waiting List Schemas
# ---------------------------------------------------------------------------


class WaitingListCreateRequest(BaseModel):
    patient_name: str = Field(..., min_length=2)
    patient_phone: str = Field(..., min_length=8)
    practitioner_id: int
    preferred_date: Optional[date] = None
    preferred_window: Literal["MORNING", "AFTERNOON", "ANY"] = "ANY"
    urgency: Literal["NORMAL", "HIGH", "URGENT"] = "NORMAL"
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# AI Agent Endpoints Schemas
# ---------------------------------------------------------------------------


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Typed or voice-transcribed staff request")
    staff_role: Literal["receptionist", "doctor"] = "receptionist"
    practitioner_id: Optional[int] = None
    thread_id: str = "clinic-frontdesk-default"


class AgentConfirmRequest(BaseModel):
    thread_id: str = "clinic-frontdesk-default"
    staff_role: Literal["receptionist", "doctor"] = "receptionist"
    confirm: bool = True
    selected_slot_time: Optional[str] = None
    selected_waitlist_id: Optional[int] = None


class AgentResponsePayload(BaseModel):
    reply: str
    detected_language: str
    intent: str
    missing_fields: list[str] = []
    conflict_report: dict[str, Any] = {}
    suggested_slots: list[dict[str, Any]] = []
    waitlist_candidates: list[dict[str, Any]] = []
    proposed_action: Optional[dict[str, Any]] = None
    requires_human_confirmation: bool = False
    ai_fallback_used: bool = False
