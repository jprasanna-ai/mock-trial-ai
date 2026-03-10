"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";

interface RecordedTrial {
  session_id: string;
  case_name: string;
  case_id: string;
  human_role: string;
  started_at: string;
  updated_at: string;
  entry_count: number;
  phases_completed: string[];
}

const ROLE_LABELS: Record<string, string> = {
  attorney_plaintiff: "Plaintiff Attorney",
  attorney_defense: "Defense Attorney",
  witness: "Witness",
  spectator: "Spectator",
};

const ScalesIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 100 100" fill="none">
    <defs><linearGradient id="sg" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stopColor="#fbbf24" /><stop offset="100%" stopColor="#b45309" /></linearGradient></defs>
    <rect x="35" y="85" width="30" height="8" rx="2" fill="url(#sg)" /><rect x="45" y="30" width="10" height="58" fill="url(#sg)" /><rect x="10" y="25" width="80" height="6" rx="2" fill="url(#sg)" /><circle cx="50" cy="20" r="8" fill="url(#sg)" />
  </svg>
);

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

export default function RecordedTrialsPage() {
  const router = useRouter();
  const [trials, setTrials] = useState<RecordedTrial[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/trial/transcripts/public`)
      .then((r) => (r.ok ? r.json() : { transcripts: [] }))
      .then((data) => setTrials(data.transcripts || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
              <button onClick={() => router.push("/")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Home</button>
              <button className="px-4 py-2 text-sm font-medium text-white bg-slate-800/60 rounded-lg transition-colors">Recorded Trials</button>
              <button onClick={() => router.push("/about")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Who We Are</button>
              <button onClick={() => router.push("/contact")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Contact</button>
            </nav>
            <div className="flex items-center gap-2">
              <button onClick={() => router.push("/login")} className="px-4 py-2 text-sm font-medium bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-white rounded-lg transition-all shadow-lg shadow-amber-500/20">Try It Out</button>
              <button onClick={() => router.push("/login")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white border border-slate-700/50 hover:border-slate-600 rounded-lg transition-colors">Sign In</button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-10">
        {/* Page header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-purple-500/10 border border-purple-500/20 rounded-full text-purple-400 text-xs font-semibold mb-4">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" /></svg>
            RECORDED TRIALS
          </div>
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-3">Watch AI Mock Trials</h1>
          <p className="text-slate-400 max-w-2xl mx-auto">Browse completed trial simulations. Read full transcripts or listen to AI-generated audio to experience how attorneys argue, examine witnesses, and how judges score performances.</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-500">
            <svg className="animate-spin w-6 h-6 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
            Loading trials...
          </div>
        ) : trials.length === 0 ? (
          <div className="text-center py-20">
            <svg className="w-16 h-16 mx-auto text-slate-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}><path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" /></svg>
            <p className="text-slate-400 text-lg mb-2">No recorded trials available yet</p>
            <p className="text-slate-500 text-sm mb-6">Completed trials will appear here for public viewing.</p>
            <button onClick={() => router.push("/login")} className="px-6 py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg transition-colors">Try It Yourself</button>
          </div>
        ) : (
          <div className="space-y-4">
            {trials.map((trial) => (
              <button
                key={trial.session_id}
                onClick={() => router.push(`/trials/${trial.session_id}`)}
                className="w-full bg-slate-800/50 border border-slate-700/50 rounded-xl px-6 py-5 flex items-center justify-between hover:bg-slate-700/30 transition-colors text-left group"
              >
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-semibold text-white mb-1 group-hover:text-amber-300 transition-colors">{trial.case_name}</h3>
                  <div className="flex items-center gap-4 text-sm text-slate-500">
                    <span>{formatDate(trial.started_at)}</span>
                    <span className="px-2 py-0.5 rounded-full bg-slate-700/50 text-slate-400 text-xs">{ROLE_LABELS[trial.human_role] || trial.human_role}</span>
                    <span>{trial.entry_count} exchanges</span>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-medium rounded-lg">Completed</span>
                  <svg className="w-5 h-5 text-slate-500 group-hover:text-white transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* CTA */}
        <div className="mt-16 text-center">
          <div className="bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-amber-500/10 border border-amber-500/15 rounded-2xl p-8">
            <h2 className="text-xl font-bold text-white mb-2">Want to Run Your Own Trial?</h2>
            <p className="text-slate-400 text-sm mb-5">Sign up and experience AI-powered mock trial preparation firsthand.</p>
            <button onClick={() => router.push("/login")} className="px-6 py-3 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-amber-500/20">Get Started Free</button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-slate-800/50 py-8 bg-slate-950/50 mt-8">
        <div className="max-w-5xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center"><ScalesIcon className="w-3.5 h-3.5" /></div>
            <span className="text-sm font-bold text-white">MockPrep<span className="text-amber-400">AI</span></span>
          </div>
          <div className="flex items-center gap-6 text-sm text-slate-500">
            <button onClick={() => router.push("/")} className="hover:text-slate-400 transition-colors">Home</button>
            <button onClick={() => router.push("/about")} className="hover:text-slate-400 transition-colors">About</button>
            <button onClick={() => router.push("/contact")} className="hover:text-slate-400 transition-colors">Contact</button>
          </div>
          <p className="text-xs text-slate-600">AI-powered preparation for mock trial excellence.</p>
        </div>
      </footer>
    </div>
  );
}
