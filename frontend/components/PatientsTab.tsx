"use client";

import React, { useState, useEffect, useCallback } from "react";

interface PatientRecord {
  id: number;
  full_name: string;
  phone: string;
  appointments_count: number;
  last_appointment?: {
    id: number;
    date: string;
    time: string;
    practitioner_name: string;
    status: string;
  } | null;
  next_appointment?: {
    id: number;
    date: string;
    time: string;
    practitioner_name: string;
    status: string;
  } | null;
  created_at?: string;
}

interface PatientsTabProps {
  apiBase: string;
  onBookAppointmentForPatient: (patient: { name: string; phone: string }) => void;
}

export default function PatientsTab({
  apiBase,
  onBookAppointmentForPatient,
}: PatientsTabProps) {
  const [patients, setPatients] = useState<PatientRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newPatientName, setNewPatientName] = useState<string>("");
  const [newPatientPhone, setNewPatientPhone] = useState<string>("");
  const [addError, setAddError] = useState<string>("");
  const [selectedPatientHistory, setSelectedPatientHistory] = useState<PatientRecord | null>(null);

  const fetchPatients = useCallback(async () => {
    try {
      setLoading(true);
      const url = searchQuery
        ? `${apiBase}/api/patients?q=${encodeURIComponent(searchQuery)}`
        : `${apiBase}/api/patients`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setPatients(data);
      }
    } catch (err) {
      console.error("Failed to fetch patients:", err);
    } finally {
      setLoading(false);
    }
  }, [apiBase, searchQuery]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPatients();
    }, 200);
    return () => clearTimeout(timer);
  }, [fetchPatients]);

  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddError("");
    if (!newPatientName.trim() || !newPatientPhone.trim()) {
      setAddError("Please provide both name and phone number.");
      return;
    }

    try {
      // Create a dummy quick booking or direct patient entry via booking modal
      setShowAddModal(false);
      onBookAppointmentForPatient({
        name: newPatientName.trim(),
        phone: newPatientPhone.trim(),
      });
      setNewPatientName("");
      setNewPatientPhone("");
    } catch (err: any) {
      setAddError("Failed to add patient.");
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Banner / Toolbar matching Figma Receptionist / Patients */}
      <div className="bg-white border border-[#E3E7EF] rounded-xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-[#0B1F4B]">Patients Directory</h2>
            <span className="bg-[#E8F0FE] text-[#0B1F4B] text-xs font-semibold px-2.5 py-0.5 rounded-full">
              {patients.length} Registered
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1">
            Search patient records by Arabic/Latin name or Algerian mobile number (05/06/07).
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#8C9BB0]">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name in English or Arabic, or by phone..."
              className="pl-9 pr-4 py-2 text-xs border border-[#E3E7EF] rounded-lg w-72 md:w-80 bg-[#F4F6FA] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#0B1F4B] transition"
            />
          </div>

          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-[#0B1F4B] text-white rounded-lg text-xs font-semibold hover:bg-[#071533] cursor-pointer transition shadow-xs"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            <span>+ New Patient</span>
          </button>
        </div>
      </div>

      {/* Patient Table */}
      <div className="bg-white border border-[#E3E7EF] rounded-xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F4F6FA] border-b border-[#E3E7EF] text-[#64748B] font-semibold uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3.5 px-5">Patient Name</th>
                <th className="py-3.5 px-5">Phone Number</th>
                <th className="py-3.5 px-5 text-center">Visits</th>
                <th className="py-3.5 px-5">Last Visit</th>
                <th className="py-3.5 px-5">Next Scheduled</th>
                <th className="py-3.5 px-5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E3E7EF]">
              {loading && patients.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-[#64748B]">
                    Loading patient database...
                  </td>
                </tr>
              ) : patients.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-[#64748B]">
                    No patients found matching your search.
                  </td>
                </tr>
              ) : (
                patients.map((p) => {
                  const initials = p.full_name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase();

                  return (
                    <tr
                      key={p.id}
                      className="hover:bg-[#F9FBFC] transition group"
                    >
                      <td className="py-3.5 px-5">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-[#E8F0FE] text-[#0B1F4B] font-bold flex items-center justify-center text-xs shrink-0 border border-[#DCE7F9]">
                            {initials || "PT"}
                          </div>
                          <div>
                            <div dir="auto" className="font-semibold text-sm text-[#0B1F4B]">
                              {p.full_name}
                            </div>
                            <div className="text-[10px] text-[#8C9BB0]">Patient ID #{p.id}</div>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-5 font-mono text-slate-700 font-medium">
                        {p.phone}
                      </td>

                      <td className="py-3.5 px-5 text-center">
                        <span className="inline-block bg-[#F4F6FA] border border-[#E3E7EF] text-[#0B1F4B] font-bold px-2 py-0.5 rounded text-[11px]">
                          {p.appointments_count}
                        </span>
                      </td>

                      <td className="py-3.5 px-5">
                        {p.last_appointment ? (
                          <div>
                            <div className="font-medium text-slate-700">
                              {p.last_appointment.date} at {p.last_appointment.time}
                            </div>
                            <div className="text-[10px] text-[#64748B]">
                              {p.last_appointment.practitioner_name}
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-400 italic">No past visits</span>
                        )}
                      </td>

                      <td className="py-3.5 px-5">
                        {p.next_appointment ? (
                          <div className="inline-flex items-center gap-1.5 bg-[#E8F5E9] text-[#1B5E20] px-2.5 py-1 rounded-md text-[11px] font-semibold border border-[#C8E6C9]">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                            <span>{p.next_appointment.date} ({p.next_appointment.time})</span>
                          </div>
                        ) : (
                          <span className="text-slate-400 italic">None booked</span>
                        )}
                      </td>

                      <td className="py-3.5 px-5 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() =>
                              onBookAppointmentForPatient({
                                name: p.full_name,
                                phone: p.phone,
                              })
                            }
                            className="px-3 py-1.5 bg-[#0B1F4B] text-white rounded-md text-[11px] font-semibold hover:bg-[#071533] cursor-pointer transition"
                          >
                            + Book
                          </button>
                          <button
                            onClick={() => setSelectedPatientHistory(p)}
                            className="px-2.5 py-1.5 border border-[#E3E7EF] text-[#64748B] hover:text-[#0B1F4B] hover:bg-[#F4F6FA] rounded-md text-[11px] font-medium cursor-pointer transition"
                            title="View Patient Details"
                          >
                            Details
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

      {/* Quick Add Patient Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#E3E7EF] rounded-xl max-w-md w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E3E7EF] pb-3">
              <h3 className="text-base font-bold text-[#0B1F4B]">Register New Patient</h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-[#8C9BB0] hover:text-[#0B1F4B] text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            {addError && (
              <div className="p-2.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                {addError}
              </div>
            )}

            <form onSubmit={handleCreatePatient} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                  Full Name (Arabic or Latin) *
                </label>
                <input
                  dir="auto"
                  required
                  value={newPatientName}
                  onChange={(e) => setNewPatientName(e.target.value)}
                  placeholder="Ex: Fatima Zohra Khelil / فاطمة خليل"
                  className="w-full border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#0B1F4B] mb-1">
                  Algerian Mobile Phone (05/06/07...) *
                </label>
                <input
                  required
                  value={newPatientPhone}
                  onChange={(e) => setNewPatientPhone(e.target.value)}
                  placeholder="Ex: 0550 12 34 56"
                  className="w-full border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[#E3E7EF]">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-[#E3E7EF] text-slate-700 rounded-lg text-xs font-semibold hover:bg-[#F4F6FA] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-[#0B1F4B] text-white rounded-lg text-xs font-semibold hover:bg-[#071533] cursor-pointer"
                >
                  Continue to Booking
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Patient History / Details Modal */}
      {selectedPatientHistory && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#E3E7EF] rounded-xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E3E7EF] pb-3">
              <div>
                <h3 dir="auto" className="text-base font-bold text-[#0B1F4B]">
                  {selectedPatientHistory.full_name}
                </h3>
                <p className="text-xs text-[#64748B]">Phone: {selectedPatientHistory.phone}</p>
              </div>
              <button
                onClick={() => setSelectedPatientHistory(null)}
                className="text-[#8C9BB0] hover:text-[#0B1F4B] text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-[#F4F6FA] p-3 rounded-lg border border-[#E3E7EF]">
                <div className="text-[10px] text-[#64748B] uppercase font-bold">Total Appointments</div>
                <div className="text-xl font-bold text-[#0B1F4B] mt-1">
                  {selectedPatientHistory.appointments_count}
                </div>
              </div>

              <div className="bg-[#F4F6FA] p-3 rounded-lg border border-[#E3E7EF]">
                <div className="text-[10px] text-[#64748B] uppercase font-bold">Status</div>
                <div className="text-xs font-semibold text-emerald-700 mt-2">
                  Active Patient Record
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-xs font-bold text-[#0B1F4B]">Appointments Summary</h4>
              <div className="border border-[#E3E7EF] rounded-lg p-3 space-y-2 text-xs bg-[#F9FBFC]">
                {selectedPatientHistory.next_appointment ? (
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-emerald-800">Next Scheduled Visit:</div>
                      <div className="text-slate-600">
                        {selectedPatientHistory.next_appointment.date} at {selectedPatientHistory.next_appointment.time} (
                        {selectedPatientHistory.next_appointment.practitioner_name})
                      </div>
                    </div>
                    <span className="bg-[#E8F5E9] text-[#1B5E20] text-[10px] font-bold px-2 py-0.5 rounded">
                      Upcoming
                    </span>
                  </div>
                ) : (
                  <div className="text-slate-500 italic">No upcoming appointments.</div>
                )}

                {selectedPatientHistory.last_appointment && (
                  <div className="pt-2 border-t border-[#E3E7EF]">
                    <div className="font-semibold text-slate-700">Last Recorded Visit:</div>
                    <div className="text-slate-600">
                      {selectedPatientHistory.last_appointment.date} at {selectedPatientHistory.last_appointment.time} (
                      {selectedPatientHistory.last_appointment.practitioner_name})
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-between items-center pt-3 border-t border-[#E3E7EF]">
              <button
                onClick={() => setSelectedPatientHistory(null)}
                className="px-4 py-2 border border-[#E3E7EF] text-slate-700 rounded-lg text-xs font-semibold hover:bg-[#F4F6FA] cursor-pointer"
              >
                Close
              </button>
              <button
                onClick={() => {
                  const pt = selectedPatientHistory;
                  setSelectedPatientHistory(null);
                  onBookAppointmentForPatient({ name: pt.full_name, phone: pt.phone });
                }}
                className="px-5 py-2 bg-[#0B1F4B] text-white rounded-lg text-xs font-semibold hover:bg-[#071533] cursor-pointer"
              >
                + Book New Slot
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
