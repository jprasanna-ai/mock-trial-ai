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
  title: "AI Mock Trial",
  description: "Practice mock trial skills with AI-powered attorneys, witnesses, and judges",
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
