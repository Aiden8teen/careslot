"""
CareSlot FastAPI Server + Real-Time WebSocket Hub + LangGraph AI Agent Endpoints.
Production Multi-Practitioner Clinic Management Platform:
- Shared Multi-Doctor Calendar (Day & Week views)
- Full Appointment Lifecycle: Create, Edit/Move, Cancel, Walk-In
- 4-Dimensional Conflict & Room Collision Detection
- Live Sequential Arrival Numbering ('Tour') & Manual Reordering
- 1-Click Consultation Finished status with Live Queue Filtering
- Per-Doctor Waiting Lists & AI Cancellation Replacement Alerts
- LangGraph Natural-Language Voice/Text Booking & Slot Suggestions
- Configurable Practitioners & Consultation Rooms
- Role-Based Views for Receptionist and Doctors
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from agent.graph import careslot_agent_graph
from agent.tools import (
    check_appointment_conflicts,
    rank_waiting_list_for_cancelled_slot,
    search_patients,
    suggest_optimal_slots_for_doctor,
)
from models import (
    Appointment,
    AppointmentStatus,
    AuditLog,
    Patient,
    Practitioner,
    Room,
    SessionLocal,
    StaffRole,
    StaffUser,
    WaitingListEntry,
    init_and_seed_db,
    normalize_algerian_phone,
    normalize_multilingual_name,
)
from schemas import (
    AgentChatRequest,
    AgentConfirmRequest,
    AgentResponsePayload,
    AppointmentCreateRequest,
    AppointmentUpdateRequest,
    ArrivalNumberUpdateRequest,
    PractitionerUpdateRequest,
    RoomAssignRequest,
    RoomCreateRequest,
    RoomUpdateRequest,
    StaffLoginRequest,
    WaitingListCreateRequest,
)


# ---------------------------------------------------------------------------
# WebSocket Connection Manager (Sub-second Sync across Receptionist & Doctors)
# ---------------------------------------------------------------------------


class ClinicConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        message = json.dumps(
            {
                "event": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": payload,
            },
            default=str,
        )
        stale: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for s in stale:
            self.disconnect(s)


ws_manager = ClinicConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_and_seed_db()
    yield


app = FastAPI(
    title="CareSlot AI Scheduling & Queue API",
    description="Centralized Multi-Doctor Scheduling, Arrival Queue ('Tour'), & LangGraph AI Assistant for Algerian Medical Clinics",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.api_route("/healthz", methods=["GET", "HEAD"])
@app.api_route("/", methods=["GET", "HEAD"])
def api_root():
    """CareSlot API Health & Status Endpoint."""
    return {
        "service": "CareSlot Clinic Management API",
        "version": "2.0.0",
        "status": "online",
        "docs": "/docs",
        "websocket": "/ws/clinic",
    }


@app.post("/api/demo/reset")
async def reset_demo_database():
    """Resets the clinic database back to the clean demonstration state with today's appointments."""
    init_and_seed_db(force=True)
    await ws_manager.broadcast("CLINIC_RESET", {"message": "Demo data restored successfully"})
    return {"status": "ok", "message": "Demo data successfully reset to clean showcase state"}


# ---------------------------------------------------------------------------
# Staff Authentication & Role Profiles (Receptionist vs. Doctors)
# ---------------------------------------------------------------------------


@app.get("/api/auth/users")
def list_staff_accounts(db: Session = Depends(get_db)):
    """Returns Receptionist and Doctor staff accounts for quick role switching / login."""
    users = db.query(StaffUser).filter(StaffUser.is_active == True).all()
    doctors = {d.id: d for d in db.query(Practitioner).all()}
    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "practitioner_id": u.practitioner_id,
            "specialty": doctors[u.practitioner_id].specialty
            if u.practitioner_id and u.practitioner_id in doctors
            else "Administration & Accueil",
        }
        for u in users
    ]


@app.post("/api/auth/login")
def staff_login(req: StaffLoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(StaffUser)
        .filter(StaffUser.username == req.username.strip().lower())
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Staff account not found.")
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "practitioner_id": user.practitioner_id,
    }


# ---------------------------------------------------------------------------
# Master Calendar & Clinic Overview (Day & Week Views)
# ---------------------------------------------------------------------------


