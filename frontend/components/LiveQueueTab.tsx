"use client";

import React from "react";

interface LiveQueueTabProps {
  practitioners: any[];
  appointments: any[];
  selectedDoctorId?: string;
  role?: "receptionist" | "doctor";
  onReorderArrival: (id: number, currentNum: number) => void;
  onToggleFinished: (id: number) => void;
}

function calculateEstimatedTime(timeStr: string, delayMin: number): string {
  if (!timeStr || !delayMin || delayMin <= 5) return timeStr;
  const [h, m] = timeStr.split(":").map(Number);
  const total = h * 60 + m + delayMin;
  const newH = Math.floor(total / 60) % 24;
  const newM = total % 60;
  return `${String(newH).padStart(2, "0")}:${String(newM).padStart(2, "0")}`;
}

export default function LiveQueueTab({
  practitioners,
  appointments,
  selectedDoctorId,
  role = "receptionist",
  onReorderArrival,
  onToggleFinished,
}: LiveQueueTabProps) {
  const displayedPractitioners =
    role === "doctor" && selectedDoctorId
      ? practitioners.filter((d) => String(d.id) === String(selectedDoctorId))
      : practitioners;

  const totalWaiting = appointments.filter(
    (a) => a.arrival_number && a.status !== "FINISHED" && a.status !== "CANCELLED"
  ).length;

  return (
    <div className="space-y-6">
      {/* Top Header matching Figma Receptionist / Waiting Room */}
      <div className="bg-white border border-[#E3E7EF] rounded-xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-[#0B1F4B]">
              {role === "doctor" && displayedPractitioners[0]
                ? `In-Room Queue: ${displayedPractitioners[0].full_name_lat}`
                : "Waiting Room & Arrival Queue"}
            </h2>
            <span className="bg-[#E8F0FE] text-[#0B1F4B] text-xs font-semibold px-2.5 py-0.5 rounded-full">
              {totalWaiting} Patients in Lounge
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1">
            Real-time Numéro de Tour sequence with dynamic delay propagation and in-consultation tracking.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {role === "doctor" ? (
            <span className="bg-amber-50 border border-amber-300 text-amber-900 px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-500"></span>
              Doctor Queue View
            </span>
          ) : (
            <span className="bg-[#E8F5E9] border border-[#C8E6C9] text-[#1B5E20] px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse"></span>
              Live Sync Active
            </span>
          )}
        </div>
      </div>

      {/* Practitioner Queue Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {displayedPractitioners.map((doc) => {
          const docQueue = appointments
            .filter((a) => a.practitioner_id === doc.id && a.arrival_number && a.status !== "CANCELLED")
            .sort((a, b) => (a.arrival_number || 0) - (b.arrival_number || 0));

          const activePatients = docQueue.filter((a) => a.status !== "FINISHED");
          const inConsultation = activePatients[0];
          const waitingQueue = activePatients.slice(1);
          const finishedPatients = docQueue.filter((a) => a.status === "FINISHED");

          return (
            <div
              key={doc.id}
              className="bg-white border border-[#E3E7EF] rounded-xl shadow-xs overflow-hidden flex flex-col"
            >
              {/* Doctor Header */}
              <div className="p-4 bg-[#F4F6FA] border-b border-[#E3E7EF] flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-bold text-[#0B1F4B]">{doc.full_name_lat}</h3>
                    {doc.delay_status === "HEAVY" ? (
                      <span className="bg-red-50 text-red-700 border border-red-200 text-[10px] font-bold px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-600 animate-pulse"></span>
                        +{doc.running_delay_min}m retard
                      </span>
                    ) : doc.delay_status === "MODERATE" ? (
                      <span className="bg-amber-50 text-amber-800 border border-amber-300 text-[10px] font-bold px-2 py-0.5 rounded-full">
                        +{doc.running_delay_min}m retard
                      </span>
                    ) : (
                      <span className="bg-[#E8F5E9] text-[#1B5E20] border border-[#C8E6C9] text-[10px] font-bold px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600"></span>
                        À l'heure
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    {doc.specialty} • {doc.room_name}
                  </p>
                </div>

                <div className="text-right">
                  <span className="inline-block bg-[#0B1F4B] text-white text-xs font-bold px-2.5 py-1 rounded-md">
                    {activePatients.length} Active
                  </span>
                </div>
              </div>

              {/* Patient Queue Content */}
              <div className="p-4 space-y-3.5 flex-1 bg-white">
                {/* Active in-consultation card (Large Highlighted Card) */}
                {inConsultation ? (
                  <div className="border-2 border-[#0F6059] bg-[#F0FDF4] rounded-xl p-3.5 shadow-2xs">
                    <div className="flex items-center justify-between mb-2">
                      <span className="inline-flex items-center gap-1.5 bg-[#0F6059] text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                        <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping"></span>
                        In Consultation • في الفحص
                      </span>
                      <span className="font-mono text-xs font-bold text-[#0F6059]">
                        Tour #{String(inConsultation.arrival_number).padStart(2, "0")}
                      </span>
                    </div>

                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div dir="auto" className="text-base font-bold text-[#0B1F4B]">
                          {inConsultation.patient_name}
                        </div>
                        <div className="text-xs text-[#64748B] font-mono mt-0.5">
                          {inConsultation.patient_phone}
                        </div>
                        <div className="flex items-center gap-2 mt-2 text-xs">
                          <span className="text-slate-600">Slot: {inConsultation.start_time}</span>
                          <span className="text-slate-400">•</span>
                          <span className="font-semibold text-[#0F6059]">
                            {inConsultation.duration_min || 20}m
                          </span>
                        </div>
                      </div>

                      <div className="flex flex-col items-end gap-1.5">
                        <button
                          onClick={() => onToggleFinished(inConsultation.id)}
                          className="px-3 py-1.5 bg-[#0F6059] text-white rounded-lg text-xs font-semibold hover:bg-[#0c4e48] cursor-pointer transition shadow-xs flex items-center gap-1"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                          </svg>
                          <span>Finished</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="border border-dashed border-[#E3E7EF] rounded-xl p-4 text-center bg-[#F4F6FA]/50">
                    <div className="text-xs font-semibold text-[#64748B]">Consultation Room Ready</div>
                    <div className="text-[11px] text-[#8C9BB0] mt-0.5">Waiting for next arrived patient</div>
                  </div>
                )}

                {/* Up Next Queue */}
                {waitingQueue.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-[#64748B]">
                      Up Next in Queue ({waitingQueue.length})
                    </div>
                    {waitingQueue.map((a, idx) => (
                      <div
                        key={a.id}
                        className="border border-[#E3E7EF] rounded-lg p-2.5 bg-[#F9FBFC] hover:bg-white transition flex items-center justify-between"
                      >
                        <div className="flex items-center gap-3">
                          <span className="w-7 h-7 rounded-lg bg-[#E8F0FE] text-[#0B1F4B] font-bold text-xs flex items-center justify-center shrink-0 border border-[#DCE7F9]">
                            {String(a.arrival_number).padStart(2, "0")}
                          </span>
                          <div>
                            <div className="flex items-center gap-2">
                              <span dir="auto" className="text-xs font-bold text-[#0B1F4B]">
                                {a.patient_name}
                              </span>
                              {idx === 0 ? (
                                <span className="bg-amber-100 text-amber-800 text-[10px] font-bold px-1.5 py-0.2 rounded">
                                  Next
                                </span>
                              ) : (
                                <span className="bg-slate-100 text-slate-600 text-[10px] font-medium px-1.5 py-0.2 rounded">
                                  Waiting
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-[#64748B] flex items-center gap-2 mt-0.5">
                              <span>Slot: {a.start_time}</span>
                              {doc.running_delay_min > 5 && (
                                <span className="text-amber-800 font-medium">
                                  (Est: {calculateEstimatedTime(a.start_time, doc.running_delay_min)})
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => onReorderArrival(a.id, a.arrival_number)}
                            className="px-2 py-1 border border-[#E3E7EF] text-slate-700 rounded text-[11px] hover:bg-[#F4F6FA] cursor-pointer transition"
                            title="Reorder arrival number"
                          >
                            # Reorder
                          </button>
                          <button
                            onClick={() => onToggleFinished(a.id)}
                            className="px-2.5 py-1 border border-[#0F6059] text-[#0F6059] rounded text-[11px] font-semibold hover:bg-[#0F6059] hover:text-white cursor-pointer transition"
                          >
                            Done
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Completed consultations for this doctor today */}
                {finishedPatients.length > 0 && (
                  <div className="pt-2 border-t border-[#E3E7EF]">
                    <div className="text-[10px] font-semibold text-slate-400 mb-1">
                      Completed Today ({finishedPatients.length})
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {finishedPatients.map((f) => (
                        <span
                          key={f.id}
                          className="bg-slate-100 text-slate-500 line-through text-[10px] px-2 py-0.5 rounded border border-slate-200"
                        >
                          Tour #{String(f.arrival_number).padStart(2, "0")} • {f.patient_name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {docQueue.length === 0 && (
                  <div className="py-8 text-center text-xs text-[#8C9BB0]">
                    No patients have checked in with arrival numbers yet.
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
