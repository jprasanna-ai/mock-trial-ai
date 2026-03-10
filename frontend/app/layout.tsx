/**
 * Root Layout
 * 
 * Per ARCHITECTURE.md Section 1:
 * - Frontend responsible for audio capture, playback, UI rendering
 * - All styling and layout is handled by the frontend
 */

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MockPrep AI — Mock Trial Preparation Platform",
  description: "AI-powered mock trial preparation platform. Practice openings, direct & cross examinations, and closings with intelligent AI opponents. Get scored by AI judges and sharpen your advocacy skills.",
  icons: {
    icon: "/icon.svg",
    apple: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
