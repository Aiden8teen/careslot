#!/usr/bin/env python3
"""
CareSlot Clinic - Standalone Demo Dataset Seeder & Restorer
Restores the exact multi-practitioner clinic showcase data (10 practitioners,
6 consultation rooms, 8 bilingual patients, 3 priority waitlist entries, and
7 active/consultation appointments for today).
"""
import os
import sys
import sqlite3
from datetime import date, datetime, timedelta

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(ROOT_DIR, "careslot_clinic.db")


def reset_and_seed(db_path: str = DB_FILE, target_date: date = None) -> None:
    if target_date is None:
        target_date = date.today()
    target_d_str = target_date.isoformat()
    now_iso = datetime.utcnow().isoformat()

    print(f"[*] Resetting CareSlot database: {db_path}")
    print(f"[*] Active showcase date: {target_d_str}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Clean all tables
    cur.execute("DELETE FROM audit_logs")
    cur.execute("DELETE FROM appointments")
    cur.execute("DELETE FROM waiting_list")
    cur.execute("DELETE FROM staff_users")
    cur.execute("DELETE FROM practitioners")
    cur.execute("DELETE FROM patients")
    cur.execute("DELETE FROM rooms")

    # 2. Rooms
    rooms = [
        (1, "Salle 1 - Consultation Générale", "RDC", 1),
        (2, "Salle 2 - Cardiologie & ECG", "RDC", 1),
        (3, "Salle 3 - Pédiatrie", "1er Étage", 1),
        (4, "Salle 4 - Gynécologie & Écho", "1er Étage", 1),
        (5, "Salle 5 - Orthopédie", "2ème Étage", 1),
        (6, "Salle 6 - Ophtalmologie / ORL", "2ème Étage", 1),
    ]
    cur.executemany(
        "INSERT INTO rooms (id, name, floor, is_active) VALUES (?, ?, ?, ?)", rooms
    )

    # 3. Practitioners (10 doctors)
    hours = '{"Sat": ["08:30", "16:00"], "Sun": ["08:30", "16:30"], "Mon": ["08:30", "16:30"], "Tue": ["08:30", "16:30"], "Wed": ["08:30", "16:30"], "Thu": ["08:30", "15:00"], "Fri": []}'
    practitioners = [
        (1, "Dr. Youcef Amrani (Chef de Service)", "د. يوسف عمراني", "Cardiologie", 2, 30, 22, hours, "#021422", 1),
        (2, "Dr. Meriem Kaci", "د. مريم قاسي", "Pédiatrie", 3, 20, 24, hours, "#0891B2", 1),
        (3, "Dr. Karim Benali", "د. كريم بن علي", "Médecine Générale", 1, 15, 30, hours, "#00852e", 1),
        (4, "Dr. Amina Boudiaf", "د. أمينة بوضياف", "Gynécologie", 4, 30, 18, hours, "#001f38", 1),
        (5, "Dr. Sofiane Mansouri", "د. سفيان منصوري", "Orthopédie", 5, 20, 20, hours, "#0891B2", 1),
        (6, "Dr. Nadia Ziani", "د. نادية زياني", "Dermatologie", 1, 20, 22, hours, "#059669", 1),
        (7, "Dr. Rachid Belkacem", "د. رشيد بلقاسم", "ORL", 6, 20, 20, hours, "#164E63", 1),
        (8, "Dr. Samira Touati", "د. سميرة تواتي", "Ophtalmologie", 6, 20, 22, hours, "#021422", 1),
        (9, "Dr. Mehdi Brahimi", "د. مهدي براهيمي", "Endocrinologie", 2, 30, 15, hours, "#00852e", 1),
        (10, "Dr. Leila Hamidi", "د. ليلى حميدي", "Médecine Interne", 5, 30, 16, hours, "#001f38", 1),
    ]
    cur.executemany(
        """INSERT INTO practitioners 
        (id, full_name_lat, full_name_ar, specialty, current_room_id, slot_duration_min, max_daily_appointments, working_hours_json, color_hex, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        practitioners,
    )

    # 4. Staff Users
    staff = [
        (1, "reception", "Leila Mansour (Réceptionniste)", "RECEPTIONIST", None, 1),
        (2, "dr.amrani", "Dr. Youcef Amrani", "DOCTOR", 1, 1),
        (3, "dr.kaci", "Dr. Meriem Kaci", "DOCTOR", 2, 1),
        (4, "dr.benali", "Dr. Karim Benali", "DOCTOR", 3, 1),
    ]
    cur.executemany(
        "INSERT INTO staff_users (id, username, full_name, role, practitioner_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        staff,
    )

    # 5. Patients (8 bilingual patient records)
    patients = [
        (1, "محمد بن علي / Mohamed Benali", "محمد بن علي / mohamed benali", "0550123456", "2026-10-22 19:20:00"),
        (2, "فاطمة الزهراء خليفي / Fatima Zohra Khelifi", "فاطمه الزهراء خليفي / fatima zohra khelifi", "0661987654", "2026-10-22 19:20:00"),
        (3, "عبد القادر منصوري / Abdelkader Mansouri", "عبد القادر منصوري / abdelkader mansouri", "0770456123", "2026-10-22 19:20:00"),
        (4, "سارة بوعلام / Sara Boualem", "ساره بوعلام / sara boualem", "0552334455", "2026-10-22 19:20:00"),
        (5, "ياسين زروقي / Yacine Zerrouki", "ياسين زروقي / yacine zerrouki", "0662112233", "2026-10-22 19:20:00"),
        (6, "خديجة بن يحيى / Khadidja Benyahia", "خديجه بن يحيي / khadidja benyahia", "0771889900", "2026-10-22 19:20:00"),
        (7, "Nabila Conflict Test", "nabila conflict test", "0550998877", "2026-10-23 01:08:58"),
        (8, "Yacine Brahimi", "yacine brahimi", "0550112233", "2026-10-23 01:13:54"),
    ]
    cur.executemany(
        "INSERT INTO patients (id, full_name, normalized_name, phone, created_at) VALUES (?, ?, ?, ?, ?)",
        patients,
    )

    # 6. Priority Waiting List (3 active entries)
    waitlist = [
        (1, 5, 1, target_d_str, "ANY", "HIGH", "Bilan pré-opératoire cardiologique", 1, now_iso),
        (2, 6, 2, target_d_str, "MORNING", "HIGH", "Fièvre enfant — disponible à 15 min de la clinique", 1, now_iso),
        (3, 4, 1, target_d_str, "MORNING", "URGENT", "Douleur thoracique légère — souhaite le premier créneau libre le matin", 1, now_iso),
    ]
    cur.executemany(
        """INSERT INTO waiting_list 
        (id, patient_id, practitioner_id, preferred_date, preferred_window, urgency, reason, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        waitlist,
    )

    # 7. Historical Appointments
    history = [
        (1, 1, 1, 2, "2026-10-22", "09:00", "09:30", "ARRIVED", 0, 1, "STANDARD", 30, "Contrôle tension & ECG"),
        (2, 2, 1, 2, "2026-10-22", "09:30", "10:00", "ARRIVED", 0, 2, "STANDARD", 30, "Suivi cardiologique"),
        (3, 3, 2, 3, "2026-10-22", "10:00", "10:20", "SCHEDULED", 0, None, "STANDARD", 20, "Vaccination pédiatrique"),
        (4, 7, 1, 2, "2026-10-18", "11:30", "12:15", "CANCELLED", 0, None, "STANDARD", 45, ""),
        (5, 8, 1, 2, "2026-10-24", "10:00", "10:30", "SCHEDULED", 0, None, "STANDARD", 30, "Booked via CareSlot AI Assistant"),
    ]
    cur.executemany(
        """INSERT INTO appointments
        (id, patient_id, practitioner_id, room_id, appointment_date, start_time, end_time, status, is_walk_in, arrival_number, consultation_type, duration_min, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        history,
    )

    # 8. Showcase Appointments (for target_date AND for 2026-10-26 if different)
    dates_to_seed = [target_d_str]
    if target_d_str != "2026-10-26":
        dates_to_seed.append("2026-10-26")

    showcase_template = [
        # (patient_id, doc_id, room_id, start, end, status, is_walk_in, arrival_num, type, dur, notes)
        (1, 1, 2, "16:00", "16:20", "IN_CONSULTATION", 0, 1, "STANDARD", 20, "Suivi tension & ECG"),
        (2, 1, 2, "16:25", "16:45", "ARRIVED", 0, 2, "FOLLOW_UP", 20, "Renouvellement ordonnance"),
        (3, 1, 2, "16:45", "17:30", "ARRIVED", 0, 3, "COMPREHENSIVE", 45, "Bilan complet"),
        (4, 2, 3, "16:20", "16:40", "IN_CONSULTATION", 0, 1, "STANDARD", 20, "Consultation pédiatrique"),
        (5, 2, 3, "16:40", "17:00", "ARRIVED", 0, 2, "FOLLOW_UP", 20, "Contrôle vaccinal"),
        (6, 3, 1, "15:30", "15:50", "FINISHED", 1, 1, "STANDARD", 20, "Sans rendez-vous"),
        (7, 3, 1, "16:20", "16:40", "IN_CONSULTATION", 0, 2, "STANDARD", 20, "Examen général"),
    ]

    for d in dates_to_seed:
        for item in showcase_template:
            cur.execute(
                """INSERT INTO appointments 
                (patient_id, practitioner_id, room_id, appointment_date, start_time, end_time, status, is_walk_in, arrival_number, consultation_type, duration_min, notes, checked_in_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item[0], item[1], item[2], d, item[3], item[4], item[5], item[6], item[7], item[8], item[9], item[10],
                    now_iso, now_iso if item[5] == "FINISHED" else None
                ),
            )

    conn.commit()
    conn.close()
    print("[+] Successfully seeded CareSlot clinic database!")
    print(f"    - Rooms: {len(rooms)}")
    print(f"    - Practitioners: {len(practitioners)}")
    print(f"    - Patients: {len(patients)}")
    print(f"    - Waiting list entries: {len(waitlist)}")
    print(f"    - Today's showcase appointments: {len(showcase_template)}")


if __name__ == "__main__":
    target = date.today()
    if len(sys.argv) > 1:
        target = date.fromisoformat(sys.argv[1])
    reset_and_seed(target_date=target)
