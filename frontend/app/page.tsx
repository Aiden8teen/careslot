"use client";

import React, { useEffect, useState, useCallback } from "react";
import Image from "next/image";
import MasterCalendarTab from "../components/MasterCalendarTab";
import LiveQueueTab from "../components/LiveQueueTab";
import WaitingListTab from "../components/WaitingListTab";
import PatientsTab from "../components/PatientsTab";
import DoctorsRoomsTab from "../components/DoctorsRoomsTab";
import LoginModal from "../components/LoginModal";

function getApiBase(): string {
  if (typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
    return process.env.NEXT_PUBLIC_API_URL || "https://careslot-9lc7.onrender.com";
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

function getWsUrl(): string {
  if (typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
    return process.env.NEXT_PUBLIC_WS_URL || "wss://careslot-9lc7.onrender.com/ws/clinic";
  }
  return process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/clinic";
}

type TabKey = "calendar" | "queue" | "waitlist" | "patients" | "practitioners";

export default function CareSlotClinicApp() {
  const API_BASE = getApiBase();
  const WS_URL = getWsUrl();
  const [role, setRole] = useState<"receptionist" | "doctor">("receptionist");
  const [activeTab, setActiveTab] = useState<TabKey>("calendar");
  const [calendarView, setCalendarView] = useState<"grid" | "week" | "list">("grid");
  const [selectedDate, setSelectedDate] = useState<string>(() => new Date().toISOString().split("T")[0]);
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [staffName, setStaffName] = useState<string>("Leila Mansour");

  const [rooms, setRooms] = useState<any[]>([]);
  const [practitioners, setPractitioners] = useState<any[]>([]);
  const [appointments, setAppointments] = useState<any[]>([]);
  const [waitingList, setWaitingList] = useState<any[]>([]);
  const [weekDays, setWeekDays] = useState<string[]>([]);

  // LangGraph AI State
  const [aiInput, setAiInput] = useState<string>("");
  const [voiceLang, setVoiceLang] = useState<string>("fr-FR");
  const [aiReply, setAiReply] = useState<string>("");
  const [aiRequiresConfirm, setAiRequiresConfirm] = useState<boolean>(false);
  const [aiLoading, setAiLoading] = useState<boolean>(false);

  // Cancellation Banner State
  const [cancelAlert, setCancelAlert] = useState<any | null>(null);

  // Login Modal State
  const [loginModalOpen, setLoginModalOpen] = useState<boolean>(false);

  // Booking Modal State
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [editingApptId, setEditingApptId] = useState<number | null>(null);
  const [formPatientName, setFormPatientName] = useState<string>("");
  const [formPatientPhone, setFormPatientPhone] = useState<string>("");
  const [formPractitionerId, setFormPractitionerId] = useState<number>(1);
  const [formDate, setFormDate] = useState<string>(selectedDate);
  const [formTime, setFormTime] = useState<string>("09:00");
  const [formWalkIn, setFormWalkIn] = useState<boolean>(false);
  const [formOverrideCap, setFormOverrideCap] = useState<boolean>(false);
  const [formNotes, setFormNotes] = useState<string>("");
  const [formDuration, setFormDuration] = useState<number>(20);
  const [formConsultType, setFormConsultType] = useState<string>("STANDARD");
  const [modalSlots, setModalSlots] = useState<any[]>([]);
  const [modalError, setModalError] = useState<string>("");

  const fetchOverview = useCallback(
    async (forcedDocId?: string) => {
      try {
        const docId = forcedDocId !== undefined ? forcedDocId : selectedDoctorId;
        const mode = calendarView === "week" ? "week" : "day";
        const params = new URLSearchParams({ target_date: selectedDate, view_mode: mode });
        if (docId) params.set("practitioner_id", docId);
        const res = await fetch(`${API_BASE}/api/clinic/overview?${params.toString()}`);
        if (!res.ok) return;
        const data = await res.json();
        setRooms(data.rooms || []);
        setPractitioners(data.practitioners || []);
        setAppointments(data.appointments || []);
        setWaitingList(data.waiting_list || []);
        setWeekDays(data.week_days || []);
      } catch (err) {
        console.error("fetchOverview error:", err);
      }
    },
    [selectedDate, calendarView, selectedDoctorId]
  );

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  // Deep-linking support for direct URLs (e.g. ?tab=queue, ?modal=login)
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get("tab") as TabKey | null;
      if (tabParam && ["calendar", "queue", "waitlist", "patients", "practitioners"].includes(tabParam)) {
        setActiveTab(tabParam);
      }
      const roleParam = params.get("role");
      if (roleParam === "doctor") {
        setRole("doctor");
        const docId = params.get("doctor_id") || "1";
        setSelectedDoctorId(docId);
        const doc = practitioners.find((p) => String(p.id) === docId);
        if (doc) setStaffName(doc.full_name_lat);
      }
      const modalParam = params.get("modal");
      if (modalParam === "booking") {
        setModalOpen(true);
      } else if (modalParam === "login") {
        setLoginModalOpen(true);
      }
    }
  }, [practitioners]);

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab);
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      params.set("tab", tab);
      params.delete("modal");
      window.history.replaceState(null, "", `?${params.toString()}`);
    }
  };

  const handleRoleChange = (newRole: "receptionist" | "doctor") => {
    setRole(newRole);
    if (newRole === "doctor") {
      const docId = selectedDoctorId || (practitioners.length > 0 ? String(practitioners[0].id) : "1");
      setSelectedDoctorId(docId);
      const doc = practitioners.find((p) => String(p.id) === docId);
      setStaffName(doc ? doc.full_name_lat : "Dr. Amine");
      fetchOverview(docId);
    } else {
      setSelectedDoctorId("");
      setStaffName("Leila Mansour");
      fetchOverview("");
    }
  };

  const handleDoctorFilterChange = (id: string) => {
    setSelectedDoctorId(id);
    fetchOverview(id);
  };

  useEffect(() => {
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(WS_URL);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.event === "APPOINTMENT_CANCELLED") {
            setCancelAlert(msg.data);
          }
          fetchOverview();
        } catch (e) {
          console.error("WS message parse error:", e);
        }
      };
    } catch (e) {
      console.warn("WS connect failed:", e);
    }
    return () => {
      if (ws) ws.close();
    };
  }, [fetchOverview]);

  const askLangGraphAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!aiInput.trim()) return;
    setAiLoading(true);
    setAiReply("Processing request with LangGraph & Google AI Studio (gemini-2.0-flash)...");
    setAiRequiresConfirm(false);

    try {
      const res = await fetch(`${API_BASE}/api/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: aiInput,
          staff_role: role,
          practitioner_id: selectedDoctorId ? Number(selectedDoctorId) : null,
          thread_id: "clinic-frontdesk-default",
        }),
      });
      const data = await res.json();
      setAiReply(data.reply);
      setAiRequiresConfirm(Boolean(data.requires_human_confirmation));
    } catch (err: any) {
      setAiReply(`Error connecting to AI assistant: ${err.message}`);
    } finally {
      setAiLoading(false);
    }
  };

  const confirmAiProposal = async (confirm: boolean) => {
    try {
      const res = await fetch(`${API_BASE}/api/agent/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: "clinic-frontdesk-default",
          staff_role: role,
          confirm,
        }),
      });
      const data = await res.json();
      setAiRequiresConfirm(false);
      setAiReply(
        confirm
          ? `Confirmed & saved: ${data.appointment?.patient_name} at ${data.appointment?.start_time}`
          : "Proposal discarded."
      );
      fetchOverview();
    } catch (err: any) {
      setAiReply(`Action failed: ${err.message}`);
    }
  };

  const startVoiceInput = () => {
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      alert("Voice recognition requires Chrome, Edge, or Safari.");
      return;
    }
    const rec = new SpeechRec();
    rec.lang = voiceLang;
    rec.onresult = (ev: any) => setAiInput(ev.results[0][0].transcript);
    rec.start();
  };

  const assignArrivalNumber = async (id: number) => {
    await fetch(`${API_BASE}/api/appointments/${id}/assign-arrival?staff_role=${role}`, { method: "POST" });
    fetchOverview();
  };

  const reorderArrivalNumber = async (id: number, currentNum: number) => {
    const next = prompt("Enter new arrival number (Numéro de Tour):", String(currentNum));
    if (!next) return;
    await fetch(`${API_BASE}/api/appointments/${id}/reorder-arrival?staff_role=${role}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_arrival_number: Number(next) }),
    });
    fetchOverview();
  };

  const toggleConsultationFinished = async (id: number) => {
    await fetch(`${API_BASE}/api/appointments/${id}/toggle-finished?staff_role=${role}`, { method: "POST" });
    fetchOverview();
  };

  const cancelAppointment = async (id: number) => {
    const res = await fetch(`${API_BASE}/api/appointments/${id}/cancel?staff_role=${role}`, { method: "POST" });
    const data = await res.json();
    setCancelAlert(data);
    fetchOverview();
  };

  const refreshModalSlots = async (docId: number, dStr: string, dur?: number) => {
    const dVal = dur !== undefined ? dur : formDuration;
    try {
      const res = await fetch(
        `${API_BASE}/api/slots/suggest?practitioner_id=${docId}&target_date=${dStr}&duration_min=${dVal}`
      );
      const data = await res.json();
      setModalSlots(data.slots || []);
    } catch (e) {
      console.error("Failed to load slots:", e);
    }
  };

  const openModalForBooking = async (appt?: any, defaultDocId?: number) => {
    setModalError("");
    const docId = appt ? appt.practitioner_id : defaultDocId || practitioners[0]?.id || 1;
    const dStr = appt ? appt.appointment_date : selectedDate;
    const dur = appt
      ? appt.duration_min || 20
      : practitioners.find((p) => p.id === docId)?.slot_duration_min || 20;
    const cType = appt ? appt.consultation_type || "STANDARD" : "STANDARD";

    setEditingApptId(appt ? appt.id : null);
    setFormPatientName(appt ? appt.patient_name : "");
    setFormPatientPhone(appt ? appt.patient_phone : "");
    setFormPractitionerId(docId);
    setFormDate(dStr);
    setFormDuration(dur);
    setFormConsultType(cType);
    setFormTime(appt ? appt.start_time : "09:00");
    setFormWalkIn(false);
    setFormOverrideCap(false);
    setFormNotes(appt ? appt.notes : "");
    setModalOpen(true);

    try {
      const slotRes = await fetch(
        `${API_BASE}/api/slots/suggest?practitioner_id=${docId}&target_date=${dStr}&duration_min=${dur}`
      );
      const slotData = await slotRes.json();
      setModalSlots(slotData.slots || []);
      if (!appt && slotData.slots?.length) {
        setFormTime(slotData.slots[0].start_time);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const openBookingFromWaitlist = (entry: any) => {
    openModalForBooking(undefined, entry.practitioner_id);
    setFormPatientName(entry.patient_name);
    setFormPatientPhone(entry.patient_phone);
    setFormNotes(`Waitlist #${entry.id}: ${entry.reason || ""}`);
  };

  const openBookingForPatient = (pt: { name: string; phone: string }) => {
    openModalForBooking();
    setFormPatientName(pt.name);
    setFormPatientPhone(pt.phone);
  };

  const saveModalAppointment = async (e: React.FormEvent) => {
    e.preventDefault();
    const url = editingApptId
      ? `${API_BASE}/api/appointments/${editingApptId}?staff_role=${role}`
      : `${API_BASE}/api/appointments?staff_role=${role}`;
    const method = editingApptId ? "PUT" : "POST";

    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        patient_name: formPatientName,
        patient_phone: formPatientPhone,
        practitioner_id: formPractitionerId,
        appointment_date: formDate,
        start_time: formTime,
        duration_min: formDuration,
        consultation_type: formConsultType,
        is_walk_in: formWalkIn,
        assign_arrival_immediately: formWalkIn,
        force_daily_cap_override: formOverrideCap,
        notes: formNotes,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      setModalError((err.detail?.reasons || [err.detail?.message || "Conflict detected"]).join(" • "));
      return;
    }
    setModalOpen(false);
    fetchOverview();
  };

  return (
    <div className="min-h-screen flex bg-[#F4F6FA] text-[#0B1F4B]">
      {/* ---------------------------------------------------- */}
      {/* Left Sidebar Navigation (Matching Figma Design)      */}
      {/* ---------------------------------------------------- */}
      <aside className="w-60 md:w-64 bg-[#0B1F4B] text-white flex flex-col justify-between shrink-0 select-none shadow-xl border-r border-[#071533] h-screen sticky top-0 overflow-y-auto">
        {/* Logo Header */}
        <div className="p-5 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="relative w-11 h-11 rounded-xl bg-white/10 border border-white/15 p-1.5 flex items-center justify-center shrink-0 shadow-sm backdrop-blur-sm">
              <Image
                src="/images/careslot-icon.png"
                alt="CareSlot Logo"
                width={36}
                height={36}
                className="object-contain"
                priority
              />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-0.5">
                <span className="text-[20px] font-black tracking-tight text-white font-sans">Care</span>
                <span className="text-[20px] font-black tracking-tight text-[#01B1A9] font-sans">Slot</span>
              </div>
              <p className="text-[11px] text-white/60 font-medium truncate leading-tight">
                El-Chifa Medical Center
              </p>
            </div>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 p-3.5 space-y-1.5 overflow-y-auto">
          {[
            {
              id: "calendar" as const,
              label: "Calendar",
              icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              ),
              badge: appointments.filter((a) => a.status !== "CANCELLED").length,
            },
            {
              id: "queue" as const,
              label: "Waiting Room",
              icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              ),
              badge: appointments.filter((a) => a.arrival_number && a.status !== "FINISHED").length,
            },
            {
              id: "waitlist" as const,
              label: "Waiting List",
              icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              ),
              badge: waitingList.length,
            },
            {
              id: "patients" as const,
              label: "Patients",
              icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                </svg>
              ),
            },
            {
              id: "practitioners" as const,
              label: "Practitioners & Rooms",
              icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              ),
              badge: practitioners.length,
            },
          ].map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleTabChange(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                  isActive
                    ? "bg-white text-[#0B1F4B] shadow-sm font-bold"
                    : "text-white/80 hover:text-white hover:bg-white/10"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={isActive ? "text-[#0B1F4B]" : "text-white/70"}>
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      isActive
                        ? "bg-[#0B1F4B] text-white"
                        : "bg-white/20 text-white"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Bottom Staff Profile Card (Matching Figma) */}
        <div className="p-4 border-t border-white/10 space-y-3 bg-[#071533]/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-white/15 text-white font-bold flex items-center justify-center text-xs border border-white/20">
              {staffName
                .split(" ")
                .map((n) => n[0])
                .join("")
                .slice(0, 2)
                .toUpperCase() || "LM"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold truncate text-white">{staffName}</div>
              <div className="text-[10px] text-white/60 capitalize flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span>{role === "doctor" ? "Doctor View" : "Receptionist"}</span>
              </div>
            </div>
          </div>

          {/* Quick Role Toggle */}
          <div className="flex rounded-md bg-white/10 p-0.5 border border-white/10 text-[11px]">
            <button
              onClick={() => handleRoleChange("receptionist")}
              className={`flex-1 py-1 rounded text-center transition cursor-pointer font-semibold ${
                role === "receptionist" ? "bg-white text-[#0B1F4B]" : "text-white/70 hover:text-white"
              }`}
            >
              Receptionist
            </button>
            <button
              onClick={() => handleRoleChange("doctor")}
              className={`flex-1 py-1 rounded text-center transition cursor-pointer font-semibold ${
                role === "doctor" ? "bg-white text-[#0B1F4B]" : "text-white/70 hover:text-white"
              }`}
            >
              Doctor View
            </button>
          </div>

          <div className="flex items-center justify-between pt-1">
            <button
              onClick={() => setLoginModalOpen(true)}
              className="text-[11px] text-white/70 hover:text-white flex items-center gap-1.5 cursor-pointer"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              <span>Switch / Sign In</span>
            </button>
            <span className="text-[10px] text-white/40">v2.0</span>
          </div>
        </div>
      </aside>

      {/* ---------------------------------------------------- */}
      {/* Main Workspace Area                                  */}
      {/* ---------------------------------------------------- */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Top Workspace Header matching Figma */}
        <header className="sticky top-0 z-30 bg-white border-b border-[#E3E7EF] px-6 py-3.5 shadow-2xs">
          <div className="max-w-[1440px] mx-auto flex flex-wrap items-center justify-between gap-4">
            {/* Title / Section Breadcrumb */}
            <div className="flex items-center gap-3">
              <h1 className="text-base font-bold text-[#0B1F4B]">
                {activeTab === "calendar"
                  ? "Master Calendar"
                  : activeTab === "queue"
                  ? "Waiting Room & Live Queue"
                  : activeTab === "waitlist"
                  ? "Priority Waiting List"
                  : activeTab === "patients"
                  ? "Patients Directory"
                  : "Practitioners & Rooms"}
              </h1>
              <span className="text-xs text-[#8C9BB0]">•</span>
              <span className="text-xs text-[#64748B]">Clinique El-Chifa</span>
            </div>

            {/* AI Assistant + Book Appointment Action Button */}
            <div className="flex items-center gap-3 flex-1 max-w-2xl justify-end">
              {/* Natural Language AI input */}
              <form onSubmit={askLangGraphAgent} className="flex-1 max-w-md relative flex items-center">
                <input
                  dir="auto"
                  value={aiInput}
                  onChange={(e) => setAiInput(e.target.value)}
                  placeholder="AI prompt: 'Book Benali with Dr. Cherif today at 10:00'..."
                  className="w-full bg-[#F4F6FA] border border-[#E3E7EF] rounded-lg pl-3 pr-20 py-2 text-xs focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#0B1F4B] transition"
                />
                <div className="absolute right-1 flex items-center gap-1">
                  <button
                    type="button"
                    onClick={startVoiceInput}
                    title="Voice input (Darja / Arabic / French)"
                    className="p-1.5 text-slate-500 hover:text-[#0B1F4B] rounded hover:bg-[#E8F0FE] cursor-pointer transition"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                    </svg>
                  </button>
                  <button
                    type="submit"
                    disabled={aiLoading}
                    className="px-2.5 py-1 bg-[#0B1F4B] text-white rounded text-[11px] font-semibold hover:bg-[#071533] cursor-pointer transition"
                  >
                    {aiLoading ? "..." : "Ask"}
                  </button>
                </div>
              </form>

              {/* Language Selector */}
              <select
                value={voiceLang}
                onChange={(e) => setVoiceLang(e.target.value)}
                className="bg-[#F4F6FA] border border-[#E3E7EF] rounded-lg px-2 py-2 text-[11px] text-slate-700 font-medium cursor-pointer"
              >
                <option value="fr-FR">FR</option>
                <option value="ar-DZ">العربية</option>
                <option value="en-US">EN</option>
              </select>

              {/* + New Appointment Button matching Figma */}
              <button
                onClick={() => openModalForBooking()}
                className="flex items-center gap-1.5 px-4 py-2 bg-[#0B1F4B] text-white rounded-lg text-xs font-semibold hover:bg-[#071533] cursor-pointer transition shadow-xs shrink-0"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
                <span>+ New Appointment</span>
              </button>
            </div>
          </div>
        </header>

        {/* AI Reply Card (when active) */}
        {aiReply && (
          <div className="max-w-[1440px] w-full mx-auto px-6 pt-4">
            <div className="bg-white border border-[#E3E7EF] rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[#0B1F4B] flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  LangGraph AI Response (Gemini 2.0 Flash)
                </span>
                <button
                  onClick={() => setAiReply("")}
                  className="text-xs text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  ✕
                </button>
              </div>
              <div dir="auto" className="text-xs text-slate-700 whitespace-pre-line">
                {aiReply}
              </div>
              {aiRequiresConfirm && (
                <div className="mt-3 pt-3 border-t border-[#E3E7EF] flex gap-2">
                  <button
                    onClick={() => confirmAiProposal(true)}
                    className="px-4 py-1.5 bg-[#0F6059] text-white rounded-lg text-xs font-semibold cursor-pointer shadow-2xs"
                  >
                    Confirm &amp; Book
                  </button>
                  <button
                    onClick={() => confirmAiProposal(false)}
                    className="px-4 py-1.5 border border-[#E3E7EF] rounded-lg text-xs font-semibold hover:bg-[#F4F6FA] cursor-pointer"
                  >
                    Discard
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Cancellation Alert Toast / Banner matching Figma */}
        {cancelAlert && (
          <div className="max-w-[1440px] w-full mx-auto px-6 pt-4">
            <div className="bg-[#FFF4F2] border border-[#F8D7DA] rounded-xl p-4 shadow-xs">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className="bg-[#C87979] text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">
                    Cancellation Slot Freed
                  </span>
                  <h3 className="text-xs font-bold text-[#842029]">
                    Cancelled: {cancelAlert.patient_name} — {cancelAlert.practitioner_name} at{" "}
                    {cancelAlert.freed_time}
                  </h3>
                </div>
                <button
                  onClick={() => setCancelAlert(null)}
                  className="text-xs text-[#842029] hover:opacity-75 cursor-pointer font-bold"
                >
                  Dismiss ✕
                </button>
              </div>

              {cancelAlert.waitlist_suggestions?.length > 0 && (
                <div className="mt-3">
                  <div className="text-[11px] font-bold text-[#842029] mb-1.5">
                    Recommended Patients from Waiting List:
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                    {cancelAlert.waitlist_suggestions.map((s: any) => (
                      <div
                        key={s.waitlist_id}
                        className="bg-white border border-[#E3E7EF] rounded-lg p-2.5 flex items-center justify-between"
                      >
                        <div>
                          <div dir="auto" className="text-xs font-bold text-[#0B1F4B]">
                            {s.patient_name}
                          </div>
                          <div className="text-[10px] text-[#64748B] font-mono">
                            {s.patient_phone}
                          </div>
                          <div className="text-[10px] text-[#0F6059] mt-0.5 font-medium">
                            {s.match_explanation}
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            openModalForBooking(undefined, cancelAlert.practitioner_id);
                            setFormPatientName(s.patient_name);
                            setFormPatientPhone(s.patient_phone);
                            setFormTime(cancelAlert.freed_time);
                          }}
                          className="px-2.5 py-1 bg-[#0B1F4B] text-white rounded text-[11px] font-semibold hover:bg-[#071533] cursor-pointer"
                        >
                          Book Slot
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab Content */}
        <main className="flex-1 max-w-[1440px] w-full mx-auto px-6 py-6">
          {activeTab === "calendar" && (
            <MasterCalendarTab
              calendarView={calendarView}
              setCalendarView={setCalendarView}
              selectedDate={selectedDate}
              setSelectedDate={setSelectedDate}
              selectedDoctorId={selectedDoctorId}
              setSelectedDoctorId={handleDoctorFilterChange}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              practitioners={practitioners}
              appointments={appointments}
              weekDays={weekDays}
              onAssignArrival={assignArrivalNumber}
              onReorderArrival={reorderArrivalNumber}
              onToggleFinished={toggleConsultationFinished}
              onCancelAppointment={cancelAppointment}
              onEditOrBook={openModalForBooking}
            />
          )}

          {activeTab === "queue" && (
            <LiveQueueTab
              practitioners={practitioners}
              appointments={appointments}
              selectedDoctorId={selectedDoctorId}
              role={role}
              onReorderArrival={reorderArrivalNumber}
              onToggleFinished={toggleConsultationFinished}
            />
          )}

          {activeTab === "waitlist" && (
            <WaitingListTab
              apiBase={API_BASE}
              practitioners={practitioners}
              waitingList={waitingList}
              onRefresh={fetchOverview}
              onBookFromWaitlist={openBookingFromWaitlist}
            />
          )}

          {activeTab === "patients" && (
            <PatientsTab
              apiBase={API_BASE}
              onBookAppointmentForPatient={openBookingForPatient}
            />
          )}

          {activeTab === "practitioners" && (
            <DoctorsRoomsTab
              apiBase={API_BASE}
              practitioners={practitioners}
              rooms={rooms}
              onRefresh={fetchOverview}
            />
          )}
        </main>
      </div>

      {/* ---------------------------------------------------- */}
      {/* Booking / Edit Modal (Matching Figma Modal Design)   */}
      {/* ---------------------------------------------------- */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#E3E7EF] rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[92vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#E3E7EF] pb-3">
              <div>
                <h3 className="text-base font-bold text-[#0B1F4B]">
                  {editingApptId ? `Edit / Move Appointment #${editingApptId}` : "New Appointment / Walk-In"}
                </h3>
                <p className="text-xs text-[#64748B]">Multi-Doctor Scheduling with Conflict Protection</p>
              </div>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="text-[#8C9BB0] hover:text-[#0B1F4B] text-sm cursor-pointer p-1"
              >
                ✕
              </button>
            </div>

            {/* Error / Conflict Alert Banner */}
            {modalError && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-xs p-3 rounded-lg flex items-start gap-2">
                <span className="font-bold text-red-800">Alert:</span>
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={saveModalAppointment} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                  Patient Full Name (Arabic or Latin) *
                </label>
                <input
                  dir="auto"
                  required
                  value={formPatientName}
                  onChange={(e) => setFormPatientName(e.target.value)}
                  placeholder="Ex: Mohamed Benali / محمد بن علي"
                  className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                  Algerian Mobile (05/06/07...) *
                </label>
                <input
                  required
                  value={formPatientPhone}
                  onChange={(e) => setFormPatientPhone(e.target.value)}
                  placeholder="Ex: 0550 12 34 56"
                  className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none font-mono transition"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">Practitioner *</label>
                  <select
                    value={formPractitionerId}
                    onChange={(e) => {
                      const id = Number(e.target.value);
                      setFormPractitionerId(id);
                      refreshModalSlots(id, formDate, formDuration);
                    }}
                    className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs text-[#0B1F4B] font-medium outline-none cursor-pointer"
                  >
                    {practitioners.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.full_name_lat} ({p.specialty})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">Date *</label>
                  <input
                    type="date"
                    required
                    value={formDate}
                    onChange={(e) => {
                      const dVal = e.target.value;
                      setFormDate(dVal);
                      refreshModalSlots(formPractitionerId, dVal, formDuration);
                    }}
                    className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs text-[#0B1F4B] font-bold outline-none cursor-pointer"
                  />
                </div>
              </div>

              {/* Consultation Type Selector */}
              <div className="bg-[#F4F6FA] border border-[#E3E7EF] rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-[#0B1F4B]">
                    Consultation Type &amp; Slot Duration
                  </label>
                  <span className="text-[11px] font-bold text-[#0F6059]">
                    {formDuration} mins
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: "FOLLOW_UP", label: "⚡ Contrôle", duration: 15, sub: "Suivi, ordonnance" },
                    { id: "STANDARD", label: "🩺 Standard", duration: 20, sub: "Routine visit" },
                    { id: "COMPREHENSIVE", label: "🔬 Bilan", duration: 45, sub: "1ère consultation, ECG" },
                  ].map((t) => (
                    <button
                      type="button"
                      key={t.id}
                      onClick={() => {
                        setFormConsultType(t.id);
                        setFormDuration(t.duration);
                        refreshModalSlots(formPractitionerId, formDate, t.duration);
                      }}
                      className={`p-2.5 rounded-lg border text-left cursor-pointer transition ${
                        formConsultType === t.id
                          ? "border-[#0B1F4B] bg-white shadow-xs ring-1 ring-[#0B1F4B]"
                          : "border-[#E3E7EF] bg-white/70 hover:bg-white"
                      }`}
                    >
                      <div className="text-xs font-bold text-[#0B1F4B]">{t.label}</div>
                      <div className="text-[11px] text-[#0F6059] font-bold mt-0.5">{t.duration}m</div>
                      <div className="text-[10px] text-[#8C9BB0] mt-0.5">{t.sub}</div>
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-1.5 flex-wrap pt-1 border-t border-[#E3E7EF]">
                  <span className="text-[11px] text-[#64748B]">Or duration:</span>
                  {[10, 15, 20, 30, 45, 60].map((mins) => (
                    <button
                      type="button"
                      key={mins}
                      onClick={() => {
                        setFormDuration(mins);
                        refreshModalSlots(formPractitionerId, formDate, mins);
                      }}
                      className={`px-2 py-0.5 rounded text-[11px] font-semibold cursor-pointer transition ${
                        formDuration === mins
                          ? "bg-[#0B1F4B] text-white"
                          : "bg-white border border-[#E3E7EF] text-slate-700 hover:bg-[#F4F6FA]"
                      }`}
                    >
                      {mins}m
                    </button>
                  ))}
                </div>
              </div>

              {/* Recommended Optimal Slots */}
              <div className="bg-[#E8F0FE] border border-[#DCE7F9] rounded-xl p-3">
                <div className="text-[10px] font-bold uppercase tracking-wider text-[#0B1F4B] mb-1.5">
                  Suggested Free Slots (Click to select):
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {modalSlots.length === 0 ? (
                    <span className="text-xs text-slate-500">No free slots on this date</span>
                  ) : (
                    modalSlots.map((s) => (
                      <button
                        type="button"
                        key={s.start_time}
                        onClick={() => setFormTime(s.start_time)}
                        className={`px-2.5 py-1 rounded text-xs font-semibold cursor-pointer transition ${
                          formTime === s.start_time
                            ? "bg-[#0B1F4B] text-white shadow-2xs"
                            : "bg-white border border-[#0B1F4B]/30 text-[#0B1F4B] hover:bg-white"
                        }`}
                      >
                        {s.start_time}
                      </button>
                    ))
                  )}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                  Start Time (24h) *
                </label>
                <input
                  type="time"
                  required
                  value={formTime}
                  onChange={(e) => setFormTime(e.target.value)}
                  className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs font-bold text-[#0B1F4B] outline-none"
                />
              </div>

              <div className="space-y-1.5 pt-1">
                <label className="inline-flex items-center gap-2 text-xs font-medium text-[#0B1F4B] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formWalkIn}
                    onChange={(e) => setFormWalkIn(e.target.checked)}
                    className="rounded text-[#0B1F4B]"
                  />
                  <span>Walk-In (Sans rendez-vous) &amp; Assign Numéro de Tour now</span>
                </label>
                <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-500 cursor-pointer block">
                  <input
                    type="checkbox"
                    checked={formOverrideCap}
                    onChange={(e) => setFormOverrideCap(e.target.checked)}
                    className="rounded text-[#0B1F4B]"
                  />
                  <span>Override daily practitioner cap if booked full</span>
                </label>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                  Consultation Notes / Motif
                </label>
                <input
                  value={formNotes}
                  onChange={(e) => setFormNotes(e.target.value)}
                  placeholder="Optional motif or reason"
                  className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[#E3E7EF]">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 border border-[#E3E7EF] text-slate-700 rounded-lg text-xs font-semibold hover:bg-[#F4F6FA] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-[#0B1F4B] text-white rounded-lg text-xs font-semibold hover:bg-[#071533] cursor-pointer transition shadow-xs"
                >
                  Save Appointment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------- */}
      {/* Login Modal (Matching Figma Login Page)              */}
      {/* ---------------------------------------------------- */}
      <LoginModal
        isOpen={loginModalOpen}
        onClose={() => setLoginModalOpen(false)}
        practitioners={practitioners}
        onLoginSuccess={(user) => {
          setRole(user.role);
          setStaffName(user.name);
          if (user.role === "doctor" && user.doctorId) {
            setSelectedDoctorId(user.doctorId);
            fetchOverview(user.doctorId);
          } else {
            setSelectedDoctorId("");
            fetchOverview("");
          }
        }}
      />
    </div>
  );
}
