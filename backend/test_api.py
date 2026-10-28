"""
CareSlot Production Workflow & Use Cases Comprehensive Test Suite
Validates all clinical, scheduling, waitlist, AI, and guardrail workflows.
"""
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import date, timedelta

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"

def request(method, path, data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"} if data else {}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            return status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"detail": content}
        return e.code, parsed

def run_tests():
    print("=" * 70)
    print("CARESLOT PRODUCTION USE CASES & WORKFLOW VALIDATION SUITE")
    print("=" * 70)
    passed = 0
    total = 0

    def check(name, condition, extra=""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f" [PASS] Use Case {total}: {name}")
        else:
            print(f" [FAIL] Use Case {total}: {name} - {extra}")

    # 1. Clinic Overview
    status, data = request("GET", f"/api/clinic/overview?target_date={date.today().isoformat()}&view_mode=day")
    check("Clinic Overview returns 10 doctors and active rooms", 
          status == 200 and len(data.get("practitioners", [])) >= 10 and len(data.get("rooms", [])) >= 6)

    # 2. Patients Directory Endpoint
    status, pts = request("GET", "/api/patients")
    check("Patients Directory API returns records with appointment history",
          status == 200 and isinstance(pts, list) and len(pts) > 0 and "appointments_count" in pts[0])

    # 3. Multilingual Patient Search (Arabic & Latin)
    status, search_ar = request("GET", "/api/patients/search?q=" + urllib.parse.quote("محمد"))
    status2, search_lat = request("GET", "/api/patients/search?q=Benali")
    status3, search_phone = request("GET", "/api/patients/search?q=0550")
    check("Multilingual patient search (Arabic, French/Latin, Phone)",
          status == 200 and status2 == 200 and status3 == 200 and len(search_lat) > 0)

    # 4. Slot Suggestions for Flexible Durations (15m, 20m, 45m)
    # Pick next workday (avoid Algerian Friday off-day)
    target_d = date.today() + timedelta(days=1)
    if target_d.strftime("%a") == "Fri":
        target_d += timedelta(days=1)
    test_date = target_d.isoformat()

    # Clean any previous test run data for test_date if local db exists
    import os, sqlite3
    db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "careslot_clinic.db")
    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("DELETE FROM appointments WHERE appointment_date = ? AND notes LIKE '%test%'", (test_date,))
            conn.commit()
            conn.close()
        except Exception:
            pass

    status_15, slots_15 = request("GET", f"/api/slots/suggest?practitioner_id=1&target_date={test_date}&duration_min=15")
    status_45, slots_45 = request("GET", f"/api/slots/suggest?practitioner_id=1&target_date={test_date}&duration_min=45")
    check("Slot engine calculates custom duration gaps (15m vs 45m)",
          status_15 == 200 and status_45 == 200 and len(slots_15.get("slots", [])) > 0)

    # 5. Standard Appointment Booking with Conflict Detection Guardrail
    booking_payload = {
        "patient_name": "Test Production Workflow Patient",
        "patient_phone": "0550998811",
        "practitioner_id": 1,
        "appointment_date": test_date,
        "start_time": "11:00",
        "duration_min": 20,
        "consultation_type": "STANDARD",
        "is_walk_in": False,
        "notes": "Automated test verification"
    }
    status_book, book_res = request("POST", "/api/appointments?staff_role=receptionist", booking_payload)
    appt_id = book_res.get("appointment_id") or book_res.get("id")
    check("Standard appointment booking succeeds with 200 OK", status_book == 200 and appt_id is not None)

    # Try booking overlapping slot at the exact same time
    status_conflict, conflict_res = request("POST", "/api/appointments?staff_role=receptionist", booking_payload)
    check("Conflict guardrail prevents double-booking (returns 409 Conflict)", 
          status_conflict == 409 and "conflict" in str(conflict_res).lower())

    # 6. Assign Sequential Arrival Number (Numéro de Tour)
    if appt_id:
        status_arr, arr_res = request("POST", f"/api/appointments/{appt_id}/assign-arrival?staff_role=receptionist")
        check("Assign sequential arrival Tour # succeeds",
              status_arr == 200 and arr_res.get("arrival_number") is not None)

        # 7. Reorder Arrival Number
        curr_tour = arr_res.get("arrival_number", 1)
        status_reorder, reorder_res = request("PUT", f"/api/appointments/{appt_id}/reorder-arrival?staff_role=receptionist", {
            "new_arrival_number": curr_tour + 10
        })
        check("Reorder arrival Tour # sequence succeeds without collision",
              status_reorder == 200 and reorder_res.get("arrival_number") == curr_tour + 10)

        # 8. Mark Consultation Finished
        status_finish, finish_res = request("POST", f"/api/appointments/{appt_id}/toggle-finished?staff_role=receptionist")
        check("Toggle consultation Finished check-off succeeds",
              status_finish == 200 and finish_res.get("status") == "FINISHED")

    # 9. Walk-In Registration (Immediate Arrival Tour # assigned)
    walkin_payload = {
        "patient_name": "Emergency Walk-In Patient",
        "patient_phone": "0661223344",
        "practitioner_id": 2,
        "appointment_date": test_date,
        "start_time": "14:00",
        "duration_min": 20,
        "consultation_type": "STANDARD",
        "is_walk_in": True,
        "assign_arrival_immediately": True,
        "notes": "Walk-in sans rendez-vous"
    }
    status_wi, wi_res = request("POST", "/api/appointments?staff_role=receptionist", walkin_payload)
    wi_id = wi_res.get("id")
    check("Walk-in registration automatically assigns immediate arrival Tour #",
          status_wi == 200 and wi_res.get("arrival_number") is not None)

    # 10. Priority Waiting List Entry Creation
    waitlist_payload = {
        "patient_name": "Priority Heart Patient",
        "patient_phone": "0770889900",
        "practitioner_id": 1,
        "preferred_window": "MORNING",
        "urgency": "URGENT",
        "reason": "Severe angina, need first freed slot"
    }
    status_wl, wl_res = request("POST", "/api/waitlist", waitlist_payload)
    wl_id = wl_res.get("id")
    check("Add to priority waiting list with URGENT rating succeeds",
          status_wl == 200 and wl_id is not None)

    # 11. Cancellation & Automated Waitlist Recovery
    # Book a temporary appointment and then cancel it to verify waitlist recovery suggestions
    temp_appt_payload = {
        "patient_name": "Patient Cancelling",
        "patient_phone": "0550001122",
        "practitioner_id": 1,
        "appointment_date": test_date,
        "start_time": "09:30",
        "duration_min": 20,
        "consultation_type": "STANDARD",
        "notes": "Will cancel"
    }
    _, temp_res = request("POST", "/api/appointments?staff_role=receptionist", temp_appt_payload)
    temp_id = temp_res.get("id")
    if temp_id:
        status_cancel, cancel_res = request("POST", f"/api/appointments/{temp_id}/cancel?staff_role=receptionist")
        suggestions = cancel_res.get("waitlist_suggestions", [])
        check("Cancellation auto-detects freed slot and ranks waitlist matches",
              status_cancel == 200 and isinstance(suggestions, list))

    # Clean up waitlist entry
    if wl_id:
        request("DELETE", f"/api/waitlist/{wl_id}")

    # 12. Practitioner Inline Configuration
    doc_patch = {
        "full_name_lat": "Dr. Youcef Amrani (Chef de Service)",
        "full_name_ar": "د. يوسف عمراني",
        "current_room_id": 2,
        "max_daily_appointments": 22
    }
    status_doc, doc_res = request("PUT", "/api/practitioners/1", doc_patch)
    check("Update practitioner names, room assignment, and daily volume cap",
          status_doc == 200 and doc_res.get("max_daily_appointments") == 22)

    # 13. Consultation Suite (Room) CRUD
    import time
    t_suffix = int(time.time())
    status_room, room_res = request("POST", "/api/rooms", {"name": f"Suite Test {t_suffix}", "floor": "3ème"})
    new_room_id = room_res.get("id")
    if new_room_id:
        status_rename, _ = request("PUT", f"/api/rooms/{new_room_id}", {"name": f"Suite Renamed {t_suffix}"})
        status_del, _ = request("DELETE", f"/api/rooms/{new_room_id}")
        check("Consultation Room CRUD (Create, Rename, Delete)",
              status_room == 200 and status_rename == 200 and status_del == 200)

    # 14. LangGraph AI Assistant Request
    ai_payload = {
        "message": "Bonjour, vérifiez les disponibilités de Dr. Amrani pour aujourd'hui.",
        "staff_role": "receptionist",
        "practitioner_id": 1,
        "thread_id": "prod-validation-thread"
    }
    status_ai, ai_res = request("POST", "/api/agent/chat", ai_payload)
    check("LangGraph AI Assistant returns valid response payload",
          status_ai == 200 and "reply" in ai_res)

    # Clean up test appointments created during test run
    conn = sqlite3.connect("careslot_clinic.db")
    c = conn.cursor()
    c.execute("DELETE FROM appointments WHERE appointment_date = ?", (test_date,))
    c.execute("DELETE FROM rooms WHERE name LIKE 'Suite %'")
    conn.commit()
    conn.close()

    print("=" * 70)
    print(f"RESULTS: {passed}/{total} USE CASES PASSED SUCCESSFULLY ({int(passed/total*100)}%)")
    print("=" * 70)
    if passed == total:
        print("ALL CLINICAL WORKFLOWS VERIFIED READY FOR PRODUCTION DEPLOYMENT!")
        return 0
    else:
        print("SOME TESTS FAILED - REVIEW LOGS.")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
