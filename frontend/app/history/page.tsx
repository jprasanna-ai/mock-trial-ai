"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, API_BASE } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

interface TranscriptHistoryItem {
  id: string;
  session_id: string;
  case_name: string;
  case_id: string;
  human_role: string;
  started_at: string;
  updated_at: string;
  entry_count: number;
  phases_completed: string[];
}

interface TranscriptDetail {
  session_id: string;
  case_name: string;
  human_role: string;
  entry_count: number;
  transcript: {
    speaker: string;
    role: string;
    text: string;
    phase: string;
    event_type?: string;
  }[];
}

const ROLE_LABELS: Record<string, string> = {
  attorney_plaintiff: "Plaintiff Attorney",
  attorney_defense: "Defense Attorney",
  witness: "Witness",
  spectator: "Spectator",
  judge: "Judge",
  system: "Court Clerk",
};

const ROLE_COLORS: Record<string, string> = {
  attorney_plaintiff: "text-blue-400",
  attorney_defense: "text-red-400",
  witness: "text-amber-400",
  judge: "text-purple-400",
  system: "text-slate-400",
};

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function HistoryPage() {
  const router = useRouter();
  const [userInitial, setUserInitial] = useState("U");
  const [authReady, setAuthReady] = useState(false);
  const [items, setItems] = useState<TranscriptHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [transcriptData, setTranscriptData] = useState<Record<string, TranscriptDetail>>({});
  const [loadingTranscript, setLoadingTranscript] = useState<string | null>(null);

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => {
      if (data.user?.email) setUserInitial(data.user.email[0].toUpperCase());
      setAuthReady(true);
    });
  }, []);

  useEffect(() => {
    if (!authReady) return;
    apiFetch(`${API_BASE}/api/trial/transcripts/history`)
      .then((r) => r.json())
      .then((data) => setItems(data.transcripts || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [authReady]);

  const toggleExpand = async (sessionId: string) => {
    if (expandedId === sessionId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(sessionId);
    if (!transcriptData[sessionId]) {
      setLoadingTranscript(sessionId);
      try {
        const res = await apiFetch(`${API_BASE}/api/trial/transcripts/${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          setTranscriptData((prev) => ({ ...prev, [sessionId]: data }));
        }
      } catch { /* ignore */ }
      setLoadingTranscript(null);
    }
  };

  const grouped = items.reduce<Record<string, TranscriptHistoryItem[]>>((acc, item) => {
    const key = item.case_name || "Unknown Case";
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-0">
          <div className="flex items-center justify-between h-16">
            <button onClick={() => router.push("/")} className="flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="white" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0012 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 01-2.031.352 5.988 5.988 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.971zm-16.5.52c.99-.203 1.99-.377 3-.52m0 0l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 01-2.031.352 5.989 5.989 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 4.971z" />
                </svg>
              </div>
              <div className="flex flex-col leading-tight">
                <span className="text-base font-bold tracking-tight">MockPrep<span className="text-amber-400">AI</span></span>
              </div>
            </button>
            <nav className="hidden md:flex items-center gap-1">
              <button onClick={() => router.push("/")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Dashboard</button>
              <button className="px-4 py-2 text-sm font-medium text-white bg-slate-800/60 rounded-lg transition-colors">Trial History</button>
              <button onClick={() => router.push("/about")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Who We Are</button>
              <button onClick={() => router.push("/contact")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Contact</button>
            </nav>
            <button onClick={() => router.push("/profile")} className="hidden sm:flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-xs font-bold hover:opacity-80 transition-opacity" title="Profile">{userInitial}</button>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {loading ? (
          <div className="text-center py-20 text-slate-400">Loading history...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-20">
            <svg className="w-16 h-16 mx-auto text-slate-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-slate-400 text-lg mb-2">No trial transcripts yet</p>
            <p className="text-slate-500 text-sm mb-6">Complete a trial to see its transcript here.</p>
            <button
              onClick={() => router.push("/")}
              className="px-6 py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg transition-colors"
            >
              Start a Trial
            </button>
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(grouped).map(([caseName, caseItems]) => (
              <div key={caseName}>
                <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                  <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                  {caseName}
                </h2>
                <div className="space-y-2">
                  {caseItems.map((item) => (
                    <div key={item.session_id} className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-hidden">
                      <button
                        onClick={() => toggleExpand(item.session_id)}
                        className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-700/30 transition-colors text-left"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3 mb-1">
                            <span className="text-sm text-slate-300">{formatDate(item.started_at)}</span>
                            <span className="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-300">
                              {ROLE_LABELS[item.human_role] || item.human_role}
                            </span>
                            <span className="text-xs text-slate-500">{item.entry_count} entries</span>
                          </div>
                          {item.phases_completed && item.phases_completed.length > 0 && (
                            <div className="flex gap-1.5 flex-wrap">
                              {item.phases_completed.map((p) => (
                                <span key={p} className="text-xs px-1.5 py-0.5 bg-slate-700/50 text-slate-400 rounded">
                                  {p}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <svg
                          className={`w-5 h-5 text-slate-400 transition-transform flex-shrink-0 ml-3 ${expandedId === item.session_id ? "rotate-180" : ""}`}
                          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                        >
                          <polyline points="6 9 12 15 18 9" />
                        </svg>
                      </button>

                      {expandedId === item.session_id && (
                        <div className="border-t border-slate-700/50 px-5 py-4 max-h-[600px] overflow-y-auto">
                          {loadingTranscript === item.session_id ? (
                            <p className="text-slate-400 text-sm py-4 text-center">Loading transcript...</p>
                          ) : transcriptData[item.session_id] ? (
                            <div className="space-y-3">
                              {transcriptData[item.session_id].transcript.map((entry, idx) => (
                                <div key={idx} className="flex gap-3">
                                  <div className="flex-shrink-0 w-32 text-right">
                                    <span className={`text-xs font-medium ${ROLE_COLORS[entry.role] || "text-slate-400"}`}>
                                      {entry.speaker || ROLE_LABELS[entry.role] || entry.role}
                                    </span>
                                  </div>
                                  <div className="flex-1 text-sm text-slate-300 leading-relaxed">
                                    {entry.text}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-slate-500 text-sm py-4 text-center">Failed to load transcript.</p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