@app.get("/api/clinic/overview")
def get_clinic_overview(
    target_date: Optional[date] = Query(default=None),
    view_mode: str = Query(default="day", description="'day' or 'week'"),
    practitioner_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Returns all practitioners (with daily counts and working hours), rooms,
    appointments (for Day or 7-day Week view), active queues, and waiting list.
    """
    day = target_date or date.today()
    doctors = db.query(Practitioner).filter(Practitioner.is_active == True).order_by(Practitioner.id).all()
    rooms = db.query(Room).filter(Room.is_active == True).order_by(Room.id).all()

    if view_mode == "week":
        # Algerian clinic week view: 7 days starting from target_date (or Saturday)
        end_day = day + timedelta(days=6)
        appt_q = db.query(Appointment).filter(
            Appointment.appointment_date >= day,
            Appointment.appointment_date <= end_day,
        )
    else:
        end_day = day
        appt_q = db.query(Appointment).filter(Appointment.appointment_date == day)

    if practitioner_id:
        appt_q = appt_q.filter(Appointment.practitioner_id == practitioner_id)

    appts = appt_q.order_by(
        Appointment.appointment_date,
        Appointment.start_time,
        Appointment.arrival_number,
    ).all()

    # Calculate active daily appointment count per doctor for the selected day
    active_statuses = {
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.ARRIVED.value,
        AppointmentStatus.IN_CONSULTATION.value,
        AppointmentStatus.FINISHED.value,
    }
    day_counts: dict[int, int] = {d.id: 0 for d in doctors}
    for a in db.query(Appointment).filter(Appointment.appointment_date == day).all():
        if a.status in active_statuses and a.practitioner_id in day_counts:
            day_counts[a.practitioner_id] += 1

    waitlist_q = db.query(WaitingListEntry).filter(WaitingListEntry.is_active == True)
    if practitioner_id:
        waitlist_q = waitlist_q.filter(WaitingListEntry.practitioner_id == practitioner_id)
    waitlist = waitlist_q.order_by(WaitingListEntry.created_at.desc()).all()

    week_days = [(day + timedelta(days=i)).isoformat() for i in range(7)]

    now = datetime.now()
    now_min = now.hour * 60 + now.minute
    today_date = date.today()
    doctor_delays = {}
    for d in doctors:
        delay_min = 0
        # Live consultation overrun calculation for active consultations today
        if day == today_date:
            doc_day_appts = [
                a for a in appts 
                if a.practitioner_id == d.id and a.appointment_date == day
            ]
            in_consult = [a for a in doc_day_appts if a.status == AppointmentStatus.IN_CONSULTATION.value]
            if in_consult:
                curr = in_consult[0]
                curr_start = curr.start_time.hour * 60 + curr.start_time.minute
                curr_end = curr.end_time.hour * 60 + curr.end_time.minute
                # If currently within the scheduled consultation window: doctor is on schedule
                if curr_start <= now_min <= curr_end:
                    delay_min = 0
                # If consultation is actively exceeding its scheduled slot end time recently (within 30m)
                elif curr_end < now_min <= curr_end + 30:
                    delay_min = now_min - curr_end
                else:
                    delay_min = 0
        doctor_delays[d.id] = delay_min

    return {
        "date": day.isoformat(),
        "end_date": end_day.isoformat(),
        "view_mode": view_mode,
        "week_days": week_days,
        "rooms": [
            {"id": r.id, "name": r.name, "floor": r.floor, "is_active": r.is_active}
            for r in rooms
        ],
        "practitioners": [
            {
                "id": d.id,
                "full_name_lat": d.full_name_lat,
                "full_name_ar": d.full_name_ar or "",
                "specialty": d.specialty,
                "room_id": d.current_room_id,
                "room_name": d.current_room.name if d.current_room else "Unassigned",
                "slot_duration_min": d.slot_duration_min,
                "max_daily_appointments": d.max_daily_appointments,
                "today_booked_count": day_counts.get(d.id, 0),
                "running_delay_min": doctor_delays.get(d.id, 0),
                "delay_status": (
                    "ON_TIME" if doctor_delays.get(d.id, 0) <= 5
                    else "MODERATE" if doctor_delays.get(d.id, 0) <= 20
                    else "HEAVY"
                ),
                "working_hours": json.loads(d.working_hours_json or "{}"),
                "color_hex": d.color_hex,
            }
            for d in doctors
        ],
        "appointments": [
            {
                "id": a.id,
                "patient_id": a.patient_id,
                "patient_name": a.patient.full_name,
                "patient_phone": a.patient.phone,
                "practitioner_id": a.practitioner_id,
                "practitioner_name": a.practitioner.full_name_lat,
                "practitioner_name_ar": a.practitioner.full_name_ar or "",
                "specialty": a.practitioner.specialty,
                "room_id": a.room_id,
                "room_name": a.room.name if a.room else "Unassigned",
                "appointment_date": a.appointment_date.isoformat(),
                "start_time": a.start_time.strftime("%H:%M"),
                "end_time": a.end_time.strftime("%H:%M"),
                "duration_min": getattr(a, "duration_min", 20) or (
                    (a.end_time.hour * 60 + a.end_time.minute) - (a.start_time.hour * 60 + a.start_time.minute)
                ),
                "consultation_type": getattr(a, "consultation_type", "STANDARD") or "STANDARD",
                "status": a.status,
                "is_walk_in": a.is_walk_in,
                "arrival_number": a.arrival_number,
                "notes": a.notes or "",
            }
            for a in appts
        ],
        "waiting_list": [
            {
                "id": w.id,
                "patient_id": w.patient_id,
                "patient_name": w.patient.full_name,
                "patient_phone": w.patient.phone,
                "practitioner_id": w.practitioner_id,
                "practitioner_name": w.practitioner.full_name_lat,
                "preferred_date": w.preferred_date.isoformat() if w.preferred_date else day.isoformat(),
                "preferred_window": w.preferred_window,
                "urgency": w.urgency,
                "reason": w.reason or "",
            }
            for w in waitlist
        ],
    }


@app.get("/api/slots/suggest")
def get_ai_slot_suggestions(
    practitioner_id: int = Query(...),
    target_date: Optional[date] = Query(default=None),
    preferred_window: str = Query(default="ANY"),
    limit: int = Query(default=6),
    duration_min: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Returns AI-scored optimal available time slots for a practitioner, date, and custom duration."""
    day = target_date or date.today()
    slots = suggest_optimal_slots_for_doctor(
        db,
        practitioner_id=practitioner_id,
        target_date=day,
        preferred_window=preferred_window,
        limit=limit,
        custom_duration_min=duration_min,
    )
    return {
        "practitioner_id": practitioner_id,
        "date": day.isoformat(),
        "duration_min": duration_min,
        "slots": slots,
    }


@app.get("/api/patients")
def api_list_patients(
    q: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Returns patient directory for Patients Tab matching Figma designs."""
    if q and q.strip():
        pts = search_patients(db, q.strip())
    else:
        pts = db.query(Patient).order_by(Patient.id.desc()).all()

    today_val = date.today()
    output = []
    for p in pts:
        appts = (
            db.query(Appointment)
            .filter(Appointment.patient_id == p.id)
            .order_by(Appointment.appointment_date.desc(), Appointment.start_time.desc())
            .all()
        )
        active_appts = [a for a in appts if a.status != "CANCELLED"]
        next_appt = (
            db.query(Appointment)
            .filter(
                Appointment.patient_id == p.id,
                Appointment.status != "CANCELLED",
                Appointment.appointment_date >= today_val,
            )
            .order_by(Appointment.appointment_date.asc(), Appointment.start_time.asc())
            .first()
        )
        last_appt = active_appts[0] if active_appts else None

        output.append({
            "id": p.id,
            "full_name": p.full_name,
            "phone": p.phone,
            "appointments_count": len(appts),
            "last_appointment": {
                "id": last_appt.id,
                "date": last_appt.appointment_date.isoformat(),
                "time": last_appt.start_time.strftime("%H:%M"),
                "practitioner_name": last_appt.practitioner.full_name_lat if last_appt.practitioner else "",
                "status": last_appt.status,
            } if last_appt else None,
            "next_appointment": {
                "id": next_appt.id,
                "date": next_appt.appointment_date.isoformat(),
                "time": next_appt.start_time.strftime("%H:%M"),
                "practitioner_name": next_appt.practitioner.full_name_lat if next_appt.practitioner else "",
                "status": next_appt.status,
            } if next_appt else None,
        })
    return output


@app.get("/api/patients/search")
def api_search_patients(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """Multilingual patient search (Arabic RTL, French/Latin, or Algerian 05/06/07 phone)."""
    matches = search_patients(db, q)
    return [
        {"id": p.id, "full_name": p.full_name, "phone": p.phone}
        for p in matches
    ]


# ---------------------------------------------------------------------------
# Appointment CRUD: Create, Edit/Move, Assign Arrival #, Reorder, Finish, Cancel
# ---------------------------------------------------------------------------


@app.post("/api/appointments")
async def create_appointment(
    req: AppointmentCreateRequest,
    staff_role: str = Query(default="receptionist"),
    db: Session = Depends(get_db),
):
    """Creates a new appointment (or walk-in) with conflict & daily cap checks."""
    doc = db.query(Practitioner).filter(Practitioner.id == req.practitioner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Practitioner not found.")

    duration = req.duration_min or doc.slot_duration_min or 20
    conflict = check_appointment_conflicts(
        db, req.practitioner_id, req.appointment_date, req.start_time, custom_duration_min=duration
    )
    if conflict["has_hard_conflict"]:
        # Allow receptionist or emergency walk-in to override off-day/shift warning if there are no physical doctor or room overlaps
        can_override = (
            (req.force_daily_cap_override or req.is_walk_in)
            and not conflict.get("has_overlap_conflict")
            and not conflict.get("has_room_collision")
        )
        if not can_override:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Scheduling conflict detected",
                    "reasons": conflict["reasons"],
                    "suggested_slots": suggest_optimal_slots_for_doctor(
                        db, req.practitioner_id, req.appointment_date, custom_duration_min=duration
                    ),
                },
            )
    if conflict["daily_cap_exceeded"] and not req.force_daily_cap_override:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Practitioner daily limit reached. Enable override to book anyway.",
                "reasons": conflict["warnings"],
                "daily_cap_exceeded": True,
            },
        )

    norm_name = normalize_multilingual_name(req.patient_name)
    norm_phone = normalize_algerian_phone(req.patient_phone) or req.patient_phone.strip()
    patient = (
        db.query(Patient)
        .filter((Patient.normalized_name == norm_name) | (Patient.phone == norm_phone))
        .first()
    )
    if not patient:
        patient = Patient(
            full_name=req.patient_name.strip(),
            normalized_name=norm_name,
            phone=norm_phone,
        )
        db.add(patient)
        db.flush()
    else:
        # Keep phone/name updated if edited
        patient.full_name = req.patient_name.strip()
        patient.normalized_name = norm_name
        patient.phone = norm_phone

    start_min = req.start_time.hour * 60 + req.start_time.minute
    end_min = start_min + duration
    end_t = time(hour=(end_min // 60) % 24, minute=end_min % 60)

    arrival_num = None
    status = AppointmentStatus.SCHEDULED.value
    if req.assign_arrival_immediately or req.is_walk_in:
        max_num = (
            db.query(func.max(Appointment.arrival_number))
            .filter(
                Appointment.practitioner_id == doc.id,
                Appointment.appointment_date == req.appointment_date,
            )
            .scalar()
            or 0
        )
        arrival_num = max_num + 1
        status = AppointmentStatus.ARRIVED.value

    appt = Appointment(
        patient_id=patient.id,
        practitioner_id=doc.id,
        room_id=doc.current_room_id,
        appointment_date=req.appointment_date,
        start_time=req.start_time,
        end_time=end_t,
        duration_min=duration,
        consultation_type=req.consultation_type or "STANDARD",
        status=status,
        is_walk_in=req.is_walk_in,
        arrival_number=arrival_num,
        checked_in_at=datetime.utcnow() if arrival_num else None,
        notes=req.notes,
    )
    db.add(appt)
    db.add(
        AuditLog(
            staff_role=staff_role,
            action="CREATE_APPOINTMENT",
            details=f"Patient {patient.full_name} with {doc.full_name_lat} on {req.appointment_date} at {req.start_time}",
        )
    )
    db.commit()
    db.refresh(appt)

    payload = {
        "appointment_id": appt.id,
        "patient_name": patient.full_name,
        "practitioner_id": doc.id,
        "practitioner_name": doc.full_name_lat,
        "appointment_date": appt.appointment_date.isoformat(),
        "start_time": appt.start_time.strftime("%H:%M"),
        "end_time": appt.end_time.strftime("%H:%M"),
        "duration_min": appt.duration_min,
        "consultation_type": appt.consultation_type,
        "status": appt.status,
        "arrival_number": appt.arrival_number,
        "warnings": conflict["warnings"],
    }
    await ws_manager.broadcast("APPOINTMENT_CREATED", payload)
    return payload


@app.put("/api/appointments/{appointment_id}")
async def update_or_move_appointment(
    appointment_id: int,
    req: AppointmentUpdateRequest,
    staff_role: str = Query(default="receptionist"),
    db: Session = Depends(get_db),
):
    """Edits patient details or moves/reschedules an appointment to a new time, date, or doctor."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    new_doc_id = req.practitioner_id or appt.practitioner_id
    new_date = req.appointment_date or appt.appointment_date
    new_start = req.start_time or appt.start_time
    doc = db.query(Practitioner).filter(Practitioner.id == new_doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Target practitioner not found.")

    duration = req.duration_min or appt.duration_min or doc.slot_duration_min or 20
    conflict = check_appointment_conflicts(
        db,
        practitioner_id=new_doc_id,
        target_date=new_date,
        start_t=new_start,
        exclude_appointment_id=appt.id,
        custom_duration_min=duration,
    )
    if conflict["has_hard_conflict"]:
        can_override = (
            req.force_daily_cap_override
            and not conflict.get("has_overlap_conflict")
            and not conflict.get("has_room_collision")
        )
        if not can_override:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Conflict when moving/editing appointment",
                    "reasons": conflict["reasons"],
                    "suggested_slots": suggest_optimal_slots_for_doctor(
                        db, new_doc_id, new_date, custom_duration_min=duration
                    ),
                },
            )

    if req.patient_name:
        appt.patient.full_name = req.patient_name.strip()
        appt.patient.normalized_name = normalize_multilingual_name(req.patient_name)
    if req.patient_phone:
        appt.patient.phone = normalize_algerian_phone(req.patient_phone) or req.patient_phone.strip()

    start_min = new_start.hour * 60 + new_start.minute
    end_min = start_min + duration
    end_t = time(hour=(end_min // 60) % 24, minute=end_min % 60)

    # If doctor or date changed, reset arrival number so it doesn't collide
    if new_doc_id != appt.practitioner_id or new_date != appt.appointment_date:
        appt.arrival_number = None
        if appt.status == AppointmentStatus.ARRIVED.value:
            appt.status = AppointmentStatus.SCHEDULED.value

    appt.practitioner_id = new_doc_id
    appt.room_id = doc.current_room_id
    appt.appointment_date = new_date
    appt.start_time = new_start
    appt.end_time = end_t
    appt.duration_min = duration
    if req.consultation_type:
        appt.consultation_type = req.consultation_type
    if req.notes is not None:
        appt.notes = req.notes

    db.add(
        AuditLog(
            staff_role=staff_role,
            action="UPDATE_APPOINTMENT",
            details=f"Moved/edited appointment #{appt.id} to {doc.full_name_lat} on {new_date} at {new_start}",
        )
    )
    db.commit()

    payload = {
        "appointment_id": appt.id,
        "patient_name": appt.patient.full_name,
        "practitioner_id": doc.id,
        "practitioner_name": doc.full_name_lat,
        "appointment_date": appt.appointment_date.isoformat(),
        "start_time": appt.start_time.strftime("%H:%M"),
        "end_time": appt.end_time.strftime("%H:%M"),
        "duration_min": appt.duration_min,
        "consultation_type": appt.consultation_type,
        "status": appt.status,
    }
    await ws_manager.broadcast("APPOINTMENT_UPDATED", payload)
    return payload


@app.post("/api/appointments/{appointment_id}/assign-arrival")
async def assign_arrival_number(
    appointment_id: int,
    staff_role: str = Query(default="receptionist"),
    db: Session = Depends(get_db),
):
    """Assigns the next sequential arrival number ('Tour') when a patient arrives."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    if appt.arrival_number is None:
        max_num = (
            db.query(func.max(Appointment.arrival_number))
            .filter(
                Appointment.practitioner_id == appt.practitioner_id,
                Appointment.appointment_date == appt.appointment_date,
            )
            .scalar()
            or 0
        )
        appt.arrival_number = max_num + 1
        appt.status = AppointmentStatus.ARRIVED.value
        appt.checked_in_at = datetime.utcnow()
        db.commit()

    payload = {
        "appointment_id": appt.id,
        "practitioner_id": appt.practitioner_id,
        "patient_name": appt.patient.full_name,
        "arrival_number": appt.arrival_number,
        "status": appt.status,
    }
    await ws_manager.broadcast("QUEUE_UPDATED", payload)
    return payload


@app.put("/api/appointments/{appointment_id}/reorder-arrival")
async def manual_reorder_arrival_number(
    appointment_id: int,
    req: ArrivalNumberUpdateRequest,
    staff_role: str = Query(default="receptionist"),
    db: Session = Depends(get_db),
):
    """Allows staff to manually change a patient's arrival number and shifts conflicting numbers."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    target_num = req.new_arrival_number
    existing = (
        db.query(Appointment)
        .filter(
            Appointment.practitioner_id == appt.practitioner_id,
            Appointment.appointment_date == appt.appointment_date,
            Appointment.arrival_number == target_num,
            Appointment.id != appt.id,
        )
        .first()
    )
    old_num = appt.arrival_number
    appt.arrival_number = None
    db.flush()
    if existing:
        existing.arrival_number = old_num or (target_num + 100)
        db.flush()
    appt.arrival_number = target_num
    if existing and old_num is None:
        existing.arrival_number = target_num + 1
    if appt.status == AppointmentStatus.SCHEDULED.value:
        appt.status = AppointmentStatus.ARRIVED.value
    db.commit()

    payload = {
        "appointment_id": appt.id,
        "practitioner_id": appt.practitioner_id,
        "arrival_number": appt.arrival_number,
        "patient_name": appt.patient.full_name,
    }
    await ws_manager.broadcast("QUEUE_UPDATED", payload)
    return payload


@app.post("/api/appointments/{appointment_id}/toggle-finished")
async def toggle_consultation_finished(
    appointment_id: int,
    staff_role: str = Query(default="doctor"),
    db: Session = Depends(get_db),
):
    """Marks consultation as FINISHED (or reverts to ARRIVED) and updates active queue live."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    if appt.status == AppointmentStatus.FINISHED.value:
        appt.status = (
            AppointmentStatus.ARRIVED.value
            if appt.arrival_number
            else AppointmentStatus.SCHEDULED.value
        )
        appt.finished_at = None
    else:
        appt.status = AppointmentStatus.FINISHED.value
        appt.finished_at = datetime.utcnow()

    db.commit()
    payload = {
        "appointment_id": appt.id,
        "practitioner_id": appt.practitioner_id,
        "patient_name": appt.patient.full_name,
        "status": appt.status,
        "arrival_number": appt.arrival_number,
    }
    await ws_manager.broadcast("CONSULTATION_FINISHED", payload)
    return payload


@app.post("/api/appointments/{appointment_id}/cancel")
async def cancel_appointment_and_suggest_waitlist(
    appointment_id: int,
    staff_role: str = Query(default="receptionist"),
    db: Session = Depends(get_db),
):
    """
    Cancels an appointment, broadcasts an instant cancellation alert,
    and returns ranked AI waiting-list suggestions for human confirmation.
    """
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    appt.status = AppointmentStatus.CANCELLED.value
    appt.arrival_number = None
    db.commit()

    suggestions = rank_waiting_list_for_cancelled_slot(
        db,
        practitioner_id=appt.practitioner_id,
        slot_date=appt.appointment_date,
        slot_time=appt.start_time,
    )

    alert_payload = {
        "cancelled_appointment_id": appt.id,
        "patient_name": appt.patient.full_name,
        "practitioner_id": appt.practitioner_id,
        "practitioner_name": appt.practitioner.full_name_lat,
        "freed_date": appt.appointment_date.isoformat(),
        "freed_time": appt.start_time.strftime("%H:%M"),
        "waitlist_suggestions": suggestions,
    }
    await ws_manager.broadcast("APPOINTMENT_CANCELLED", alert_payload)
    return alert_payload


# ---------------------------------------------------------------------------
# Practitioners & Rooms Management CRUD
# ---------------------------------------------------------------------------


@app.put("/api/practitioners/{practitioner_id}")
async def update_practitioner_settings(
    practitioner_id: int,
    req: PractitionerUpdateRequest,
    db: Session = Depends(get_db),
):
    """Edits practitioner Latin/Arabic name, specialty, room, slot duration, or daily cap."""
    doc = db.query(Practitioner).filter(Practitioner.id == practitioner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Practitioner not found.")

    if req.full_name_lat is not None:
        doc.full_name_lat = req.full_name_lat.strip()
    if req.full_name_ar is not None:
        doc.full_name_ar = req.full_name_ar.strip()
    if req.specialty is not None:
        doc.specialty = req.specialty.strip()
    if req.slot_duration_min is not None:
        doc.slot_duration_min = req.slot_duration_min
    if req.max_daily_appointments is not None:
        doc.max_daily_appointments = req.max_daily_appointments
    if req.working_hours_json is not None:
        doc.working_hours_json = req.working_hours_json
    if req.color_hex is not None:
        doc.color_hex = req.color_hex

    if req.current_room_id is not None and req.current_room_id != doc.current_room_id:
        room = db.query(Room).filter(Room.id == req.current_room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Assigned room not found.")
        doc.current_room_id = room.id
        # Update active appointments from today onward to show the current room
        active_appts = (
            db.query(Appointment)
            .filter(
                Appointment.practitioner_id == doc.id,
                Appointment.appointment_date >= date.today(),
                Appointment.status != AppointmentStatus.CANCELLED.value,
            )
            .all()
        )
        for a in active_appts:
            a.room_id = room.id

    db.commit()
    db.refresh(doc)
    payload = {
        "practitioner_id": doc.id,
        "full_name_lat": doc.full_name_lat,
        "full_name_ar": doc.full_name_ar,
        "specialty": doc.specialty,
        "room_id": doc.current_room_id,
        "room_name": doc.current_room.name if doc.current_room else "Unassigned",
        "slot_duration_min": doc.slot_duration_min,
        "max_daily_appointments": doc.max_daily_appointments,
    }
    await ws_manager.broadcast("PRACTITIONER_UPDATED", payload)
    return payload


@app.put("/api/practitioners/{practitioner_id}/room")
async def change_practitioner_room(
    practitioner_id: int,
    req: RoomAssignRequest,
    db: Session = Depends(get_db),
):
    """Quick room change endpoint for a practitioner."""
    return await update_practitioner_settings(
        practitioner_id,
        PractitionerUpdateRequest(current_room_id=req.room_id),
        db=db,
    )


@app.post("/api/rooms")
async def create_room(req: RoomCreateRequest, db: Session = Depends(get_db)):
    """Adds a new consultation room."""
    existing = db.query(Room).filter(Room.name == req.name.strip()).first()
    if existing:
        existing.is_active = True
        existing.floor = req.floor
        db.commit()
        return {"id": existing.id, "name": existing.name, "floor": existing.floor}

    room = Room(name=req.name.strip(), floor=req.floor.strip(), is_active=True)
    db.add(room)
    db.commit()
    db.refresh(room)
    payload = {"id": room.id, "name": room.name, "floor": room.floor}
    await ws_manager.broadcast("ROOMS_UPDATED", payload)
    return payload


@app.put("/api/rooms/{room_id}")
async def rename_room(room_id: int, req: RoomUpdateRequest, db: Session = Depends(get_db)):
    """Renames an existing consultation room."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")
    
    new_name = req.name.strip()
    conflict = db.query(Room).filter(Room.name == new_name, Room.id != room_id).first()
    if conflict:
        if not conflict.is_active:
            # Overwrite archived room
            conflict.name = f"{conflict.name}_archived_{conflict.id}"
            db.commit()
        else:
            raise HTTPException(status_code=409, detail=f"A room named '{new_name}' already exists.")

    room.name = new_name
    if req.floor is not None:
        room.floor = req.floor.strip()
    db.commit()
    payload = {"id": room.id, "name": room.name, "floor": room.floor}
    await ws_manager.broadcast("ROOMS_UPDATED", payload)
    return payload


@app.delete("/api/rooms/{room_id}")
async def delete_room(room_id: int, db: Session = Depends(get_db)):
    """Removes (archives) a consultation room and unassigns doctors currently in it."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")
    room.is_active = False
    for doc in db.query(Practitioner).filter(Practitioner.current_room_id == room.id).all():
        doc.current_room_id = None
    db.commit()
    await ws_manager.broadcast("ROOMS_UPDATED", {"deleted_room_id": room_id})
    return {"status": "removed", "room_id": room_id}


# ---------------------------------------------------------------------------
# Waiting List CRUD
# ---------------------------------------------------------------------------


@app.post("/api/waitlist")
async def add_to_waiting_list(req: WaitingListCreateRequest, db: Session = Depends(get_db)):
    """Adds a patient to a specific practitioner's waiting list."""
    doc = db.query(Practitioner).filter(Practitioner.id == req.practitioner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Practitioner not found.")

    norm_name = normalize_multilingual_name(req.patient_name)
    norm_phone = normalize_algerian_phone(req.patient_phone) or req.patient_phone.strip()
    patient = (
        db.query(Patient)
        .filter((Patient.normalized_name == norm_name) | (Patient.phone == norm_phone))
        .first()
    )
    if not patient:
        patient = Patient(
            full_name=req.patient_name.strip(),
            normalized_name=norm_name,
            phone=norm_phone,
        )
        db.add(patient)
        db.flush()

    entry = WaitingListEntry(
        patient_id=patient.id,
        practitioner_id=doc.id,
        preferred_date=req.preferred_date or date.today(),
        preferred_window=req.preferred_window,
        urgency=req.urgency,
        reason=req.reason,
        is_active=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    payload = {
        "id": entry.id,
        "patient_name": patient.full_name,
        "patient_phone": patient.phone,
        "practitioner_id": doc.id,
        "practitioner_name": doc.full_name_lat,
        "urgency": entry.urgency,
        "preferred_window": entry.preferred_window,
    }
    await ws_manager.broadcast("WAITLIST_UPDATED", payload)
    return payload


@app.delete("/api/waitlist/{waitlist_id}")
async def remove_from_waiting_list(waitlist_id: int, db: Session = Depends(get_db)):
    entry = db.query(WaitingListEntry).filter(WaitingListEntry.id == waitlist_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Waiting list entry not found.")
    entry.is_active = False
    db.commit()
    await ws_manager.broadcast("WAITLIST_UPDATED", {"removed_id": waitlist_id})
    return {"status": "removed", "id": waitlist_id}


# ---------------------------------------------------------------------------
# LangGraph AI Agent Endpoints (Natural Language Booking & Human Confirmation)
# ---------------------------------------------------------------------------


@app.post("/api/agent/chat", response_model=AgentResponsePayload)
async def chat_with_careslot_agent(req: AgentChatRequest):
    """
    Invokes the stateful LangGraph agent (`gemini-2.0-flash` + fallback circuit breaker).
    Processes English, French, Arabic, and Algerian Darja requests and stages proposals
    for human confirmation before writing to the database.
    """
    config = {"configurable": {"thread_id": req.thread_id}}
    result_state = careslot_agent_graph.invoke(
        {
            "user_input": req.message,
            "staff_role": req.staff_role,
            "staff_practitioner_id": req.practitioner_id,
        },
        config=config,
    )

    return AgentResponsePayload(
        reply=result_state.get("reply_text", ""),
        detected_language=result_state.get("detected_language", "fr"),
        intent=result_state.get("intent", "book_appointment"),
        missing_fields=result_state.get("missing_fields", []),
        conflict_report=result_state.get("conflict_report", {}),
        suggested_slots=result_state.get("suggested_slots", []),
        waitlist_candidates=result_state.get("waitlist_candidates", []),
        proposed_action=result_state.get("proposed_action"),
        requires_human_confirmation=result_state.get("requires_human_confirmation", False),
        ai_fallback_used=result_state.get("ai_fallback_used", False),
    )


@app.post("/api/agent/confirm")
async def confirm_agent_proposed_action(
    req: AgentConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Human-in-the-Loop Confirmation Endpoint.
    Executes the staged appointment or waitlist replacement ONLY after explicit staff approval.
    """
    config = {"configurable": {"thread_id": req.thread_id}}
    snapshot = careslot_agent_graph.get_state(config)
    state_values = snapshot.values if snapshot else {}
    proposed = state_values.get("proposed_action")

    if not req.confirm:
        return {"status": "discarded", "message": "Proposed AI action cancelled by staff."}

    if not proposed:
        raise HTTPException(
            status_code=400,
            detail="No pending AI proposal found for this session thread.",
        )

    action_type = proposed.get("action_type")
    if action_type in ("CREATE_APPOINTMENT", "FILL_FROM_WAITLIST"):
        doc = (
            db.query(Practitioner)
            .filter(Practitioner.id == proposed["practitioner_id"])
            .first()
        )
        target_d = date.fromisoformat(proposed["appointment_date"])
        start_t = time.fromisoformat(req.selected_slot_time or proposed["start_time"])

        conflict = check_appointment_conflicts(db, doc.id, target_d, start_t)
        if conflict["has_hard_conflict"]:
            raise HTTPException(
                status_code=409,
                detail={"message": "Slot was just taken.", "reasons": conflict["reasons"]},
            )

        pt_id = proposed.get("patient_id")
        patient = db.query(Patient).filter(Patient.id == pt_id).first() if pt_id else None
        if not patient:
            norm_name = normalize_multilingual_name(proposed["patient_name"])
            norm_phone = normalize_algerian_phone(proposed["patient_phone"]) or proposed["patient_phone"]
            patient = Patient(
                full_name=proposed["patient_name"],
                normalized_name=norm_name,
                phone=norm_phone,
            )
            db.add(patient)
            db.flush()

        start_min = start_t.hour * 60 + start_t.minute
        end_min = start_min + (doc.slot_duration_min or 20)
        end_t = time(hour=(end_min // 60) % 24, minute=end_min % 60)

        appt = Appointment(
            patient_id=patient.id,
            practitioner_id=doc.id,
            room_id=doc.current_room_id,
            appointment_date=target_d,
            start_time=start_t,
            end_time=end_t,
            status=AppointmentStatus.SCHEDULED.value,
            notes=proposed.get("notes") or "Confirmed via CareSlot AI",
        )
        db.add(appt)

        if action_type == "FILL_FROM_WAITLIST":
            wl_id = req.selected_waitlist_id or proposed.get("waitlist_id")
            if wl_id:
                wl = db.query(WaitingListEntry).filter(WaitingListEntry.id == wl_id).first()
                if wl:
                    wl.is_active = False

        db.commit()
        db.refresh(appt)

        event_payload = {
            "appointment_id": appt.id,
            "patient_name": patient.full_name,
            "practitioner_id": doc.id,
            "practitioner_name": doc.full_name_lat,
            "appointment_date": target_d.isoformat(),
            "start_time": start_t.strftime("%H:%M"),
            "status": appt.status,
        }
        await ws_manager.broadcast("AI_BOOKING_CONFIRMED", event_payload)
        return {"status": "confirmed", "appointment": event_payload}

    raise HTTPException(status_code=400, detail=f"Unsupported action_type: {action_type}")


# ---------------------------------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws/clinic")
async def clinic_websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
