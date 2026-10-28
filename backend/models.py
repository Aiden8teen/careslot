"""
Database models and Algerian clinic normalization utilities for CareSlot.
Supports SQLite (for zero-config local pilot) and PostgreSQL 16 (production).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date, datetime, time
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

load_dotenv()

_DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "careslot_clinic.db")
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{_DEFAULT_DB_PATH}"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Multilingual (Arabic / Franco-Algerian / Latin) Normalization Helpers
# ---------------------------------------------------------------------------

ARABIC_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")
ALGERIAN_PHONE_RE = re.compile(r"^(?:\+213|00213|0)?([567]\d{8})$")


def normalize_multilingual_name(raw_name: str) -> str:
    """
    Normalizes Arabic and Latin/French patient names for resilient search in Algerian clinics.
    - Strips Arabic harakat/tashkeel and unifies Alef/Hamza (أ, إ, آ -> ا), Ta-Marbuta (ة -> ه), Alef Maqsura (ى -> ي)
    - Unifies Franco-Algerian spacing/prefixes ('Ben Ali' -> 'benali', 'Mohammed' -> 'mohamed', 'Abdelkader' -> 'abdelkader')
    """
    if not raw_name:
        return ""
    text = raw_name.strip().lower()
    text = ARABIC_DIACRITICS_RE.sub("", text)
    text = re.sub(r"[أإآٱ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ؤ", "و", text)
    text = re.sub(r"ئ", "ي", text)
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    text = re.sub(r"\bmohammed\b|\bmohamad\b|\bmuhammad\b", "mohamed", text)
    text = re.sub(r"\bben\s+", "ben", text)
    text = re.sub(r"\bel\s+|\bal\s+", "el", text)
    text = re.sub(r"\babdel\s+", "abdel", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_algerian_phone(phone: str) -> Optional[str]:
    """
    Validates and normalizes Algerian mobile numbers (Mobilis 06, Djezzy 07, Ooredoo 05)
    into standard 10-digit format: 05XXXXXXXX / 06XXXXXXXX / 07XXXXXXXX.
    """
    if not phone:
        return None
    cleaned = re.sub(r"[\s\-\.\(\)]", "", phone)
    match = ALGERIAN_PHONE_RE.match(cleaned)
    if match:
        return f"0{match.group(1)}"
    return cleaned if len(cleaned) >= 8 else None


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StaffRole(str, Enum):
    RECEPTIONIST = "receptionist"
    DOCTOR = "doctor"


class AppointmentStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    ARRIVED = "ARRIVED"
    IN_CONSULTATION = "IN_CONSULTATION"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class WaitlistUrgency(str, Enum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class PreferredWindow(str, Enum):
    MORNING = "MORNING"      # 08:00 - 12:30
    AFTERNOON = "AFTERNOON"  # 13:30 - 17:30
    ANY = "ANY"


# ---------------------------------------------------------------------------
# ORM Models (Single Algerian Clinic with Multiple Doctors & Rooms)
# ---------------------------------------------------------------------------


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    floor = Column(String(50), default="Rez-de-chaussée")
    is_active = Column(Boolean, default=True)

    practitioners = relationship("Practitioner", back_populates="current_room")
    appointments = relationship("Appointment", back_populates="room")


class Practitioner(Base):
    __tablename__ = "practitioners"

    id = Column(Integer, primary_key=True, index=True)
    full_name_lat = Column(String(120), nullable=False)
    full_name_ar = Column(String(120), nullable=True)
    specialty = Column(String(100), nullable=False)
    current_room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)
    slot_duration_min = Column(Integer, default=20, nullable=False)
    max_daily_appointments = Column(Integer, default=20, nullable=False)
    working_hours_json = Column(
        Text,
        default=lambda: json.dumps(
            {
                "Sat": ["08:30", "16:00"],
                "Sun": ["08:30", "16:30"],
                "Mon": ["08:30", "16:30"],
                "Tue": ["08:30", "16:30"],
                "Wed": ["08:30", "16:30"],
                "Thu": ["08:30", "15:00"],
                "Fri": [],  # Weekend in Algeria
            }
        ),
    )
    color_hex = Column(String(16), default="#0891B2")
    is_active = Column(Boolean, default=True)

    current_room = relationship("Room", back_populates="practitioners")
    appointments = relationship("Appointment", back_populates="practitioner")
    waiting_list_entries = relationship("WaitingListEntry", back_populates="practitioner")


class StaffUser(Base):
    __tablename__ = "staff_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    role = Column(String(32), nullable=False, default=StaffRole.RECEPTIONIST.value)
    practitioner_id = Column(Integer, ForeignKey("practitioners.id"), nullable=True)
    is_active = Column(Boolean, default=True)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    normalized_name = Column(String(150), nullable=False, index=True)
    phone = Column(String(30), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointments = relationship("Appointment", back_populates="patient")
    waiting_list_entries = relationship("WaitingListEntry", back_populates="patient")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint(
            "practitioner_id",
            "appointment_date",
            "arrival_number",
            name="uq_practitioner_date_arrival_num",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    practitioner_id = Column(Integer, ForeignKey("practitioners.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)
    appointment_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(String(32), default=AppointmentStatus.SCHEDULED.value, index=True)
    is_walk_in = Column(Boolean, default=False)
    arrival_number = Column(Integer, nullable=True)
    consultation_type = Column(String(50), default="STANDARD", nullable=True)
    duration_min = Column(Integer, default=20, nullable=True)
    checked_in_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="appointments")
    practitioner = relationship("Practitioner", back_populates="appointments")
    room = relationship("Room", back_populates="appointments")


class WaitingListEntry(Base):
    __tablename__ = "waiting_list"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    practitioner_id = Column(Integer, ForeignKey("practitioners.id"), nullable=False)
    preferred_date = Column(Date, nullable=True)
    preferred_window = Column(String(20), default=PreferredWindow.ANY.value)
    urgency = Column(String(20), default=WaitlistUrgency.NORMAL.value)
    reason = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="waiting_list_entries")
    practitioner = relationship("Practitioner", back_populates="waiting_list_entries")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    staff_role = Column(String(32), nullable=False)
    action = Column(String(64), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Seed Initial Algerian Clinic Data (10 Doctors, 6 Rooms, Sample Patients)
# ---------------------------------------------------------------------------


def _seed_showcase_appointments_for_date(db: Session, target_date: date, patients=None, practitioners=None) -> None:
    if patients is None:
        patients = db.query(Patient).order_by(Patient.id).all()
    if practitioners is None:
        practitioners = db.query(Practitioner).order_by(Practitioner.id).all()

    if len(patients) < 7 or len(practitioners) < 3:
        return

    # Delete existing appointments on target_date to avoid duplicates
    db.query(Appointment).filter(Appointment.appointment_date == target_date).delete()

    now = datetime.utcnow()
    showcase_appts = [
        # Dr. Youcef Amrani (Cardiologie - Room 2)
        Appointment(
            patient_id=patients[0].id,
            practitioner_id=practitioners[0].id,
            room_id=practitioners[0].current_room_id,
            appointment_date=target_date,
            start_time=time(16, 0),
            end_time=time(16, 20),
            duration_min=20,
            consultation_type="STANDARD",
            status=AppointmentStatus.IN_CONSULTATION.value,
            arrival_number=1,
            checked_in_at=now,
            notes="Suivi tension & ECG",
        ),
        Appointment(
            patient_id=patients[1].id,
            practitioner_id=practitioners[0].id,
            room_id=practitioners[0].current_room_id,
            appointment_date=target_date,
            start_time=time(16, 25),
            end_time=time(16, 45),
            duration_min=20,
            consultation_type="FOLLOW_UP",
            status=AppointmentStatus.ARRIVED.value,
            arrival_number=2,
            checked_in_at=now,
            notes="Renouvellement ordonnance",
        ),
        Appointment(
            patient_id=patients[2].id,
            practitioner_id=practitioners[0].id,
            room_id=practitioners[0].current_room_id,
            appointment_date=target_date,
            start_time=time(16, 45),
            end_time=time(17, 30),
            duration_min=45,
            consultation_type="COMPREHENSIVE",
            status=AppointmentStatus.ARRIVED.value,
            arrival_number=3,
            checked_in_at=now,
            notes="Bilan complet",
        ),
        # Dr. Meriem Kaci (Pédiatrie - Room 3)
        Appointment(
            patient_id=patients[3].id,
            practitioner_id=practitioners[1].id,
            room_id=practitioners[1].current_room_id,
            appointment_date=target_date,
            start_time=time(16, 20),
            end_time=time(16, 40),
            duration_min=20,
            consultation_type="STANDARD",
            status=AppointmentStatus.IN_CONSULTATION.value,
            arrival_number=1,
            checked_in_at=now,
            notes="Consultation pédiatrique",
        ),
        Appointment(
            patient_id=patients[4].id,
            practitioner_id=practitioners[1].id,
            room_id=practitioners[1].current_room_id,
            appointment_date=target_date,
            start_time=time(16, 40),
            end_time=time(17, 0),
            duration_min=20,
            consultation_type="FOLLOW_UP",
            status=AppointmentStatus.ARRIVED.value,
            arrival_number=2,
            checked_in_at=now,
            notes="Contrôle vaccinal",
        ),
        # Dr. Karim Benali (Médecine Générale - Room 1)
        Appointment(
            patient_id=patients[5].id,
            practitioner_id=practitioners[2].id,
            room_id=practitioners[2].current_room_id,
            appointment_date=target_date,
            start_time=time(15, 30),
            end_time=time(15, 50),
            duration_min=20,
            consultation_type="STANDARD",
            status=AppointmentStatus.FINISHED.value,
            arrival_number=1,
            is_walk_in=True,
            checked_in_at=now - timedelta(minutes=45),
            finished_at=now - timedelta(minutes=15),
            notes="Sans rendez-vous",
        ),
        Appointment(
            patient_id=patients[6].id,
            practitioner_id=practitioners[2].id,
            room_id=practitioners[2].current_room_id,
            appointment_date=target_date,
            start_time=time(16, 20),
            end_time=time(16, 40),
            duration_min=20,
            consultation_type="STANDARD",
            status=AppointmentStatus.IN_CONSULTATION.value,
            arrival_number=2,
            checked_in_at=now,
            notes="Examen général",
        ),
    ]
    db.add_all(showcase_appts)


def init_and_seed_db(force: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if force:
            db.query(AuditLog).delete()
            db.query(Appointment).delete()
            db.query(WaitingListEntry).delete()
            db.query(StaffUser).delete()
            db.query(Practitioner).delete()
            db.query(Patient).delete()
            db.query(Room).delete()
            db.commit()

        if db.query(Practitioner).count() > 0 and not force:
            # Check if today has appointments; if not, automatically populate today's schedule
            today = date.today()
            if db.query(Appointment).filter(Appointment.appointment_date == today).count() == 0:
                _seed_showcase_appointments_for_date(db, today)
                db.commit()
            return

        rooms = [
            Room(name="Salle 1 - Consultation Générale", floor="RDC"),
            Room(name="Salle 2 - Cardiologie & ECG", floor="RDC"),
            Room(name="Salle 3 - Pédiatrie", floor="1er Étage"),
            Room(name="Salle 4 - Gynécologie & Écho", floor="1er Étage"),
            Room(name="Salle 5 - Orthopédie", floor="2ème Étage"),
            Room(name="Salle 6 - Ophtalmologie / ORL", floor="2ème Étage"),
        ]
        db.add_all(rooms)
        db.flush()

        doctors_data = [
            ("Dr. Youcef Amrani (Chef de Service)", "د. يوسف عمراني", "Cardiologie", rooms[1].id, 30, 22, "#021422"),
            ("Dr. Meriem Kaci", "د. مريم قاسي", "Pédiatrie", rooms[2].id, 20, 24, "#0891B2"),
            ("Dr. Karim Benali", "د. كريم بن علي", "Médecine Générale", rooms[0].id, 15, 30, "#00852e"),
            ("Dr. Amina Boudiaf", "د. أمينة بوضياف", "Gynécologie", rooms[3].id, 30, 18, "#001f38"),
            ("Dr. Sofiane Mansouri", "د. سفيان منصوري", "Orthopédie", rooms[4].id, 20, 20, "#0891B2"),
            ("Dr. Nadia Ziani", "د. نادية زياني", "Dermatologie", rooms[0].id, 20, 22, "#059669"),
            ("Dr. Rachid Belkacem", "د. رشيد بلقاسم", "ORL", rooms[5].id, 20, 20, "#164E63"),
            ("Dr. Samira Touati", "د. سميرة تواتي", "Ophtalmologie", rooms[5].id, 20, 22, "#021422"),
            ("Dr. Mehdi Brahimi", "د. مهدي براهيمي", "Endocrinologie", rooms[1].id, 30, 15, "#00852e"),
            ("Dr. Leila Hamidi", "د. ليلى حميدي", "Médecine Interne", rooms[4].id, 30, 16, "#001f38"),
        ]

        practitioners = []
        for lat, ar, spec, rm_id, dur, cap, col in doctors_data:
            p = Practitioner(
                full_name_lat=lat,
                full_name_ar=ar,
                specialty=spec,
                current_room_id=rm_id,
                slot_duration_min=dur,
                max_daily_appointments=cap,
                color_hex=col,
            )
            practitioners.append(p)
        db.add_all(practitioners)
        db.flush()

        staff = [
            StaffUser(
                username="reception",
                full_name="Leila Mansour (Réceptionniste)",
                role=StaffRole.RECEPTIONIST.value,
                practitioner_id=None,
            ),
            StaffUser(
                username="dr.amrani",
                full_name="Dr. Youcef Amrani",
                role=StaffRole.DOCTOR.value,
                practitioner_id=practitioners[0].id,
            ),
            StaffUser(
                username="dr.kaci",
                full_name="Dr. Meriem Kaci",
                role=StaffRole.DOCTOR.value,
                practitioner_id=practitioners[1].id,
            ),
            StaffUser(
                username="dr.benali",
                full_name="Dr. Karim Benali",
                role=StaffRole.DOCTOR.value,
                practitioner_id=practitioners[2].id,
            ),
        ]
        db.add_all(staff)

        patients_seed = [
            ("محمد بن علي / Mohamed Benali", "0550123456"),
            ("فاطمة الزهراء خليفي / Fatima Zohra Khelifi", "0661987654"),
            ("عبد القادر منصوري / Abdelkader Mansouri", "0770456123"),
            ("سارة بوعلام / Sara Boualem", "0552334455"),
            ("ياسين زروقي / Yacine Zerrouki", "0662112233"),
            ("خديجة بن يحيى / Khadidja Benyahia", "0771889900"),
            ("Nabila Conflict Test", "0550998877"),
            ("Yacine Brahimi", "0550112233"),
        ]
        patients = []
        for name, phone in patients_seed:
            pt = Patient(
                full_name=name,
                normalized_name=normalize_multilingual_name(name),
                phone=phone,
            )
            patients.append(pt)
        db.add_all(patients)
        db.flush()

        today = date.today()
        # Seed 3 priority waitlist entries
        waitlist = [
            WaitingListEntry(
                patient_id=patients[4].id,  # Yacine Zerrouki
                practitioner_id=practitioners[0].id,  # Dr. Amrani
                preferred_date=today,
                preferred_window=PreferredWindow.ANY.value,
                urgency=WaitlistUrgency.HIGH.value,
                reason="Bilan pré-opératoire cardiologique",
                is_active=True,
            ),
            WaitingListEntry(
                patient_id=patients[5].id,  # Khadidja Benyahia
                practitioner_id=practitioners[1].id,  # Dr. Kaci
                preferred_date=today,
                preferred_window=PreferredWindow.MORNING.value,
                urgency=WaitlistUrgency.HIGH.value,
                reason="Fièvre enfant — disponible à 15 min de la clinique",
                is_active=True,
            ),
            WaitingListEntry(
                patient_id=patients[3].id,  # Sara Boualem
                practitioner_id=practitioners[0].id,  # Dr. Amrani
                preferred_date=today,
                preferred_window=PreferredWindow.MORNING.value,
                urgency=WaitlistUrgency.URGENT.value,
                reason="Douleur thoracique légère — souhaite le premier créneau libre le matin",
                is_active=True,
            ),
        ]
        db.add_all(waitlist)

        # Historical appointments (past visits for patient directory visit counts)
        history_appts = [
            Appointment(
                patient_id=patients[0].id,
                practitioner_id=practitioners[0].id,
                room_id=practitioners[0].current_room_id,
                appointment_date=date(2026, 10, 22),
                start_time=time(9, 0),
                end_time=time(9, 30),
                duration_min=30,
                consultation_type="STANDARD",
                status=AppointmentStatus.ARRIVED.value,
                arrival_number=1,
                checked_in_at=datetime.utcnow() - timedelta(days=6),
                notes="Contrôle tension & ECG",
            ),
            Appointment(
                patient_id=patients[1].id,
                practitioner_id=practitioners[0].id,
                room_id=practitioners[0].current_room_id,
                appointment_date=date(2026, 10, 22),
                start_time=time(9, 30),
                end_time=time(10, 0),
                duration_min=30,
                consultation_type="STANDARD",
                status=AppointmentStatus.ARRIVED.value,
                arrival_number=2,
                checked_in_at=datetime.utcnow() - timedelta(days=6),
                notes="Suivi cardiologique",
            ),
            Appointment(
                patient_id=patients[2].id,
                practitioner_id=practitioners[1].id,
                room_id=practitioners[1].current_room_id,
                appointment_date=date(2026, 10, 22),
                start_time=time(10, 0),
                end_time=time(10, 20),
                duration_min=20,
                consultation_type="STANDARD",
                status=AppointmentStatus.SCHEDULED.value,
                arrival_number=None,
                notes="Vaccination pédiatrique",
            ),
            Appointment(
                patient_id=patients[6].id,  # Nabila Conflict Test
                practitioner_id=practitioners[0].id,
                room_id=practitioners[0].current_room_id,
                appointment_date=date(2026, 10, 18),
                start_time=time(11, 30),
                end_time=time(12, 15),
                duration_min=45,
                consultation_type="STANDARD",
                status=AppointmentStatus.CANCELLED.value,
                arrival_number=None,
                notes="",
            ),
            Appointment(
                patient_id=patients[7].id,  # Yacine Brahimi
                practitioner_id=practitioners[0].id,
                room_id=practitioners[0].current_room_id,
                appointment_date=date(2026, 10, 24),
                start_time=time(10, 0),
                end_time=time(10, 30),
                duration_min=30,
                consultation_type="STANDARD",
                status=AppointmentStatus.SCHEDULED.value,
                arrival_number=None,
                notes="Booked via CareSlot AI Assistant",
            ),
        ]
        db.add_all(history_appts)

        # Showcase appointments for today
        _seed_showcase_appointments_for_date(db, today, patients=patients, practitioners=practitioners)

        # Also seed 2026-10-26 if different from today for historical view
        if today != date(2026, 10, 26):
            _seed_showcase_appointments_for_date(db, date(2026, 10, 26), patients=patients, practitioners=practitioners)

        db.commit()
