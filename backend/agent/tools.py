"""
LangChain Tools & Deterministic Scheduling / Conflict / Waitlist Engines for CareSlot.
Used by the LangGraph AI nodes AND as the 100%-uptime fallback when AI is offline.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from models import (
    Appointment,
    AppointmentStatus,
    Patient,
    Practitioner,
    PreferredWindow,
    Room,
    SessionLocal,
    WaitingListEntry,
    WaitlistUrgency,
    normalize_algerian_phone,
    normalize_multilingual_name,
)


# ---------------------------------------------------------------------------
# Deterministic Helper Functions
# ---------------------------------------------------------------------------


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    return time(hour=(m // 60) % 24, minute=m % 60)


def resolve_practitioner(db: Session, query: Optional[str]) -> list[Practitioner]:
    """Finds matching practitioners by Arabic name, Latin name, or specialty."""
    if not query:
        return []
    norm_q = normalize_multilingual_name(query.replace("dr.", "").replace("dr", "").replace("د.", "").replace("دكتور", ""))
    all_docs = db.query(Practitioner).filter(Practitioner.is_active == True).all()
    matches = []
    for doc in all_docs:
        haystack = normalize_multilingual_name(
            f"{doc.full_name_lat} {doc.full_name_ar or ''} {doc.specialty}"
        )
        if norm_q and norm_q in haystack:
            matches.append(doc)
    return matches


def search_patients(db: Session, query: str) -> list[Patient]:
    """Searches patients by Arabic/Latin normalized name or Algerian phone digits."""
    if not query:
        return []
    norm_q = normalize_multilingual_name(query)
    phone_q = normalize_algerian_phone(query) or query.strip()
    patients = db.query(Patient).all()
    results = []
    for pt in patients:
        if (norm_q and norm_q in pt.normalized_name) or (phone_q and phone_q in pt.phone):
            results.append(pt)
    return results


def check_appointment_conflicts(
    db: Session,
    practitioner_id: int,
    target_date: date,
    start_t: time,
    exclude_appointment_id: Optional[int] = None,
    custom_duration_min: Optional[int] = None,
) -> dict[str, Any]:
    """
    Comprehensive 4-dimensional conflict detector:
    1. Practitioner working hours & Algerian Friday weekend check
    2. Practitioner time-slot overlap check
    3. Shared consultation room collision check
    4. Practitioner daily appointment capacity check
    """
    doc = db.query(Practitioner).filter(Practitioner.id == practitioner_id).first()
    if not doc:
        return {"has_hard_conflict": True, "reasons": ["Practitioner not found."]}

    duration = custom_duration_min or doc.slot_duration_min or 20
    start_min = _time_to_minutes(start_t)
    end_min = start_min + duration
    end_t = _minutes_to_time(end_min)

    reasons: list[str] = []
    warnings: list[str] = []
    has_hard_conflict = False
    has_overlap_conflict = False
    has_room_collision = False
    is_off_day = False

    # 1. Working hours check
    day_abbr = target_date.strftime("%a")  # Sat, Sun, Mon, Tue, Wed, Thu, Fri
    try:
        hours_map = json.loads(doc.working_hours_json or "{}")
    except Exception:
        hours_map = {}

    day_hours = hours_map.get(day_abbr, ["08:30", "16:30"])
    if not day_hours or len(day_hours) < 2:
        is_off_day = True
        has_hard_conflict = True
        reasons.append(f"{doc.full_name_lat} does not consult on {day_abbr} ({target_date.isoformat()}).")
    else:
        shift_start = _time_to_minutes(time.fromisoformat(day_hours[0]))
        shift_end = _time_to_minutes(time.fromisoformat(day_hours[1]))
        if start_min < shift_start or end_min > shift_end:
            warnings.append(
                f"Requested time {start_t.strftime('%H:%M')}–{end_t.strftime('%H:%M')} is outside "
                f"{doc.full_name_lat}'s regular shift ({day_hours[0]}–{day_hours[1]})."
            )

    # 2. Practitioner overlap check
    active_statuses = [
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.ARRIVED.value,
        AppointmentStatus.IN_CONSULTATION.value,
    ]
    day_appts_query = db.query(Appointment).filter(
        Appointment.appointment_date == target_date,
        Appointment.status.in_(active_statuses),
    )
    if exclude_appointment_id:
        day_appts_query = day_appts_query.filter(Appointment.id != exclude_appointment_id)

    all_day_appts = day_appts_query.all()
    doc_appts = [a for a in all_day_appts if a.practitioner_id == practitioner_id]

    for existing in doc_appts:
        ex_start = _time_to_minutes(existing.start_time)
        ex_end = _time_to_minutes(existing.end_time)
        if max(start_min, ex_start) < min(end_min, ex_end):
            has_hard_conflict = True
            has_overlap_conflict = True
            reasons.append(
                f"Time overlap for {doc.full_name_lat}: existing appointment with "
                f"{existing.patient.full_name} from {existing.start_time.strftime('%H:%M')} to {existing.end_time.strftime('%H:%M')}."
            )

    # 3. Shared Room Collision Check
    if doc.current_room_id:
        room_appts = [
            a
            for a in all_day_appts
            if a.room_id == doc.current_room_id and a.practitioner_id != practitioner_id
        ]
        for rm_appt in room_appts:
            rm_start = _time_to_minutes(rm_appt.start_time)
            rm_end = _time_to_minutes(rm_appt.end_time)
            if max(start_min, rm_start) < min(end_min, rm_end):
                has_hard_conflict = True
                has_room_collision = True
                room_name = doc.current_room.name if doc.current_room else f"Room #{doc.current_room_id}"
                reasons.append(
                    f"Room collision in {room_name}: occupied by {rm_appt.practitioner.full_name_lat} "
                    f"({rm_appt.start_time.strftime('%H:%M')}–{rm_appt.end_time.strftime('%H:%M')})."
                )

    # 4. Daily Capacity Check
    current_count = len(doc_appts)
    max_cap = doc.max_daily_appointments or 20
    daily_cap_exceeded = current_count >= max_cap
    if daily_cap_exceeded:
        warnings.append(
            f"Daily limit reached for {doc.full_name_lat} ({current_count}/{max_cap} appointments booked)."
        )
    elif current_count >= int(max_cap * 0.85):
        warnings.append(
            f"High daily load for {doc.full_name_lat}: {current_count}/{max_cap} slots filled."
        )

    return {
        "has_hard_conflict": has_hard_conflict,
        "has_overlap_conflict": has_overlap_conflict,
        "has_room_collision": has_room_collision,
        "is_off_day": is_off_day,
        "daily_cap_exceeded": daily_cap_exceeded,
        "current_daily_count": current_count,
        "max_daily_appointments": max_cap,
        "slot_start": start_t.strftime("%H:%M"),
        "slot_end": end_t.strftime("%H:%M"),
        "reasons": reasons,
        "warnings": warnings,
    }


def suggest_optimal_slots_for_doctor(
    db: Session,
    practitioner_id: int,
    target_date: date,
    preferred_window: str = "ANY",
    limit: int = 4,
    custom_duration_min: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    AI Slot Suggestion & Load Optimization Engine.
    Scans the practitioner's shift in `slot_duration_min` increments (or custom_duration_min),
    eliminates conflicted slots, and scores remaining slots to cluster appointments cleanly.
    """
    doc = db.query(Practitioner).filter(Practitioner.id == practitioner_id).first()
    if not doc:
        return []

    duration = custom_duration_min or doc.slot_duration_min or 20
    day_abbr = target_date.strftime("%a")
    try:
        hours_map = json.loads(doc.working_hours_json or "{}")
    except Exception:
        hours_map = {}

    day_hours = hours_map.get(day_abbr, ["08:30", "16:30"])
    if not day_hours or len(day_hours) < 2:
        return []

    shift_start = _time_to_minutes(time.fromisoformat(day_hours[0]))
    shift_end = _time_to_minutes(time.fromisoformat(day_hours[1]))

    active_statuses = [
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.ARRIVED.value,
        AppointmentStatus.IN_CONSULTATION.value,
    ]
    existing_appts = (
        db.query(Appointment)
        .filter(
            Appointment.practitioner_id == practitioner_id,
            Appointment.appointment_date == target_date,
            Appointment.status.in_(active_statuses),
        )
        .all()
    )
    existing_end_mins = {_time_to_minutes(a.end_time) for a in existing_appts}
    existing_start_mins = {_time_to_minutes(a.start_time) for a in existing_appts}

    candidates: list[dict[str, Any]] = []
    cursor = shift_start
    while cursor + duration <= shift_end:
        # Skip lunch transition 12:30 - 13:00 unless needed
        slot_t = _minutes_to_time(cursor)
        is_morning = cursor < 12 * 60 + 30
        if preferred_window == "MORNING" and not is_morning:
            cursor += duration
            continue
        if preferred_window == "AFTERNOON" and is_morning:
            cursor += duration
            continue

        conflict = check_appointment_conflicts(
            db, practitioner_id, target_date, slot_t, custom_duration_min=duration
        )
        if not conflict["has_hard_conflict"]:
            # Score slot: prefer contiguous slots (adjacent to an existing booking) to avoid dead gaps
            score = 70
            rationale = "Open shift slot"
            if cursor in existing_end_mins or (cursor + duration) in existing_start_mins:
                score += 20
                rationale = "Contiguous slot (prevents fragmented schedule gap)"
            if is_morning and preferred_window in ("MORNING", "ANY"):
                score += 5
            candidates.append(
                {
                    "start_time": slot_t.strftime("%H:%M"),
                    "end_time": _minutes_to_time(cursor + duration).strftime("%H:%M"),
                    "date": target_date.isoformat(),
                    "practitioner_id": doc.id,
                    "practitioner_name": doc.full_name_lat,
                    "room_name": doc.current_room.name if doc.current_room else "Unassigned",
                    "score": score,
                    "rationale": rationale,
                }
            )
        cursor += duration

    candidates.sort(key=lambda x: (-x["score"], x["start_time"]))
    return candidates[:limit]


