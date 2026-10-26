import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareSlot — AI Scheduling & Queue Platform for Algerian Clinics",
  description:
    "CareSlot replaces paper agendas with centralized multi-doctor scheduling, live arrival numbering (Tour), and LangGraph + Gemini 2.0 Flash AI assistance.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-white text-[#021422] antialiased">
        {children}
      </body>
    </html>
  );
}
