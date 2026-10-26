"use client";

import React, { useState } from "react";

interface DoctorsRoomsTabProps {
  apiBase: string;
  practitioners: any[];
  rooms: any[];
  onRefresh: () => void;
}

export default function DoctorsRoomsTab({
  apiBase,
  practitioners,
  rooms,
  onRefresh,
}: DoctorsRoomsTabProps) {
  const [newRoomName, setNewRoomName] = useState("");
  const [newRoomFloor, setNewRoomFloor] = useState("RDC");
  const [edits, setEdits] = useState<Record<number, any>>({});
  const [roomEdits, setRoomEdits] = useState<Record<number, string>>({});
  const [savingDocId, setSavingDocId] = useState<number | null>(null);

  const updateDocField = (id: number, field: string, val: any) => {
    setEdits((prev) => ({
      ...prev,
      [id]: { ...(prev[id] || {}), [field]: val },
    }));
  };

  const saveDoctor = async (doc: any) => {
    setSavingDocId(doc.id);
    try {
      const patch = edits[doc.id] || {};
      await fetch(`${apiBase}/api/practitioners/${doc.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name_lat: patch.full_name_lat ?? doc.full_name_lat,
          full_name_ar: patch.full_name_ar ?? doc.full_name_ar,
          current_room_id: Number(patch.room_id ?? doc.room_id),
          max_daily_appointments: Number(patch.max_daily_appointments ?? doc.max_daily_appointments),
        }),
      });
      onRefresh();
    } finally {
      setSavingDocId(null);
    }
  };

  const handleAddRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRoomName.trim()) return;
    await fetch(`${apiBase}/api/rooms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newRoomName, floor: newRoomFloor }),
    });
    setNewRoomName("");
    onRefresh();
  };

  const handleRenameRoom = async (room: any) => {
    const updatedName = roomEdits[room.id] ?? room.name;
    await fetch(`${apiBase}/api/rooms/${room.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: updatedName }),
    });
    onRefresh();
  };

  const handleDeleteRoom = async (id: number) => {
    if (!confirm("Are you sure you want to remove this consultation room?")) return;
    await fetch(`${apiBase}/api/rooms/${id}`, { method: "DELETE" });
    onRefresh();
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white border border-[#E3E7EF] rounded-xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-[#0B1F4B]">Practitioners &amp; Rooms Management</h2>
            <span className="bg-[#E8F0FE] text-[#0B1F4B] text-xs font-semibold px-2.5 py-0.5 rounded-full">
              {practitioners.length} Doctors • {rooms.length} Rooms
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1">
            Configure practitioner shifts, consultation room assignments, bilingual names, and daily booking caps.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* 10 Editable Practitioners (8 cols) */}
        <div className="lg:col-span-8 bg-white border border-[#E3E7EF] rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-[#0B1F4B]">Clinic Practitioners ({practitioners.length})</h3>
            <span className="text-xs text-[#64748B]">Inline editable settings</span>
          </div>

          <div className="space-y-3">
            {practitioners.map((d) => {
              const currentPatch = edits[d.id] || {};
              const isSaving = savingDocId === d.id;

              return (
                <div
                  key={d.id}
                  className="border border-[#E3E7EF] rounded-xl p-4 bg-[#F9FBFC] hover:bg-white transition grid grid-cols-1 md:grid-cols-12 gap-3 items-center"
                >
                  <div className="md:col-span-4">
                    <label className="text-[10px] uppercase font-bold text-[#64748B] block mb-1">
                      Latin Full Name
                    </label>
                    <input
                      value={currentPatch.full_name_lat ?? d.full_name_lat}
                      onChange={(e) => updateDocField(d.id, "full_name_lat", e.target.value)}
                      className="w-full bg-white border border-[#E3E7EF] rounded-lg px-2.5 py-1.5 text-xs font-semibold text-[#0B1F4B] focus:ring-1 focus:ring-[#0B1F4B] outline-none"
                    />
                    <div className="text-[10px] text-[#8C9BB0] mt-1">{d.specialty}</div>
                  </div>

                  <div className="md:col-span-3">
                    <label className="text-[10px] uppercase font-bold text-[#64748B] block mb-1">
                      Arabic Name
                    </label>
                    <input
                      dir="auto"
                      value={currentPatch.full_name_ar ?? d.full_name_ar}
                      onChange={(e) => updateDocField(d.id, "full_name_ar", e.target.value)}
                      className="w-full bg-white border border-[#E3E7EF] rounded-lg px-2.5 py-1.5 text-xs text-[#0B1F4B] focus:ring-1 focus:ring-[#0B1F4B] outline-none"
                    />
                  </div>

                  <div className="md:col-span-3">
                    <label className="text-[10px] uppercase font-bold text-[#64748B] block mb-1">
                      Assigned Room
                    </label>
                    <select
                      value={currentPatch.room_id ?? d.room_id ?? ""}
                      onChange={(e) => updateDocField(d.id, "room_id", Number(e.target.value))}
                      className="w-full bg-white border border-[#E3E7EF] rounded-lg px-2 py-1.5 text-xs font-medium text-slate-800 focus:ring-1 focus:ring-[#0B1F4B] outline-none cursor-pointer"
                    >
                      {rooms.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} ({r.floor})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="md:col-span-1">
                    <label className="text-[10px] uppercase font-bold text-[#64748B] block mb-1 text-center">
                      Daily Cap
                    </label>
                    <input
                      type="number"
                      value={currentPatch.max_daily_appointments ?? d.max_daily_appointments}
                      onChange={(e) => updateDocField(d.id, "max_daily_appointments", e.target.value)}
                      className="w-full bg-white border border-[#E3E7EF] rounded-lg px-1.5 py-1.5 text-xs text-center font-bold text-[#0B1F4B] focus:ring-1 focus:ring-[#0B1F4B] outline-none"
                    />
                  </div>

                  <div className="md:col-span-1 flex items-end">
                    <button
                      onClick={() => saveDoctor(d)}
                      disabled={isSaving}
                      className="w-full py-1.5 bg-[#0B1F4B] text-white rounded-lg text-xs font-semibold hover:bg-[#071533] cursor-pointer transition shadow-2xs"
                    >
                      {isSaving ? "..." : "Save"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Consultation Rooms (4 cols) */}
        <div className="lg:col-span-4 bg-white border border-[#E3E7EF] rounded-xl p-5 shadow-xs space-y-4">
          <div>
            <h3 className="text-base font-bold text-[#0B1F4B]">Consultation Rooms ({rooms.length})</h3>
            <p className="text-xs text-[#64748B] mt-0.5">Physical consultation suites</p>
          </div>

          <form onSubmit={handleAddRoom} className="flex gap-2">
            <input
              required
              value={newRoomName}
              onChange={(e) => setNewRoomName(e.target.value)}
              placeholder="Ex: Salle 7 - ECG"
              className="flex-1 bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-3 py-1.5 text-xs focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
            />
            <input
              value={newRoomFloor}
              onChange={(e) => setNewRoomFloor(e.target.value)}
              placeholder="Floor"
              className="w-16 bg-[#F4F6FA] focus:bg-white border border-[#E3E7EF] rounded-lg px-2 py-1.5 text-xs text-center focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
            />
            <button
              type="submit"
              className="px-3 py-1.5 bg-[#0B1F4B] text-white rounded-lg text-xs font-semibold hover:bg-[#071533] cursor-pointer transition shadow-2xs"
            >
              + Add
            </button>
          </form>

          <div className="space-y-2">
            {rooms.map((r) => {
              const assignedDocs = practitioners.filter((p) => p.room_id === r.id);
              return (
                <div
                  key={r.id}
                  className="bg-[#F9FBFC] border border-[#E3E7EF] rounded-lg p-3 space-y-2"
                >
                  <div className="flex items-center gap-2">
                    <input
                      value={roomEdits[r.id] ?? r.name}
                      onChange={(e) => setRoomEdits((prev) => ({ ...prev, [r.id]: e.target.value }))}
                      className="flex-1 bg-white border border-[#E3E7EF] rounded px-2.5 py-1 text-xs font-semibold text-[#0B1F4B]"
                    />
                    <button
                      onClick={() => handleRenameRoom(r)}
                      className="px-2 py-1 bg-[#0B1F4B] text-white rounded text-[11px] font-semibold hover:bg-[#071533] cursor-pointer transition"
                    >
                      Update
                    </button>
                    <button
                      onClick={() => handleDeleteRoom(r.id)}
                      className="px-2 py-1 text-red-600 hover:bg-red-50 rounded text-[11px] cursor-pointer transition"
                      title="Remove room"
                    >
                      ✕
                    </button>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-[#64748B]">
                    <span>Floor: {r.floor}</span>
                    <span>
                      {assignedDocs.length > 0 ? (
                        <span className="text-[#0F6059] font-semibold">
                          {assignedDocs.map((doc) => doc.full_name_lat.split(" ")[1] || doc.full_name_lat).join(", ")}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic">No doctor assigned</span>
                      )}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
