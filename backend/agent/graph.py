"""
CareSlot Stateful AI Agent built with LangChain & LangGraph.
Configured for Google AI Studio (`gemini-2.0-flash`) with an isolated circuit-breaker
fallback so core clinic operations remain 100% functional even if internet/AI drops.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Literal, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.state import CareSlotAgentState
from agent.tools import (
    check_appointment_conflicts,
    rank_waiting_list_for_cancelled_slot,
    resolve_practitioner,
    search_patients,
    suggest_optimal_slots_for_doctor,
)
from models import (
    Appointment,
    AppointmentStatus,
    Patient,
    Practitioner,
    SessionLocal,
    WaitingListEntry,
    normalize_algerian_phone,
    normalize_multilingual_name,
)
from schemas import NaturalLanguageIntentSchema

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "8"))


def get_gemini_llm() -> Optional[ChatGoogleGenerativeAI]:
    """Initializes Google AI Studio `gemini-2.0-flash` model with strict timeout."""
    if not GOOGLE_API_KEY:
        return None
    try:
        return ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.1,
            timeout=AI_TIMEOUT_SECONDS,
            max_retries=1,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Deterministic Regex / Multilingual Parser Fallback (When AI is Offline)
# ---------------------------------------------------------------------------

WEEKDAY_MAP = {
    "saturday": 5, "samedi": 5, "سبت": 5, "السبت": 5, "sebt": 5,
    "sunday": 6, "dimanche": 6, "أحد": 6, "الأحد": 6, "had": 6,
    "monday": 0, "lundi": 0, "اثنين": 0, "الاثنين": 0, "tnine": 0,
    "tuesday": 1, "mardi": 1, "ثلاثاء": 1, "الثلاثاء": 1, "tlata": 1,
    "wednesday": 2, "mercredi": 2, "أربعاء": 2, "الأربعاء": 2, "larb3a": 2,
    "thursday": 3, "jeudi": 3, "خميس": 3, "الخميس": 3, "khmis": 3,
    "friday": 4, "vendredi": 4, "جمعة": 4, "الجمعة": 4, "jem3a": 4,
}


def fallback_parse_multilingual_request(text: str) -> NaturalLanguageIntentSchema:
    """
    Deterministic rule-based parser for Arabic, Algerian Darja, French, and English
    when Google AI Studio API is unreachable or times out (NFR Resilience).
    """
    lower = text.lower()
    has_arabic = bool(re.search(r"[\u0600-\u06FF]", text))
    is_darja = any(w in lower for w in ["dirli", "ghodwa", "sba7", "3chiya", "m3a", "รونديفو", "غدوة"])
    lang: Literal["ar", "dz", "fr", "en"] = "ar" if has_arabic else ("dz" if is_darja else ("fr" if any(w in lower for w in ["prends", "rdv", "demain", "avec", "pour", "annuler"]) else "en"))

    # Detect Intent
    if any(w in lower for w in ["cancel", "annul", "إلغاء", "الغي", "waitlist", "liste d'attente"]):
        intent: Literal[
            "book_appointment",
            "cancel_appointment",
            "fill_cancelled_slot",
            "suggest_optimal_slots",
            "query_schedule_or_queue",
        ] = "fill_cancelled_slot"
    elif any(w in lower for w in ["queue", "tour", "attente", "schedule", "planning", "طابور", "برنامج"]):
        intent = "query_schedule_or_queue"
    elif any(w in lower for w in ["suggest", "creneau", "créneau", "available", "libre", "فرغ"]):
        intent = "suggest_optimal_slots"
    else:
        intent = "book_appointment"

    # Phone extraction
    phone_match = re.search(r"(?:\+213|0)?[567]\d{8}", re.sub(r"[\s\-\.]", "", text))
    phone = phone_match.group(0) if phone_match else None

    # Doctor extraction
    doc_query = None
    doc_match = re.search(
        r"(?:(?:chez|avec|with|مع|عند)\s+)?(?:dr\.?|docteur|doctor|le\s+dr\.?|د\.|دكتور|الدكتور|طبيب|الطبيب)\s+([a-zA-Z\u0600-\u06FF]+)",
        text,
        re.IGNORECASE,
    )
    if doc_match:
        doc_query = doc_match.group(1)
    else:
        # Check for direct doctor names in Arabic or Latin
        doc_names = [
            ("amrani", "عمراني"), ("kaci", "قاسي"), ("benali", "بن علي"),
            ("boudiaf", "بوضياف"), ("mansouri", "منصوري"), ("ziani", "زياني"),
            ("belkacem", "بلقاسم"), ("touati", "تواتي"), ("brahimi", "براهيمي"),
            ("hamidi", "حميدي")
        ]
        for lat, ar in doc_names:
            if lat in lower or ar in text:
                doc_query = ar if ar in text else lat
                break

    # Patient extraction
    patient_name = None
    pt_match = re.search(
        r"(?:for|pour|l'|للسيد|للسيدة|لـ|لمحمد|patient|mr\.?|mme\.?|m\.?)\s+([a-zA-Z\u0600-\u06FF\s]{3,35}?)(?=\s+(?:with|avec|m3a|مع|عند|on|le|à|at|0[567]|dr|دكتور|$))",
        text,
        re.IGNORECASE,
    )
    if pt_match:
        patient_name = pt_match.group(1).strip()
    elif "لمحمد بن علي" in text:
        patient_name = "محمد بن علي"

    # Date extraction
    today = date.today()
    target_date_iso = None
    if any(w in lower for w in ["today", "aujourd'hui", "اليوم", "lyoum"]):
        target_date_iso = today.isoformat()
    elif any(w in lower for w in ["tomorrow", "demain", "غدا", "غدوة", "ghodwa"]):
        target_date_iso = (today + timedelta(days=1)).isoformat()
    else:
        iso_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", text)
        if iso_match:
            target_date_iso = iso_match.group(1)
        else:
            for day_word, weekday_idx in WEEKDAY_MAP.items():
                if day_word in lower:
                    days_ahead = (weekday_idx - today.weekday() + 7) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    target_date_iso = (today + timedelta(days=days_ahead)).isoformat()
                    break

    # Time extraction
    target_time_hhmm = None
    time_match = re.search(r"\b([01]?\d|2[0-3])[:hH]([0-5]\d)?\b", text)
    if time_match:
        hh = int(time_match.group(1))
        mm = int(time_match.group(2) or 0)
        if 1 <= hh <= 6:
            hh += 12
        target_time_hhmm = f"{hh:02d}:{mm:02d}"
    else:
        darja_hours = {
            "العشرة": "10:00", "عشرة": "10:00",
            "التسعة": "09:00", "تسعة": "09:00",
            "الثمانية": "08:30", "ثمانية": "08:30",
            "الحداش": "11:00", "حداش": "11:00",
            "طناش": "12:00", "اثنا عشر": "12:00",
            "الوحدة": "13:00", "وحدة": "13:00",
            "الزوج": "14:00", "زوج": "14:00",
            "الثلاثة": "15:00", "ثلاثة": "15:00",
            "الربعة": "16:00", "ربعة": "16:00",
        }
        for dh_word, dh_val in darja_hours.items():
            if dh_word in text:
                target_time_hhmm = dh_val
                break

    # Window extraction
    pref_window: Literal["MORNING", "AFTERNOON", "ANY"] = "ANY"
    if any(w in lower for w in ["morning", "matin", "sba7", "صباح", "الصباح"]):
        pref_window = "MORNING"
    elif any(w in lower for w in ["afternoon", "après-midi", "apres-midi", "3chiya", "مساء", "العشية"]):
        pref_window = "AFTERNOON"

    return NaturalLanguageIntentSchema(
        detected_language=lang,
        intent=intent,
        patient_name=patient_name,
        patient_phone=phone,
        practitioner_query=doc_query,
        target_date_iso=target_date_iso,
        target_time_hhmm=target_time_hhmm,
        preferred_window=pref_window,
    )


# ---------------------------------------------------------------------------
# LangGraph Nodes
# ---------------------------------------------------------------------------


def node_ingest_and_extract(state: CareSlotAgentState) -> dict[str, Any]:
    """
    Node 1: Uses Gemini 2.0 Flash (`gemini-2.0-flash`) with structured output to extract
    multilingual intent (Arabic, Algerian Darja, French, English).
    Falls back cleanly to deterministic parser if Google AI Studio is unreachable.
    """
    user_text = state.get("user_input", "").strip()
    staff_role = state.get("staff_role", "receptionist")
    today_str = date.today().isoformat()
    weekday_str = date.today().strftime("%A")

    with SessionLocal() as db:
        doctors = db.query(Practitioner).filter(Practitioner.is_active == True).all()
        doc_roster = ", ".join(
            [f"{d.full_name_lat} ({d.full_name_ar} - {d.specialty})" for d in doctors]
        )

    llm = get_gemini_llm()
    ai_fallback_used = False
    parsed: Optional[NaturalLanguageIntentSchema] = None

    if llm is not None:
        try:
            structured_llm = llm.with_structured_output(NaturalLanguageIntentSchema)
            sys_prompt = (
                f"You are CareSlot AI, the intelligent medical scheduling assistant for an Algerian clinic.\n"
                f"Today is {weekday_str}, {today_str}.\n"
                f"Available clinic doctors: {doc_roster}.\n"
                f"Staff Role making request: {staff_role}.\n"
                f"Extract the structured scheduling intent from the staff member's message (which may be in "
                f"English, French, Modern Standard Arabic, or Algerian Darja).\n"
                f"CRITICAL RULE: Never guess or invent a time, date, or doctor if the user did not specify one. "
                f"Leave unspecified fields as null."
            )
            parsed = structured_llm.invoke(
                [
                    SystemMessage(content=sys_prompt),
                    HumanMessage(content=user_text),
                ]
            )
        except Exception:
            ai_fallback_used = True
            parsed = fallback_parse_multilingual_request(user_text)
    else:
        ai_fallback_used = True
        parsed = fallback_parse_multilingual_request(user_text)

    if parsed is None:
        ai_fallback_used = True
        parsed = fallback_parse_multilingual_request(user_text)

    return {
        "detected_language": parsed.detected_language,
        "intent": parsed.intent,
        "extracted_entities": parsed.model_dump(),
        "ai_fallback_used": ai_fallback_used,
    }


def node_role_permission_guard(state: CareSlotAgentState) -> dict[str, Any]:
    """
    Node 2: Enforces RBAC between Receptionist (`receptionist`) and Doctor (`doctor`).
    Doctors have schedule & live queue visibility and consultation completion controls,
    while front-desk booking and waitlist replacement confirmation belong to the Receptionist
    (or a Doctor booking specifically into their own schedule).
    """
    role = state.get("staff_role", "receptionist")
    intent = state.get("intent", "book_appointment")
    entities = state.get("extracted_entities", {})
    staff_doc_id = state.get("staff_practitioner_id")

    if role == "doctor" and intent in ("book_appointment", "fill_cancelled_slot"):
        # Check if doctor is trying to modify another doctor's schedule
        with SessionLocal() as db:
            matched_docs = resolve_practitioner(db, entities.get("practitioner_query"))
            if matched_docs and staff_doc_id and matched_docs[0].id != staff_doc_id:
                return {
                    "intent": "role_restricted",
                    "requires_human_confirmation": False,
                    "reply_text": (
                        f"Role Restriction (Doctor View): You are signed in as a Doctor and can only manage "
                        f"your own consultation queue or request the Receptionist to book across other specialists "
                        f"({matched_docs[0].full_name_lat})."
                    ),
                }
    return {}


def node_validate_and_optimize_slots(state: CareSlotAgentState) -> dict[str, Any]:
    """
    Node 3: Validates extracted booking parameters against the database, checks for missing
    fields (never guesses missing time or practitioner), runs the 4-dimensional
    conflict detector, and computes optimal slot suggestions.
    """
    entities = state.get("extracted_entities", {})
    missing: list[str] = []

    with SessionLocal() as db:
        # 1. Resolve Practitioner
        doc_query = entities.get("practitioner_query")
        matched_docs = resolve_practitioner(db, doc_query) if doc_query else []

        if not matched_docs:
            missing.append("practitioner (Which doctor should I book with?)")
            selected_doc = None
        elif len(matched_docs) > 1:
            names = ", ".join(d.full_name_lat for d in matched_docs)
            missing.append(f"practitioner_disambiguation (Multiple matches: {names})")
            selected_doc = None
        else:
            selected_doc = matched_docs[0]

        # 2. Resolve Patient
        patient_name = entities.get("patient_name")
        patient_phone = normalize_algerian_phone(entities.get("patient_phone") or "")
        existing_patients = search_patients(db, patient_name or patient_phone or "")
        resolved_patient = existing_patients[0] if len(existing_patients) == 1 else None

        if not patient_name and not resolved_patient:
            missing.append("patient_name (Patient full name in Arabic or Latin)")
        if not patient_phone and not resolved_patient:
            missing.append("patient_phone (Algerian mobile number: 05/06/07XXXXXXXX)")

        # 3. Resolve Target Date
        target_date_iso = entities.get("target_date_iso")
        if not target_date_iso:
            missing.append("appointment_date (e.g., Today, Tomorrow, Tuesday)")
            target_d = date.today()
        else:
            try:
                target_d = date.fromisoformat(target_date_iso)
            except ValueError:
                missing.append("appointment_date (Valid date format YYYY-MM-DD)")
                target_d = date.today()

        # 4. Suggest Optimal Slots if Doctor is known
        pref_window = entities.get("preferred_window") or "ANY"
        suggested_slots = (
            suggest_optimal_slots_for_doctor(db, selected_doc.id, target_d, pref_window, limit=4)
            if selected_doc
            else []
        )

        # 5. Check Exact Time & Conflict Detection
        target_time_hhmm = entities.get("target_time_hhmm")
        conflict_report: dict[str, Any] = {}
        if not target_time_hhmm:
            missing.append("start_time (Please pick one of the suggested available slots)")
        elif selected_doc:
            try:
                start_t = time.fromisoformat(target_time_hhmm)
                conflict_report = check_appointment_conflicts(
                    db, selected_doc.id, target_d, start_t
                )
            except ValueError:
                missing.append("start_time (Valid 24h time HH:MM)")

        # Build response & confirmation gate
        if missing or conflict_report.get("has_hard_conflict"):
            reasons_txt = ""
            if conflict_report.get("has_hard_conflict"):
                reasons_txt = "⚠️ **Scheduling Conflict Detected:** " + " ".join(
                    conflict_report.get("reasons", [])
                ) + "\n\n"

            slots_txt = ""
            if suggested_slots:
                formatted_slots = ", ".join(
                    f"**{s['start_time']}–{s['end_time']}** ({s['rationale']})"
                    for s in suggested_slots
                )
                slots_txt = f"\n\n**AI Recommended Slots for {selected_doc.full_name_lat} on {target_d.isoformat()}:**\n{formatted_slots}"

            missing_txt = (
                "Please specify: " + ", ".join(missing) + "."
                if missing
                else "Please select one of the conflict-free slots above."
            )

            return {
                "missing_fields": missing,
                "conflict_report": conflict_report,
                "suggested_slots": suggested_slots,
                "requires_human_confirmation": False,
                "proposed_action": None,
                "reply_text": f"{reasons_txt}{missing_txt}{slots_txt}",
            }

        # All fields present and no hard conflict -> Stage Proposal for Human Confirmation!
        final_patient_name = resolved_patient.full_name if resolved_patient else patient_name
        final_patient_phone = resolved_patient.phone if resolved_patient else patient_phone
        room_label = (
            selected_doc.current_room.name
            if selected_doc and selected_doc.current_room
            else "Unassigned Room"
        )
        warnings_list = conflict_report.get("warnings", [])
        warning_banner = (
            "\n⚠️ *Note:* " + " ".join(warnings_list) if warnings_list else ""
        )

        proposed = {
            "action_type": "CREATE_APPOINTMENT",
            "patient_id": resolved_patient.id if resolved_patient else None,
            "patient_name": final_patient_name,
            "patient_phone": final_patient_phone,
            "practitioner_id": selected_doc.id,
            "practitioner_name": f"{selected_doc.full_name_lat} ({selected_doc.full_name_ar})",
            "room_id": selected_doc.current_room_id,
            "room_name": room_label,
            "appointment_date": target_d.isoformat(),
            "start_time": conflict_report["slot_start"],
            "end_time": conflict_report["slot_end"],
            "notes": entities.get("notes") or "Booked via CareSlot AI Assistant",
        }

        reply = (
            f"✅ **Proposed Appointment Ready for Confirmation:**\n"
            f"- **Patient:** {final_patient_name} (`{final_patient_phone}`)\n"
            f"- **Doctor:** {selected_doc.full_name_lat} ({selected_doc.specialty})\n"
            f"- **Room:** {room_label}\n"
            f"- **Date & Time:** {target_d.isoformat()} at **{conflict_report['slot_start']}–{conflict_report['slot_end']}**"
            f"{warning_banner}\n\n"
            f"*Please click **Confirm Booking** to save to the master schedule.*"
        )

        return {
            "missing_fields": [],
            "conflict_report": conflict_report,
            "suggested_slots": suggested_slots,
            "proposed_action": proposed,
            "requires_human_confirmation": True,
            "reply_text": reply,
        }


def node_match_waitlist(state: CareSlotAgentState) -> dict[str, Any]:
    """
    Node 4: Handles cancellation recovery & waiting list matching.
    Never auto-books; proposes the top waiting list candidate for receptionist confirmation.
    """
    entities = state.get("extracted_entities", {})
    with SessionLocal() as db:
        doc_query = entities.get("practitioner_query")
        matched_docs = resolve_practitioner(db, doc_query) if doc_query else []
        selected_doc = matched_docs[0] if matched_docs else db.query(Practitioner).first()

        target_d = (
            date.fromisoformat(entities["target_date_iso"])
            if entities.get("target_date_iso")
            else date.today()
        )
        target_t = (
            time.fromisoformat(entities["target_time_hhmm"])
            if entities.get("target_time_hhmm")
            else time(10, 0)
        )

        candidates = rank_waiting_list_for_cancelled_slot(
            db, selected_doc.id, target_d, target_t
        )

        if not candidates:
            return {
                "waitlist_candidates": [],
                "requires_human_confirmation": False,
                "reply_text": f"No active waiting-list patients found for {selected_doc.full_name_lat}.",
            }

        top = candidates[0]
        proposed = {
            "action_type": "FILL_FROM_WAITLIST",
            "waitlist_id": top["waitlist_id"],
            "patient_id": top["patient_id"],
            "patient_name": top["patient_name"],
            "patient_phone": top["patient_phone"],
            "practitioner_id": top["practitioner_id"],
            "practitioner_name": top["practitioner_name"],
            "appointment_date": top["target_date"],
            "start_time": top["target_time"],
        }

        reply = (
            f"🔔 **AI Waiting-List Replacement Suggestion for {selected_doc.full_name_lat} ({top['target_date']} at {top['target_time']}):**\n"
            f"1. **{top['patient_name']}** (`{top['patient_phone']}`) — Score: **{top['match_score']}** ({top['match_explanation']}) — *{top['reason']}*\n"
        )
        if len(candidates) > 1:
            alt = candidates[1]
            reply += f"2. Backup: **{alt['patient_name']}** (`{alt['patient_phone']}`) — {alt['match_explanation']}\n"
        reply += "\n*Call the patient and click **Confirm Replacement** to book the freed slot.*"

        return {
            "waitlist_candidates": candidates,
            "proposed_action": proposed,
            "requires_human_confirmation": True,
            "reply_text": reply,
        }


def node_query_schedule_or_queue(state: CareSlotAgentState) -> dict[str, Any]:
    """
    Node 5: Answers live schedule & arrival queue ('Tour') questions for Doctors and Receptionists.
    """
    entities = state.get("extracted_entities", {})
    with SessionLocal() as db:
        doc_query = entities.get("practitioner_query")
        matched_docs = resolve_practitioner(db, doc_query) if doc_query else []
        if not matched_docs and state.get("staff_practitioner_id"):
            doc = db.query(Practitioner).filter(Practitioner.id == state["staff_practitioner_id"]).first()
            matched_docs = [doc] if doc else []

        today = date.today()
        if matched_docs:
            doc = matched_docs[0]
            appts = (
                db.query(Appointment)
                .filter(
                    Appointment.practitioner_id == doc.id,
                    Appointment.appointment_date == today,
                    Appointment.status != AppointmentStatus.CANCELLED.value,
                )
                .order_by(Appointment.arrival_number.is_(None), Appointment.arrival_number, Appointment.start_time)
                .all()
            )
            arrived = [a for a in appts if a.status in (AppointmentStatus.ARRIVED.value, AppointmentStatus.IN_CONSULTATION.value)]
            finished = [a for a in appts if a.status == AppointmentStatus.FINISHED.value]
            suggested = suggest_optimal_slots_for_doctor(db, doc.id, today, limit=3)

            queue_lines = [
                f"Tour **#{a.arrival_number:02d}** — {a.patient.full_name} ({a.status})"
                for a in arrived
                if a.arrival_number
            ]
            queue_summary = "\n".join(queue_lines) if queue_lines else "No patients currently waiting in queue."

            return {
                "suggested_slots": suggested,
                "requires_human_confirmation": False,
                "reply_text": (
                    f"📋 **Live Status for {doc.full_name_lat} ({doc.specialty}):**\n"
                    f"- **Room:** {doc.current_room.name if doc.current_room else 'Unassigned'}\n"
                    f"- **Today's Load:** {len(appts)}/{doc.max_daily_appointments} booked ({len(finished)} finished, {len(arrived)} in active queue)\n"
                    f"- **Active Arrival Queue (Tour):**\n{queue_summary}"
                ),
            }

        total_today = db.query(Appointment).filter(Appointment.appointment_date == today).count()
        return {
            "requires_human_confirmation": False,
            "reply_text": f"📊 **Clinic Overview ({today.isoformat()}):** {total_today} appointments scheduled across 10 practitioners.",
        }


# ---------------------------------------------------------------------------
# Routing Functions & Graph Compilation
# ---------------------------------------------------------------------------


def route_after_permission_guard(
    state: CareSlotAgentState,
) -> Literal[
    "validate_and_optimize_slots",
    "match_waitlist",
    "query_schedule_or_queue",
    "__end__",
]:
    intent = state.get("intent", "book_appointment")
    if intent == "role_restricted":
        return "__end__"
    if intent in ("book_appointment", "suggest_optimal_slots"):
        return "validate_and_optimize_slots"
    if intent in ("cancel_appointment", "fill_cancelled_slot"):
        return "match_waitlist"
    return "query_schedule_or_queue"


def build_careslot_graph():
    """Compiles the stateful LangGraph workflow with an in-memory checkpointer."""
    workflow = StateGraph(CareSlotAgentState)

    workflow.add_node("ingest_and_extract", node_ingest_and_extract)
    workflow.add_node("role_permission_guard", node_role_permission_guard)
    workflow.add_node("validate_and_optimize_slots", node_validate_and_optimize_slots)
    workflow.add_node("match_waitlist", node_match_waitlist)
    workflow.add_node("query_schedule_or_queue", node_query_schedule_or_queue)

    workflow.add_edge(START, "ingest_and_extract")
    workflow.add_edge("ingest_and_extract", "role_permission_guard")
    workflow.add_conditional_edges(
        "role_permission_guard",
        route_after_permission_guard,
        {
            "validate_and_optimize_slots": "validate_and_optimize_slots",
            "match_waitlist": "match_waitlist",
            "query_schedule_or_queue": "query_schedule_or_queue",
            "__end__": END,
        },
    )
    workflow.add_edge("validate_and_optimize_slots", END)
    workflow.add_edge("match_waitlist", END)
    workflow.add_edge("query_schedule_or_queue", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


careslot_agent_graph = build_careslot_graph()
