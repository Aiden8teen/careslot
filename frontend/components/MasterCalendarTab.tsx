"use client";

import React from "react";

interface MasterCalendarTabProps {
  calendarView: "grid" | "week" | "list";
  setCalendarView: (view: "grid" | "week" | "list") => void;
  selectedDate: string;
  setSelectedDate: (d: string) => void;
  selectedDoctorId: string;
  setSelectedDoctorId: (id: string) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  practitioners: any[];
  appointments: any[];
  weekDays: string[];
  onAssignArrival: (id: number) => void;
  onReorderArrival: (id: number, currentNum: number) => void;
  onToggleFinished: (id: number) => void;
  onCancelAppointment: (id: number) => void;
  onEditOrBook: (appt?: any, docId?: number) => void;
}

export default function MasterCalendarTab({
  calendarView,
  setCalendarView,
  selectedDate,
  setSelectedDate,
  selectedDoctorId,
  setSelectedDoctorId,
  searchQuery,
  setSearchQuery,
  practitioners,
  appointments,
  weekDays,
  onAssignArrival,
  onReorderArrival,
  onToggleFinished,
  onCancelAppointment,
  onEditOrBook,
}: MasterCalendarTabProps) {
  const visibleDoctors = selectedDoctorId
    ? practitioners.filter((d) => String(d.id) === String(selectedDoctorId))
    : practitioners;

  const filteredAppointments = appointments.filter(
    (a) =>
      !searchQuery ||
      a.patient_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.patient_phone.includes(searchQuery) ||
      a.practitioner_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const changeDay = (offset: number) => {
    const curr = new Date(selectedDate);
    curr.setDate(curr.getDate() + offset);
    setSelectedDate(curr.toISOString().split("T")[0]);
  };

  const formattedDateHeader = (() => {
    try {
      const d = new Date(selectedDate + "T12:00:00");
      return d.toLocaleDateString("en-US", {
        weekday: "long",
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch {
      return selectedDate;
    }
  })();

  return (
    <div className="space-y-4">
      {/* Figma Toolbar with Date Picker, View Switcher & Doctor Filter */}
      <div className="bg-white border border-[#E3E7EF] rounded-xl p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
        {/* Left: Date selector & quick day shifts */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1 bg-[#F4F6FA] border border-[#E3E7EF] rounded-lg p-1">
            <button
              onClick={() => changeDay(-1)}
              className="p-1.5 text-slate-600 hover:text-[#0B1F4B] hover:bg-white rounded transition cursor-pointer"
              title="Previous Day"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="bg-transparent text-xs font-bold text-[#0B1F4B] px-2 outline-none cursor-pointer"
            />
            <button
              onClick={() => changeDay(1)}
              className="p-1.5 text-slate-600 hover:text-[#0B1F4B] hover:bg-white rounded transition cursor-pointer"
              title="Next Day"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
          <span className="text-xs font-semibold text-slate-700 hidden sm:inline">
            {formattedDateHeader}
          </span>

          {/* View Switcher Pills */}
          <div className="flex items-center bg-[#F4F6FA] p-1 rounded-lg border border-[#E3E7EF]">
            {(["grid", "week", "list"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setCalendarView(mode)}
                className={`px-3 py-1 rounded-md text-xs font-semibold cursor-pointer transition ${
                  calendarView === mode
                    ? "bg-[#0B1F4B] text-white shadow-xs"
                    : "text-[#64748B] hover:text-[#0B1F4B]"
                }`}
              >
                {mode === "grid" ? "Day Grid" : mode === "week" ? "Week (7D)" : "List"}
              </button>
            ))}
          </div>
        </div>

        {/* Right: Practitioner Filter & Patient Search */}
        <div className="flex flex-wrap items-center gap-2.5">
          <select
            value={selectedDoctorId}
            onChange={(e) => setSelectedDoctorId(e.target.value)}
            className="border border-[#E3E7EF] rounded-lg px-3 py-1.5 text-xs text-[#0B1F4B] bg-[#F4F6FA] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#0B1F4B] transition cursor-pointer font-medium"
          >
            <option value="">All Practitioners ({practitioners.length})</option>
            {practitioners.map((p) => (
              <option key={p.id} value={p.id}>
                {p.full_name_lat} ({p.specialty} • {p.room_name})
              </option>
            ))}
          </select>

          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-[#8C9BB0]">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </span>
            <input
              dir="auto"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search appointments..."
              className="pl-8 pr-3 py-1.5 text-xs border border-[#E3E7EF] rounded-lg w-48 sm:w-60 bg-[#F4F6FA] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#0B1F4B] transition"
            />
          </div>
        </div>
      </div>

      {/* Multi-Doctor Day Grid */}
      {calendarView === "grid" && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {visibleDoctors.map((doc) => {
            const docAppts = filteredAppointments.filter(
              (a) => a.practitioner_id === doc.id && a.status !== "CANCELLED"
            );
            return (
              <div
                key={doc.id}
                className="border border-[#E3E7EF] rounded-xl bg-white shadow-xs flex flex-col overflow-hidden"
              >
                {/* Doctor Column Header */}
                <div className="p-4 bg-[#F4F6FA] border-b border-[#E3E7EF] flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-bold text-[#0B1F4B]">
                        {doc.full_name_lat}
                      </span>
                      {doc.delay_status === "HEAVY" ? (
                        <span className="bg-red-50 text-red-700 border border-red-200 text-[10px] font-bold px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-600 animate-pulse"></span>
                          +{doc.running_delay_min}m delay
                        </span>
                      ) : doc.delay_status === "MODERATE" ? (
                        <span className="bg-amber-50 text-amber-800 border border-amber-300 text-[10px] font-bold px-2 py-0.5 rounded-full">
                          +{doc.running_delay_min}m delay
                        </span>
                      ) : (
                        <span className="bg-[#E8F5E9] text-[#1B5E20] border border-[#C8E6C9] text-[10px] font-bold px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-600"></span>
                          À l'heure
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-[#64748B] mt-0.5">
                      {doc.full_name_ar} • {doc.specialty}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="inline-block bg-white text-[#0B1F4B] border border-[#E3E7EF] font-semibold text-[10px] px-2 py-0.5 rounded">
                        {doc.room_name}
                      </span>
                      <span className="text-[11px] text-[#64748B]">
                        {doc.today_booked_count}/{doc.max_daily_appointments} booked
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => onEditOrBook(undefined, doc.id)}
                    className="px-2.5 py-1.5 bg-[#0B1F4B] text-white rounded-lg text-xs font-semibold hover:bg-[#071533] cursor-pointer transition shadow-2xs"
                  >
                    + Book
                  </button>
                </div>

                {/* Appointment Cards in this Column */}
                <div className="p-3.5 space-y-2.5 flex-1 bg-white">
                  {docAppts.length === 0 ? (
                    <div className="text-xs text-[#8C9BB0] py-10 text-center flex flex-col items-center justify-center">
                      <svg className="w-8 h-8 text-slate-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      No bookings scheduled
                    </div>
                  ) : (
                    docAppts.map((a) => {
                      const isFinished = a.status === "FINISHED";
                      return (
                        <div
                          key={a.id}
                          className={`border rounded-lg p-3 transition ${
                            isFinished
                              ? "bg-slate-50/70 border-slate-200 opacity-60"
                              : "bg-white border-[#E3E7EF] hover:border-[#0B1F4B]/40 hover:shadow-2xs"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className={`text-xs font-bold ${isFinished ? "line-through text-slate-500" : "text-[#0B1F4B]"}`}>
                                  {a.start_time}–{a.end_time}
                                </span>
                                <span className="bg-[#F4F6FA] text-slate-600 border border-[#E3E7EF] text-[10px] font-semibold px-1.5 py-0.5 rounded">
                                  {a.duration_min || 20}m
                                </span>
                                {a.consultation_type && a.consultation_type !== "STANDARD" && (
                                  <span className="bg-sky-50 text-sky-800 border border-sky-200 text-[10px] font-bold px-1.5 py-0.5 rounded">
                                    {a.consultation_type === "FOLLOW_UP" ? "⚡ Contrôle" : "🔬 Bilan"}
                                  </span>
                                )}
                                {a.arrival_number && (
                                  <span className="bg-[#0F6059] text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                                    Tour #{String(a.arrival_number).padStart(2, "0")}
                                  </span>
                                )}
                              </div>

                              <div
                                dir="auto"
                                className={`text-sm font-semibold mt-1 ${
                                  isFinished ? "line-through text-slate-500" : "text-[#0B1F4B]"
                                }`}
                              >
                                {a.patient_name}
                              </div>
                              <div className="text-[11px] text-[#64748B] font-mono">
                                {a.patient_phone}
                              </div>
                            </div>

                            <label className="inline-flex items-center gap-1.5 text-[11px] font-semibold border border-[#E3E7EF] px-2 py-1 rounded-md bg-[#F4F6FA] hover:bg-white cursor-pointer transition select-none">
                              <input
                                type="checkbox"
                                checked={isFinished}
                                onChange={() => onToggleFinished(a.id)}
                                className="rounded text-[#0B1F4B] focus:ring-0"
                              />
                              <span>Done</span>
                            </label>
                          </div>

                          {!isFinished && (
                            <div className="flex items-center gap-2 pt-2.5 mt-2 border-t border-[#E3E7EF]">
                              {!a.arrival_number ? (
                                <button
                                  onClick={() => onAssignArrival(a.id)}
                                  className="px-2.5 py-1 bg-[#0B1F4B] text-white rounded text-[11px] font-semibold hover:bg-[#071533] cursor-pointer transition"
                                >
                                  + Tour #
                                </button>
                              ) : (
                                <button
                                  onClick={() => onReorderArrival(a.id, a.arrival_number)}
                                  className="px-2 py-1 border border-[#E3E7EF] text-slate-700 rounded text-[11px] hover:bg-[#F4F6FA] cursor-pointer transition"
                                >
                                  Reorder
                                </button>
                              )}
                              <button
                                onClick={() => onEditOrBook(a)}
                                className="px-2 py-1 border border-[#E3E7EF] text-slate-700 rounded text-[11px] hover:bg-[#F4F6FA] cursor-pointer transition"
                              >
                                Edit / Move
                              </button>
                              <button
                                onClick={() => onCancelAppointment(a.id)}
                                className="px-2 py-1 border border-red-200 text-red-600 rounded text-[11px] ml-auto hover:bg-red-50 cursor-pointer transition"
                              >
                                Cancel
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 7-Day Week View */}
      {calendarView === "week" && (
        <div className="grid grid-cols-1 sm:grid-cols-7 gap-3">
          {weekDays.map((dStr) => {
            const dayAppts = filteredAppointments.filter(
              (a) => a.appointment_date === dStr && a.status !== "CANCELLED"
            );
            return (
              <div
                key={dStr}
                className="border border-[#E3E7EF] rounded-xl bg-white shadow-xs flex flex-col overflow-hidden"
              >
                <div className="p-3 bg-[#F4F6FA] border-b border-[#E3E7EF] text-center">
                  <div className="text-xs font-bold text-[#0B1F4B]">{dStr}</div>
                  <div className="text-[10px] text-[#64748B] font-medium mt-0.5">
                    {dayAppts.length} Appt(s)
                  </div>
                </div>
                <div className="p-2 space-y-2 flex-1">
                  {dayAppts.length === 0 ? (
                    <div className="text-[11px] text-slate-400 text-center py-6">Empty</div>
                  ) : (
                    dayAppts.map((a) => (
                      <div
                        key={a.id}
                        className="border border-[#E3E7EF] rounded-lg p-2 text-xs hover:border-[#0B1F4B]/50 transition bg-white"
                      >
                        <div className="font-bold text-[#0B1F4B] flex justify-between">
                          <span>{a.start_time}</span>
                          <span className="text-[10px] text-slate-500 font-normal">
                            {a.duration_min || 20}m
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-600 truncate mt-0.5">
                          {a.practitioner_name}
                        </div>
                        <div dir="auto" className="font-semibold text-slate-800 truncate mt-1">
                          {a.patient_name}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Detailed List View */}
      {calendarView === "list" && (
        <div className="bg-white border border-[#E3E7EF] rounded-xl overflow-hidden shadow-xs">
          <div className="divide-y divide-[#E3E7EF]">
            {filteredAppointments.length === 0 ? (
              <div className="py-8 text-center text-[#64748B] text-xs">
                No appointments found for the selected criteria.
              </div>
            ) : (
              filteredAppointments.map((a) => (
                <div
                  key={a.id}
                  className="p-4 hover:bg-[#F9FBFC] transition flex items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="bg-[#E8F0FE] text-[#0B1F4B] border border-[#DCE7F9] font-bold text-xs px-2.5 py-1.5 rounded-lg text-center min-w-18">
                      {a.start_time}
                      <div className="text-[10px] font-normal text-slate-500">
                        {a.duration_min || 20}m
                      </div>
                    </div>
                    <div>
                      <div dir="auto" className="text-sm font-bold text-[#0B1F4B]">
                        {a.patient_name}
                      </div>
                      <div className="text-xs text-[#64748B] flex items-center gap-2 mt-0.5">
                        <span className="font-mono">{a.patient_phone}</span>
                        <span>•</span>
                        <span>{a.practitioner_name}</span>
                        <span>•</span>
                        <span>{a.room_name}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {a.arrival_number && (
                      <span className="bg-[#0F6059] text-white text-xs font-bold px-2.5 py-1 rounded-md">
                        Tour #{String(a.arrival_number).padStart(2, "0")}
                      </span>
                    )}
                    <button
                      onClick={() => onEditOrBook(a)}
                      className="px-3 py-1.5 border border-[#E3E7EF] text-slate-700 rounded-lg text-xs font-medium hover:bg-[#F4F6FA] cursor-pointer transition"
                    >
                      Edit / Move
                    </button>
                    <button
                      onClick={() => onCancelAppointment(a.id)}
                      className="px-3 py-1.5 border border-red-200 text-red-600 rounded-lg text-xs font-medium hover:bg-red-50 cursor-pointer transition"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