def rank_waiting_list_for_cancelled_slot(
    db: Session,
    practitioner_id: int,
    slot_date: date,
    slot_time: time,
) -> list[dict[str, Any]]:
    """
    AI Waiting-List Replacement Matcher.
    Scores active waiting list entries for the given practitioner based on:
    - Clinical/Administrative Urgency (URGENT=50, HIGH=30, NORMAL=10)
    - Preferred Time Window match (MORNING vs AFTERNOON = +30)
    - Waiting time seniority (+2 per day waiting)
    """
    entries = (
        db.query(WaitingListEntry)
        .filter(
            WaitingListEntry.practitioner_id == practitioner_id,
            WaitingListEntry.is_active == True,
        )
        .all()
    )

    is_morning = _time_to_minutes(slot_time) < 12 * 60 + 30
    slot_window = PreferredWindow.MORNING.value if is_morning else PreferredWindow.AFTERNOON.value

    urgency_weights = {
        WaitlistUrgency.URGENT.value: 50,
        WaitlistUrgency.HIGH.value: 30,
        WaitlistUrgency.NORMAL.value: 10,
    }

    ranked: list[dict[str, Any]] = []
    now = datetime.utcnow()
    for entry in entries:
        score = urgency_weights.get(entry.urgency, 10)
        reasons = [f"Urgency: {entry.urgency}"]

        if entry.preferred_window in (slot_window, PreferredWindow.ANY.value):
            score += 30
            reasons.append(f"Matches {slot_window.lower()} preference")

        days_waiting = max(0, (now - (entry.created_at or now)).days)
        score += min(days_waiting * 3, 20)

        ranked.append(
            {
                "waitlist_id": entry.id,
                "patient_id": entry.patient_id,
                "patient_name": entry.patient.full_name,
                "patient_phone": entry.patient.phone,
                "practitioner_id": entry.practitioner_id,
                "practitioner_name": entry.practitioner.full_name_lat,
                "urgency": entry.urgency,
                "preferred_window": entry.preferred_window,
                "reason": entry.reason or "Waiting for earlier slot",
                "match_score": score,
                "match_explanation": " • ".join(reasons),
                "target_date": slot_date.isoformat(),
                "target_time": slot_time.strftime("%H:%M"),
            }
        )

    ranked.sort(key=lambda r: -r["match_score"])
    return ranked[:3]


# ---------------------------------------------------------------------------
# LangChain @tool wrappers (exposed to LangGraph Agent)
# ---------------------------------------------------------------------------


@tool
def tool_find_optimal_slots(
    practitioner_query: str,
    target_date_iso: str,
    preferred_window: str = "ANY",
) -> list[dict[str, Any]]:
    """Find the best available appointment slots for a doctor on a given YYYY-MM-DD date."""
    with SessionLocal() as db:
        docs = resolve_practitioner(db, practitioner_query)
        if not docs:
            return [{"error": f"No practitioner found matching '{practitioner_query}'."}]
        target_d = date.fromisoformat(target_date_iso)
        return suggest_optimal_slots_for_doctor(db, docs[0].id, target_d, preferred_window)


@tool
def tool_match_waitlist(
    practitioner_id: int,
    slot_date_iso: str,
    slot_time_hhmm: str,
) -> list[dict[str, Any]]:
    """Rank waiting list candidates to fill a cancelled slot for a practitioner."""
    with SessionLocal() as db:
        return rank_waiting_list_for_cancelled_slot(
            db,
            practitioner_id=practitioner_id,
            slot_date=date.fromisoformat(slot_date_iso),
            slot_time=time.fromisoformat(slot_time_hhmm),
        )
