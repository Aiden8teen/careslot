"use client";

import React, { useState } from "react";

interface WaitingListTabProps {
  apiBase: string;
  practitioners: any[];
  waitingList: any[];
  onRefresh: () => void;
  onBookFromWaitlist: (entry: any) => void;
}

export default function WaitingListTab({
  apiBase,
  practitioners,
  waitingList,
  onRefresh,
  onBookFromWaitlist,
}: WaitingListTabProps) {
  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [practitionerId, setPractitionerId] = useState<number>(practitioners[0]?.id || 1);
  const [preferredWindow, setPreferredWindow] = useState("ANY");
  const [urgency, setUrgency] = useState("NORMAL");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetch(`${apiBase}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_name: patientName,
          patient_phone: patientPhone,
          practitioner_id: practitionerId,
          preferred_window: preferredWindow,
          urgency,
          reason,
        }),
      });
      setPatientName("");
      setPatientPhone("");
      setReason("");
      onRefresh();
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    await fetch(`${apiBase}/api/waitlist/${id}`, { method: "DELETE" });
    onRefresh();
  };

  return (
    <div className="space-y-6">
      {/* Top Header Banner */}
      <div className="bg-white border border-[#E3E7EF] rounded-xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-[#0B1F4B]">Priority Waiting List</h2>
            <span className="bg-[#E8F0FE] text-[#0B1F4B] text-xs font-semibold px-2.5 py-0.5 rounded-full">
              {waitingList.length} In Queue
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1">
            Automated ranking and slot recovery when cancellations occur across all 10 clinic practitioners.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Form to Add to Waiting List (Left 4 cols) */}
        <div className="lg:col-span-4 bg-white border border-[#E3E7EF] rounded-xl p-5 shadow-xs space-y-4">
          <div>
            <h3 className="text-base font-bold text-[#0B1F4B]">Add to Waiting List</h3>
            <p className="text-xs text-[#64748B] mt-0.5">
              Patients will be queued and suggested first whenever an opening matches their criteria.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div>
              <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                Patient Full Name *
              </label>
              <input
                dir="auto"
                required
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                placeholder="Ex: Sarah Hadj / سارة حاج"
                className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                Algerian Mobile Phone *
              </label>
              <input
                required
                value={patientPhone}
                onChange={(e) => setPatientPhone(e.target.value)}
                placeholder="Ex: 0550 12 34 56"
                className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none font-mono transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                Requested Practitioner *
              </label>
              <select
                value={practitionerId}
                onChange={(e) => setPractitionerId(Number(e.target.value))}
                className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
              >
                {practitioners.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name_lat} ({p.specialty})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                  Preferred Shift
                </label>
                <select
                  value={preferredWindow}
                  onChange={(e) => setPreferredWindow(e.target.value)}
                  className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
                >
                  <option value="ANY">Any Time</option>
                  <option value="MORNING">Morning (08:30-12:30)</option>
                  <option value="AFTERNOON">Afternoon (13:30-17:00)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                  Urgency Level
                </label>
                <select
                  value={urgency}
                  onChange={(e) => setUrgency(e.target.value)}
                  className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
                >
                  <option value="NORMAL">Normal</option>
                  <option value="HIGH">High</option>
                  <option value="URGENT">Urgent</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                Medical Reason / Note
              </label>
              <input
                dir="auto"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Ex: Severe chest pain, post-op check"
                className="w-full bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 bg-[#0B1F4B] text-white rounded-lg text-xs font-semibold hover:bg-[#071533] cursor-pointer transition shadow-xs"
            >
              {submitting ? "Adding..." : "+ Add to Waiting List"}
            </button>
          </form>
        </div>

        {/* Waitlist Table (Right 8 cols) */}
        <div className="lg:col-span-8 bg-white border border-[#E3E7EF] rounded-xl overflow-hidden shadow-xs flex flex-col">
          <div className="p-4 bg-[#F4F6FA] border-b border-[#E3E7EF] flex items-center justify-between">
            <h3 className="text-sm font-bold text-[#0B1F4B]">Patients Awaiting Slot Recovery</h3>
            <span className="text-xs text-[#64748B]">Sorted by AI Priority Rating</span>
          </div>

          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F9FBFC] border-b border-[#E3E7EF] text-[#64748B] font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Patient</th>
                  <th className="py-3 px-4">Practitioner</th>
                  <th className="py-3 px-4 text-center">Urgency</th>
                  <th className="py-3 px-4">Availability</th>
                  <th className="py-3 px-4">Reason</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E3E7EF]">
                {waitingList.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-[#8C9BB0]">
                      No patients currently on the waiting list.
                    </td>
                  </tr>
                ) : (
                  waitingList.map((w) => {
                    const initials = w.patient_name
                      .split(" ")
                      .map((n: string) => n[0])
                      .join("")
                      .slice(0, 2)
                      .toUpperCase();

                    return (
                      <tr key={w.id} className="hover:bg-[#F9FBFC] transition">
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-full bg-[#E8F0FE] text-[#0B1F4B] font-bold text-[11px] flex items-center justify-center shrink-0 border border-[#DCE7F9]">
                              {initials || "PT"}
                            </div>
                            <div>
                              <div dir="auto" className="font-semibold text-slate-900">
                                {w.patient_name}
                              </div>
                              <div className="text-[11px] text-[#64748B] font-mono">
                                {w.patient_phone}
                              </div>
                            </div>
                          </div>
                        </td>

                        <td className="py-3.5 px-4">
                          <div className="font-medium text-slate-800">{w.practitioner_name}</div>
                        </td>

                        <td className="py-3.5 px-4 text-center">
                          {w.urgency === "URGENT" ? (
                            <span className="bg-red-50 text-red-700 border border-red-200 text-[10px] font-bold px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-red-600"></span>
                              Urgent
                            </span>
                          ) : w.urgency === "HIGH" ? (
                            <span className="bg-amber-50 text-amber-800 border border-amber-300 text-[10px] font-bold px-2 py-0.5 rounded-full">
                              High
                            </span>
                          ) : (
                            <span className="bg-slate-100 text-slate-700 border border-slate-200 text-[10px] font-medium px-2 py-0.5 rounded-full">
                              Normal
                            </span>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-slate-600">
                          <span className="bg-[#F4F6FA] border border-[#E3E7EF] px-2 py-0.5 rounded text-[11px] font-medium">
                            {w.preferred_window}
                          </span>
                        </td>

                        <td className="py-3.5 px-4 text-slate-600 italic max-w-xs truncate">
                          {w.reason || "—"}
                        </td>

                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => onBookFromWaitlist(w)}
                              className="px-3 py-1 bg-[#0F6059] text-white rounded-md text-[11px] font-semibold hover:bg-[#0c4e48] cursor-pointer transition shadow-2xs"
                            >
                              Book Slot
                            </button>
                            <button
                              onClick={() => handleDelete(w.id)}
                              className="px-2 py-1 text-red-600 hover:bg-red-50 rounded-md text-[11px] cursor-pointer transition"
                              title="Remove from waitlist"
                            >
                              ✕
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
