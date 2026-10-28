"use client";

import React, { useState } from "react";
import Image from "next/image";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (user: { role: "receptionist" | "doctor"; doctorId?: string; name: string }) => void;
  practitioners: any[];
}

export default function LoginModal({
  isOpen,
  onClose,
  onLoginSuccess,
  practitioners,
}: LoginModalProps) {
  const [selectedRole, setSelectedRole] = useState<"receptionist" | "doctor">("receptionist");
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>(
    practitioners.length > 0 ? String(practitioners[0].id) : "1"
  );
  const [email, setEmail] = useState<string>("leila.mansour@elchifa-clinic.dz");
  const [password, setPassword] = useState<string>("••••••••••••");

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedRole === "receptionist") {
      onLoginSuccess({
        role: "receptionist",
        name: "Leila Mansour",
      });
    } else {
      const doc = practitioners.find((p) => String(p.id) === String(selectedDoctorId));
      onLoginSuccess({
        role: "doctor",
        doctorId: selectedDoctorId,
        name: doc ? doc.full_name_lat : "Dr. Amine",
      });
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-4xl bg-white rounded-2xl shadow-2xl overflow-hidden grid grid-cols-1 md:grid-cols-2 border border-[#E3E7EF]">
        {/* Left Side: Hospital / Clinic Art Background from Figma */}
        <div className="relative hidden md:block min-h-[520px] bg-[#0B1F4B]">
          <Image
            src="/images/login-bg.png"
            alt="CareSlot Clinic"
            fill
            className="object-cover opacity-85"
            priority
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0B1F4B]/90 via-[#0B1F4B]/40 to-transparent flex flex-col justify-end p-8 text-white">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-md flex items-center justify-center font-bold text-lg mb-3">
              CS
            </div>
            <h2 className="text-2xl font-bold leading-tight">CareSlot Clinic OS</h2>
            <p className="text-xs text-white/80 mt-1 max-w-xs">
              AI-driven multi-practitioner scheduling, dynamic live room queues &amp; intelligent waitlist dispatching.
            </p>
            <div className="mt-4 pt-4 border-t border-white/20 flex items-center gap-3 text-[11px] text-white/70">
              <span>El-Chifa Clinic (الشفاء)</span>
              <span>•</span>
              <span>Algiers, DZ</span>
            </div>
          </div>
        </div>

        {/* Right Side: Sign-In Form */}
        <div className="p-8 md:p-10 flex flex-col justify-center">
          <div className="flex justify-between items-start mb-6">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <div className="relative w-10 h-10 rounded-xl bg-[#01B1A9]/10 border border-[#01B1A9]/20 p-1.5 flex items-center justify-center shrink-0 shadow-sm">
                  <Image
                    src="/images/careslot-icon.png"
                    alt="CareSlot Logo"
                    width={32}
                    height={32}
                    className="object-contain"
                  />
                </div>
                <div>
                  <div className="flex items-center gap-0.5 leading-none">
                    <span className="text-xl font-black tracking-tight text-[#0B1F4B] font-sans">Care</span>
                    <span className="text-xl font-black tracking-tight text-[#01B1A9] font-sans">Slot</span>
                  </div>
                  <span className="text-[10px] font-semibold text-[#01B1A9] uppercase tracking-wider">Clinical Workspace</span>
                </div>
              </div>
              <h1 className="text-xl font-bold text-[#0B1F4B]">Staff Portal Login</h1>
              <p className="text-xs text-[#64748B] mt-0.5">
                Select your role or enter credentials to access your terminal
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-[#8C9BB0] hover:text-[#0B1F4B] p-1.5 rounded-lg hover:bg-[#F4F6FA] text-sm cursor-pointer"
            >
              ✕
            </button>
          </div>

          {/* Quick Role Selection Tabs */}
          <div className="flex rounded-lg bg-[#F4F6FA] p-1 border border-[#E3E7EF] mb-5">
            <button
              type="button"
              onClick={() => {
                setSelectedRole("receptionist");
                setEmail("leila.mansour@elchifa-clinic.dz");
              }}
              className={`flex-1 py-2 text-xs font-semibold rounded-md transition cursor-pointer ${
                selectedRole === "receptionist"
                  ? "bg-[#0B1F4B] text-white shadow-xs"
                  : "text-[#64748B] hover:text-[#0B1F4B]"
              }`}
            >
              Receptionist
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedRole("doctor");
                setEmail("doctor@elchifa-clinic.dz");
              }}
              className={`flex-1 py-2 text-xs font-semibold rounded-md transition cursor-pointer ${
                selectedRole === "doctor"
                  ? "bg-[#0B1F4B] text-white shadow-xs"
                  : "text-[#64748B] hover:text-[#0B1F4B]"
              }`}
            >
              Doctor View
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            {selectedRole === "doctor" && (
              <div>
                <label className="block font-semibold text-[#0B1F4B] mb-1">
                  Practitioner Profile
                </label>
                <select
                  value={selectedDoctorId}
                  onChange={(e) => setSelectedDoctorId(e.target.value)}
                  className="w-full border border-[#E3E7EF] rounded-lg px-3 py-2 bg-white text-xs text-[#0B1F4B] font-medium focus:ring-1 focus:ring-[#0B1F4B] outline-none"
                >
                  {practitioners.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.full_name_lat} ({p.specialty} • {p.room_name})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block font-semibold text-[#0B1F4B] mb-1">Clinic Email / ID</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs bg-[#F4F6FA] focus:bg-white focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
              />
            </div>

            <div>
              <label className="block font-semibold text-[#0B1F4B] mb-1">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-[#E3E7EF] rounded-lg px-3 py-2 text-xs bg-[#F4F6FA] focus:bg-white focus:ring-1 focus:ring-[#0B1F4B] outline-none transition"
              />
            </div>

            <div className="flex items-center justify-between text-[11px] text-[#64748B]">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="checkbox" defaultChecked className="rounded border-[#E3E7EF]" />
                <span>Remember this terminal</span>
              </label>
              <span className="text-[#0B1F4B] hover:underline cursor-pointer">
                Forgot password?
              </span>
            </div>

            <button
              type="submit"
              className="w-full py-2.5 bg-[#0B1F4B] text-white rounded-lg font-semibold text-xs hover:bg-[#071533] cursor-pointer transition shadow-xs mt-2"
            >
              Sign In to CareSlot
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-[#E3E7EF] text-center text-[11px] text-[#8C9BB0]">
            CareSlot Health Systems • Secured with OAuth2 &amp; Role Guardrails
          </div>
        </div>
      </div>
    </div>
  );
}
