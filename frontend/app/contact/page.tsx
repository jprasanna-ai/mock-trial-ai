"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { User } from "@supabase/supabase-js";

const ScalesIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 100 100" fill="none">
    <defs>
      <linearGradient id="sg" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#fbbf24" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
    </defs>
    <rect x="35" y="85" width="30" height="8" rx="2" fill="url(#sg)" />
    <rect x="45" y="30" width="10" height="58" fill="url(#sg)" />
    <rect x="10" y="25" width="80" height="6" rx="2" fill="url(#sg)" />
    <circle cx="50" cy="20" r="8" fill="url(#sg)" />
  </svg>
);

type FormStatus = "idle" | "sending" | "sent" | "error";

export default function ContactPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<FormStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => setUser(data.user));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !message.trim()) return;

    setStatus("sending");
    setErrorMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), email: email.trim(), subject: subject.trim(), message: message.trim() }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to send message");
      }
      setStatus("sent");
      setName("");
      setEmail("");
      setSubject("");
      setMessage("");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-0">
          <div className="flex items-center justify-between h-16">
            <button onClick={() => router.push("/")} className="flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                <ScalesIcon className="w-5 h-5" />
              </div>
              <span className="text-base font-bold tracking-tight">MockPrep<span className="text-amber-400">AI</span></span>
            </button>
            <nav className="hidden md:flex items-center gap-1">
              <button onClick={() => router.push("/")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">{user ? "Dashboard" : "Home"}</button>
              {!user && <button onClick={() => router.push("/trials")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Recorded Trials</button>}
              <button onClick={() => router.push("/about")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Who We Are</button>
              <button className="px-4 py-2 text-sm font-medium text-white bg-slate-800/60 rounded-lg transition-colors">Contact</button>
            </nav>
            {user ? (
              <button onClick={() => router.push("/profile")} className="hidden sm:flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-xs font-bold hover:opacity-80 transition-opacity" title="Profile">{(user.email || "U")[0].toUpperCase()}</button>
            ) : (
              <button onClick={() => router.push("/login")} className="px-4 py-2 text-sm font-medium text-amber-400 border border-amber-500/30 hover:bg-amber-500/10 rounded-lg transition-colors">Sign In</button>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-12">
        <div className="grid md:grid-cols-5 gap-10">
          {/* Left — Info */}
          <div className="md:col-span-2 space-y-8">
            <div>
              <div className="text-xs text-amber-400 uppercase tracking-widest font-semibold mb-3">Get in Touch</div>
              <h1 className="text-3xl font-bold text-white mb-3">Contact Us</h1>
              <p className="text-slate-400 leading-relaxed">
                Have a question, suggestion, or want to partner with us?
                We&apos;d love to hear from you. Fill out the form and our team will get back to you shortly.
              </p>
            </div>

            <div className="space-y-5">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                  </svg>
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">Email</div>
                  <div className="text-sm text-slate-400">support@mockprepai.com</div>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">Response Time</div>
                  <div className="text-sm text-slate-400">We typically respond within 24 hours</div>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shrink-0">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
                  </svg>
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">FAQ</div>
                  <div className="text-sm text-slate-400">Check our <button onClick={() => router.push("/about")} className="text-amber-400 hover:underline">About</button> page for common questions</div>
                </div>
              </div>
            </div>
          </div>

          {/* Right — Form */}
          <div className="md:col-span-3">
            {status === "sent" ? (
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-10 text-center">
                <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-white mb-2">Message Sent!</h3>
                <p className="text-slate-400 mb-6">Thank you for reaching out. We&apos;ll get back to you soon.</p>
                <button onClick={() => setStatus("idle")} className="px-6 py-2.5 bg-slate-700/50 hover:bg-slate-600/50 text-slate-300 rounded-xl transition-colors text-sm">
                  Send Another Message
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 md:p-8 space-y-5">
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-slate-500 uppercase tracking-wider mb-1.5">Name *</label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                      placeholder="Your name"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 uppercase tracking-wider mb-1.5">Email *</label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                      placeholder="you@example.com"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-1.5">Subject</label>
                  <input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                    placeholder="What's this about?"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-1.5">Message *</label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    required
                    rows={6}
                    className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
                    placeholder="Tell us what you're thinking..."
                  />
                </div>

                {status === "error" && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 text-sm text-red-400">
                    {errorMsg || "Failed to send message. Please try again."}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={status === "sending" || !name.trim() || !email.trim() || !message.trim()}
                  className="w-full py-3 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-amber-500/20 disabled:shadow-none"
                >
                  {status === "sending" ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                      Sending...
                    </span>
                  ) : "Send Message"}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-slate-800/50 py-8 bg-slate-950/50 mt-16">
        <div className="max-w-5xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
              <ScalesIcon className="w-3.5 h-3.5" />
            </div>
            <span className="text-sm font-bold text-white">MockPrep<span className="text-amber-400">AI</span></span>
          </div>
          <div className="flex items-center gap-6 text-sm text-slate-500">
            <button onClick={() => router.push("/")} className="hover:text-slate-400 transition-colors">Dashboard</button>
            <button onClick={() => router.push("/about")} className="hover:text-slate-400 transition-colors">About</button>
            <button onClick={() => router.push("/contact")} className="hover:text-slate-400 transition-colors">Contact</button>
          </div>
          <p className="text-xs text-slate-600">AI-powered preparation for mock trial excellence.</p>
        </div>
      </footer>
    </div>
  );
}
