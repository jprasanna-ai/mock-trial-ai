/**
 * Homepage — Dashboard (authenticated) or Landing (unauthenticated)
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, API_BASE } from "@/lib/api";
import type { User } from "@supabase/supabase-js";

// =============================================================================
// TYPES
// =============================================================================

type Role = "attorney_plaintiff" | "attorney_defense" | "witness" | "spectator";

interface CaseMetadata {
  id: string;
  title: string;
  description: string;
  year: number;
  difficulty: "beginner" | "intermediate" | "advanced";
  case_type?: string;
  witness_count?: number;
  exhibit_count?: number;
  featured?: boolean;
  popularity?: number;
}

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

interface SessionScore {
  session_id: string;
  scores: Record<string, { side?: string; average?: number; name?: string; attorney_sub_role?: string; witness_role?: string }>;
}

// =============================================================================
// SVG ICONS (compact inline)
// =============================================================================

const ScalesOfJusticeIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 100 100" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="scaleGold" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#fbbf24" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
    </defs>
    <rect x="35" y="85" width="30" height="8" rx="2" fill="url(#scaleGold)" />
    <rect x="45" y="30" width="10" height="58" fill="url(#scaleGold)" />
    <rect x="10" y="25" width="80" height="6" rx="2" fill="url(#scaleGold)" />
    <circle cx="50" cy="20" r="8" fill="url(#scaleGold)" />
    <circle cx="50" cy="20" r="4" fill="#fef3c7" />
    <line x1="20" y1="31" x2="20" y2="50" stroke="#d97706" strokeWidth="2" />
    <line x1="80" y1="31" x2="80" y2="45" stroke="#d97706" strokeWidth="2" />
    <ellipse cx="20" cy="55" rx="15" ry="5" fill="url(#scaleGold)" />
    <path d="M5 55 Q20 70 35 55" fill="url(#scaleGold)" />
    <ellipse cx="80" cy="50" rx="15" ry="5" fill="url(#scaleGold)" />
    <path d="M65 50 Q80 65 95 50" fill="url(#scaleGold)" />
  </svg>
);

const GavelIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 100 100" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="woodGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#92400e" /><stop offset="50%" stopColor="#78350f" /><stop offset="100%" stopColor="#451a03" />
      </linearGradient>
      <linearGradient id="metalGradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#d4d4d8" /><stop offset="100%" stopColor="#71717a" />
      </linearGradient>
    </defs>
    <ellipse cx="70" cy="75" rx="25" ry="8" fill="url(#woodGradient)" />
    <rect x="45" y="65" width="50" height="10" rx="2" fill="url(#woodGradient)" />
    <rect x="15" y="35" width="45" height="8" rx="2" fill="url(#woodGradient)" transform="rotate(-30 35 40)" />
    <rect x="5" y="15" width="30" height="18" rx="4" fill="url(#woodGradient)" transform="rotate(-30 20 24)" />
    <rect x="8" y="18" width="4" height="12" rx="1" fill="url(#metalGradient)" transform="rotate(-30 10 24)" />
    <rect x="28" y="18" width="4" height="12" rx="1" fill="url(#metalGradient)" transform="rotate(-30 30 24)" />
  </svg>
);

const MicrophoneIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 100 100" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="micGradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#3b82f6" /><stop offset="100%" stopColor="#1d4ed8" />
      </linearGradient>
    </defs>
    <rect x="35" y="15" width="30" height="45" rx="15" fill="url(#micGradient)" />
    {[25, 32, 39, 46].map((y, i) => (
      <line key={i} x1="42" y1={y} x2="58" y2={y} stroke="#1e40af" strokeWidth="2" opacity="0.5" />
    ))}
    <path d="M25 55 Q25 80 50 80 Q75 80 75 55" stroke="#6b7280" strokeWidth="4" fill="none" />
    <rect x="47" y="80" width="6" height="12" fill="#6b7280" />
    <ellipse cx="50" cy="95" rx="18" ry="4" fill="#4b5563" />
  </svg>
);

const DocumentIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 100 100" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="paperGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#fef9c3" /><stop offset="100%" stopColor="#fde68a" />
      </linearGradient>
    </defs>
    <rect x="25" y="8" width="55" height="70" rx="3" fill="#d4d4d8" />
    <rect x="20" y="13" width="55" height="70" rx="3" fill="#e5e7eb" />
    <rect x="15" y="18" width="55" height="70" rx="3" fill="url(#paperGradient)" />
    {[30, 40, 50, 60, 70].map((y, i) => (
      <line key={i} x1="25" y1={y} x2={i === 4 ? 45 : 60} y2={y} stroke="#92400e" strokeWidth="2" opacity="0.3" />
    ))}
    <circle cx="55" cy="75" r="10" fill="#dc2626" opacity="0.8" />
    <circle cx="55" cy="75" r="6" fill="#fef2f2" opacity="0.5" />
  </svg>
);

const AttorneyIllustration = ({ side }: { side: "plaintiff" | "defense" }) => (
  <svg viewBox="0 0 80 100" className="w-full h-auto" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="40" cy="25" r="15" fill="#fcd5b8" />
    <path d={side === "plaintiff" ? "M25 20 Q25 8 40 8 Q55 8 55 20 Q55 15 40 15 Q25 15 25 20" : "M28 18 Q28 10 40 10 Q52 10 52 18 L52 22 Q52 18 40 18 Q28 18 28 22 Z"} fill={side === "plaintiff" ? "#451a03" : "#1f2937"} />
    <path d="M20 45 L25 100 L55 100 L60 45 Q60 35 40 35 Q20 35 20 45" fill={side === "plaintiff" ? "#1e3a8a" : "#1f2937"} />
    <polygon points="35,40 40,70 45,40" fill={side === "plaintiff" ? "#dc2626" : "#1e3a8a"} />
    <polygon points="33,38 40,45 47,38" fill="white" />
    <path d="M32 40 L25 55 L32 50 Z" fill={side === "plaintiff" ? "#1e40af" : "#374151"} />
    <path d="M48 40 L55 55 L48 50 Z" fill={side === "plaintiff" ? "#1e40af" : "#374151"} />
    <circle cx="35" cy="23" r="2" fill="#451a03" /><circle cx="45" cy="23" r="2" fill="#451a03" />
    <path d="M36 30 Q40 33 44 30" stroke="#92400e" strokeWidth="1.5" fill="none" />
    <rect x="58" y="70" width="18" height="14" rx="2" fill="#78350f" /><rect x="64" y="68" width="6" height="4" rx="1" fill="#92400e" />
  </svg>
);

const WitnessIllustration = () => (
  <svg viewBox="0 0 100 100" className="w-full h-auto" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="20" y="50" width="60" height="45" fill="#78350f" rx="3" />
    <rect x="18" y="48" width="64" height="5" fill="#92400e" rx="2" />
    <circle cx="50" cy="28" r="14" fill="#e0c8a8" />
    <ellipse cx="50" cy="18" rx="12" ry="8" fill="#6b7280" />
    <circle cx="45" cy="26" r="2" fill="#374151" /><circle cx="55" cy="26" r="2" fill="#374151" />
    <path d="M46 33 Q50 35 54 33" stroke="#78350f" strokeWidth="1.5" fill="none" />
    <path d="M30 55 Q30 42 50 40 Q70 42 70 55" fill="#60a5fa" />
    <rect x="72" y="35" width="4" height="20" fill="#374151" />
    <ellipse cx="74" cy="33" rx="5" ry="7" fill="#1f2937" />
  </svg>
);

// =============================================================================
// ROLE LABELS
// =============================================================================

const ROLE_LABELS: Record<string, string> = {
  attorney_plaintiff: "Plaintiff Attorney",
  attorney_defense: "Defense Attorney",
  witness: "Witness",
  spectator: "Spectator",
};

// =============================================================================
// DASHBOARD VIEW (Authenticated)
// =============================================================================

function DashboardView({
  user,
  router,
  cases,
  featuredCases,
  isLoadingCases,
  selectedCase,
  setSelectedCase,
  selectedRole,
  setSelectedRole,
  selectedSubRole,
  setSelectedSubRole,
  handleStartTrial,
  isLoading,
  error,
}: {
  user: User;
  router: ReturnType<typeof useRouter>;
  cases: CaseMetadata[];
  featuredCases: CaseMetadata[];
  isLoadingCases: boolean;
  selectedCase: string;
  setSelectedCase: (v: string) => void;
  selectedRole: Role;
  setSelectedRole: (v: Role) => void;
  selectedSubRole: "opening" | "direct_cross" | "closing";
  setSelectedSubRole: (v: "opening" | "direct_cross" | "closing") => void;
  handleStartTrial: () => void;
  isLoading: boolean;
  error: string | null;
}) {
  const [recentSessions, setRecentSessions] = useState<TranscriptHistoryItem[]>([]);
  const [sessionScores, setSessionScores] = useState<Record<string, SessionScore>>({});
  const [dashLoading, setDashLoading] = useState(true);

  const loadDashboardData = useCallback(async () => {
    setDashLoading(true);
    try {
      const histResp = await apiFetch(`${API_BASE}/api/trial/transcripts/history`);
      if (histResp.ok) {
        const data = await histResp.json();
        const transcripts: TranscriptHistoryItem[] = data.transcripts || [];
        transcripts.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
        setRecentSessions(transcripts.slice(0, 8));

        const top5 = transcripts.slice(0, 5);
        const scoreResults = await Promise.all(
          top5.map((t) =>
            apiFetch(`${API_BASE}/api/scoring/${t.session_id}/live-scores`)
              .then((r) => (r.ok ? r.json() : null))
              .catch(() => null)
          )
        );
        const scoresMap: Record<string, SessionScore> = {};
        top5.forEach((t, i) => {
          if (scoreResults[i]?.scores && Object.keys(scoreResults[i].scores).length > 0) {
            scoresMap[t.session_id] = { session_id: t.session_id, scores: scoreResults[i].scores };
          }
        });
        setSessionScores(scoresMap);
      }
    } catch {
      // Non-critical
    } finally {
      setDashLoading(false);
    }
  }, []);

  useEffect(() => { loadDashboardData(); }, [loadDashboardData]);

  // Aggregate stats from session scores
  const allAvgs: number[] = [];
  const prosAvgs: number[] = [];
  const defAvgs: number[] = [];
  Object.values(sessionScores).forEach((ss) => {
    Object.values(ss.scores).forEach((s) => {
      if (s.average && s.average > 0) {
        allAvgs.push(s.average);
        if (s.side === "Prosecution") prosAvgs.push(s.average);
        if (s.side === "Defense") defAvgs.push(s.average);
      }
    });
  });
  const overallAvg = allAvgs.length ? (allAvgs.reduce((a, b) => a + b, 0) / allAvgs.length) : 0;
  const bestScore = allAvgs.length ? Math.max(...allAvgs) : 0;
  const totalTrials = recentSessions.length;

  const displayCases = featuredCases.length > 0 ? featuredCases : cases.slice(0, 3);

  function getSessionAvg(sessionId: string): number | null {
    const ss = sessionScores[sessionId];
    if (!ss) return null;
    const avgs = Object.values(ss.scores).map((s) => s.average || 0).filter((a) => a > 0);
    return avgs.length ? Math.round((avgs.reduce((a, b) => a + b, 0) / avgs.length) * 10) / 10 : null;
  }

  function formatDate(dateStr: string): string {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffHrs = Math.floor(diffMs / 3600000);
    if (diffHrs < 1) return "Just now";
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  function phaseLabel(phases: string[]): string {
    if (!phases || phases.length === 0) return "Not started";
    const last = phases[phases.length - 1]?.toLowerCase();
    if (last === "scoring" || last === "completed") return "Completed";
    return last.charAt(0).toUpperCase() + last.slice(1);
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Welcome Banner */}
      <div className="mb-8">
        <div className="bg-gradient-to-r from-slate-800/80 via-indigo-900/30 to-slate-800/80 border border-slate-700/50 rounded-2xl p-6 md:p-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-white mb-1">
                Welcome back{user.user_metadata?.display_name ? `, ${user.user_metadata.display_name}` : user.email ? `, ${user.email.split("@")[0]}` : ""}
              </h1>
              <p className="text-slate-400 text-sm">Your mock trial preparation dashboard</p>
            </div>
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-2xl font-bold text-white">{totalTrials}</div>
                <div className="text-xs text-slate-500">Trials</div>
              </div>
              <div className="h-8 w-px bg-slate-700" />
              <div className="text-center">
                <div className="text-2xl font-bold text-amber-400">{overallAvg ? overallAvg.toFixed(1) : "--"}</div>
                <div className="text-xs text-slate-500">Avg Score</div>
              </div>
              <div className="h-8 w-px bg-slate-700" />
              <div className="text-center">
                <div className="text-2xl font-bold text-emerald-400">{bestScore ? bestScore.toFixed(1) : "--"}</div>
                <div className="text-xs text-slate-500">Best Score</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Quick Start + Recent Sessions */}
      <div className="grid lg:grid-cols-5 gap-6 mb-8">
        {/* Quick Start (3/5 width) */}
        <div className="lg:col-span-3">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 h-full">
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <GavelIcon className="w-5 h-5" />
              Quick Start
            </h2>

            {/* Compact role picker */}
            <div className="grid grid-cols-4 gap-2 mb-4">
              {([
                { value: "attorney_plaintiff" as Role, label: "Plaintiff", short: "Pros. Atty" },
                { value: "attorney_defense" as Role, label: "Defense", short: "Def. Atty" },
                { value: "witness" as Role, label: "Witness", short: "Witness" },
                { value: "spectator" as Role, label: "Spectator", short: "Watch" },
              ]).map((r) => (
                <button
                  key={r.value}
                  onClick={() => setSelectedRole(r.value)}
                  className={`py-2.5 px-2 rounded-xl text-xs font-medium transition-all text-center ${
                    selectedRole === r.value
                      ? "bg-indigo-600 text-white ring-2 ring-indigo-400 ring-offset-1 ring-offset-slate-800"
                      : "bg-slate-700/50 text-slate-400 hover:bg-slate-700 hover:text-white"
                  }`}
                >
                  {r.short}
                </button>
              ))}
            </div>

            {/* Attorney sub-role */}
            {(selectedRole === "attorney_plaintiff" || selectedRole === "attorney_defense") && (
              <div className="grid grid-cols-3 gap-2 mb-4">
                {([
                  { value: "opening" as const, label: "Opening" },
                  { value: "direct_cross" as const, label: "Direct/Cross" },
                  { value: "closing" as const, label: "Closing" },
                ]).map((sr) => (
                  <button
                    key={sr.value}
                    onClick={() => setSelectedSubRole(sr.value)}
                    className={`py-2 px-2 rounded-lg text-xs font-medium transition-all ${
                      selectedSubRole === sr.value
                        ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/50"
                        : "bg-slate-700/30 text-slate-500 border border-slate-600/30 hover:text-slate-300"
                    }`}
                  >
                    {sr.label}
                  </button>
                ))}
              </div>
            )}

            {/* Compact case list */}
            <div className="space-y-2 mb-4 max-h-[220px] overflow-y-auto">
              {isLoadingCases ? (
                <div className="flex items-center justify-center py-6 text-slate-500 text-sm">
                  <svg className="animate-spin w-4 h-4 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  Loading cases...
                </div>
              ) : displayCases.length > 0 ? (
                displayCases.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedCase(c.id)}
                    className={`w-full text-left p-3 rounded-xl transition-all flex items-center gap-3 ${
                      selectedCase === c.id
                        ? "bg-indigo-600/15 border border-indigo-500/40 ring-1 ring-indigo-400/30"
                        : "bg-slate-700/20 border border-slate-700/30 hover:bg-slate-700/40"
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      c.case_type === "criminal" ? "bg-red-500/20" : "bg-blue-500/20"
                    }`}>
                      {c.case_type === "criminal" ? <GavelIcon className="w-5 h-5" /> : <ScalesOfJusticeIcon className="w-5 h-5" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-white truncate">{c.title}</div>
                      <div className="text-xs text-slate-500">{c.case_type === "criminal" ? "Criminal" : "Civil"} &middot; {c.year}</div>
                    </div>
                    {selectedCase === c.id && (
                      <svg className="w-4 h-4 text-indigo-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </button>
                ))
              ) : (
                <div className="text-center py-4 text-sm text-slate-500">No cases available. Check backend.</div>
              )}
            </div>
            <div className="flex items-center justify-between">
              <button onClick={() => router.push("/cases")} className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                Browse all cases &rarr;
              </button>
              {error && <span className="text-xs text-red-400">{error}</span>}
            </div>

            {/* Start button */}
            <button
              onClick={handleStartTrial}
              disabled={isLoading || !selectedCase}
              className={`w-full mt-4 py-3.5 rounded-xl font-bold text-base transition-all ${
                isLoading || !selectedCase
                  ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                  : "bg-gradient-to-r from-amber-400 via-amber-500 to-orange-500 text-slate-900 hover:from-amber-300 hover:via-amber-400 hover:to-orange-400 shadow-lg shadow-amber-500/20 hover:shadow-xl hover:scale-[1.01]"
              }`}
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  Preparing...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  <GavelIcon className="w-5 h-5" />
                  Enter the Courtroom
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Recent Sessions (2/5 width) */}
        <div className="lg:col-span-2">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 h-full">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Recent Trials
              </h2>
              <button onClick={() => router.push("/history")} className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                View all &rarr;
              </button>
            </div>

            {dashLoading ? (
              <div className="flex items-center justify-center py-12 text-slate-500 text-sm">
                <svg className="animate-spin w-5 h-5 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                Loading...
              </div>
            ) : recentSessions.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-14 h-14 mx-auto mb-3 rounded-full bg-slate-700/50 flex items-center justify-center">
                  <GavelIcon className="w-8 h-8 opacity-40" />
                </div>
                <p className="text-sm text-slate-500 mb-1">No trials yet</p>
                <p className="text-xs text-slate-600">Start your first trial to see it here</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[380px] overflow-y-auto">
                {recentSessions.map((s) => {
                  const avg = getSessionAvg(s.session_id);
                  const status = phaseLabel(s.phases_completed);
                  const isCompleted = status === "Completed";
                  return (
                    <button
                      key={s.session_id}
                      onClick={() => router.push(`/trials/${s.session_id}`)}
                      className="w-full text-left p-3 rounded-xl bg-slate-700/20 border border-slate-700/30 hover:bg-slate-700/40 transition-all group"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-white truncate group-hover:text-indigo-300 transition-colors">
                            {s.case_name || "Untitled Case"}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-slate-500">{ROLE_LABELS[s.human_role] || s.human_role}</span>
                            <span className="text-slate-700">&middot;</span>
                            <span className="text-xs text-slate-500">{formatDate(s.updated_at)}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {avg !== null && (
                            <span className={`px-2 py-1 rounded-lg text-xs font-bold ${
                              avg >= 7 ? "bg-emerald-500/20 text-emerald-300" : avg >= 5 ? "bg-amber-500/20 text-amber-300" : "bg-red-500/20 text-red-300"
                            }`}>
                              {avg}
                            </span>
                          )}
                          <span className={`px-2 py-1 rounded-lg text-xs font-medium ${
                            isCompleted ? "bg-emerald-500/10 text-emerald-400" : "bg-blue-500/10 text-blue-400"
                          }`}>
                            {status}
                          </span>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Performance Overview */}
      {Object.keys(sessionScores).length > 0 && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 mb-8">
          <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
            <ScalesOfJusticeIcon className="w-5 h-5" />
            Performance Overview
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {/* Overall */}
            <div className="bg-slate-700/30 rounded-xl p-5 text-center">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Overall Average</div>
              <div className="text-4xl font-bold text-white mb-1">{overallAvg.toFixed(1)}</div>
              <div className="text-xs text-slate-500">across {allAvgs.length} scored participants</div>
              <div className="mt-3 h-2 bg-slate-600/50 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-amber-400 to-amber-500 rounded-full transition-all" style={{ width: `${(overallAvg / 10) * 100}%` }} />
              </div>
            </div>

            {/* Prosecution Side */}
            <div className="bg-blue-500/5 border border-blue-500/10 rounded-xl p-5 text-center">
              <div className="text-xs text-blue-400 uppercase tracking-wider mb-2">Prosecution Avg</div>
              <div className="text-4xl font-bold text-blue-300 mb-1">
                {prosAvgs.length ? (prosAvgs.reduce((a, b) => a + b, 0) / prosAvgs.length).toFixed(1) : "--"}
              </div>
              <div className="text-xs text-slate-500">{prosAvgs.length} scored members</div>
              {prosAvgs.length > 0 && (
                <div className="mt-3 h-2 bg-slate-600/50 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-400 to-blue-500 rounded-full transition-all" style={{ width: `${((prosAvgs.reduce((a, b) => a + b, 0) / prosAvgs.length) / 10) * 100}%` }} />
                </div>
              )}
            </div>

            {/* Defense Side */}
            <div className="bg-red-500/5 border border-red-500/10 rounded-xl p-5 text-center">
              <div className="text-xs text-red-400 uppercase tracking-wider mb-2">Defense Avg</div>
              <div className="text-4xl font-bold text-red-300 mb-1">
                {defAvgs.length ? (defAvgs.reduce((a, b) => a + b, 0) / defAvgs.length).toFixed(1) : "--"}
              </div>
              <div className="text-xs text-slate-500">{defAvgs.length} scored members</div>
              {defAvgs.length > 0 && (
                <div className="mt-3 h-2 bg-slate-600/50 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-red-400 to-red-500 rounded-full transition-all" style={{ width: `${((defAvgs.reduce((a, b) => a + b, 0) / defAvgs.length) / 10) * 100}%` }} />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Your Performance — User's own scores by role */}
      {recentSessions.length > 0 && (() => {
        type UserTrialScore = {
          sessionId: string;
          caseName: string;
          role: string;
          subRole?: string;
          score: number;
          date: string;
        };

        const userScores: UserTrialScore[] = [];

        recentSessions.forEach((s) => {
          const ss = sessionScores[s.session_id];
          if (!ss) return;

          const rolePrefix = s.human_role;
          Object.entries(ss.scores).forEach(([key, val]) => {
            if (key.startsWith(rolePrefix) && val.average && val.average > 0) {
              const subPart = key.replace(rolePrefix + "_", "");
              userScores.push({
                sessionId: s.session_id,
                caseName: s.case_name,
                role: s.human_role,
                subRole: subPart !== key ? subPart : undefined,
                score: val.average,
                date: s.updated_at,
              });
            }
          });
        });

        if (userScores.length === 0) return null;

        const byRole: Record<string, UserTrialScore[]> = {};
        userScores.forEach((us) => {
          const label = ROLE_LABELS[us.role] || us.role;
          if (!byRole[label]) byRole[label] = [];
          byRole[label].push(us);
        });

        const userOverallAvg = userScores.reduce((a, b) => a + b.score, 0) / userScores.length;
        const userBest = Math.max(...userScores.map((u) => u.score));
        const userLatest = userScores[0]?.score || 0;

        const subRoleLabel = (sr: string) => {
          const map: Record<string, string> = { opening: "Opening", closing: "Closing", direct_cross: "Direct/Cross", direct: "Direct", cross: "Cross" };
          return map[sr] || sr.charAt(0).toUpperCase() + sr.slice(1);
        };

        return (
          <div className="bg-gradient-to-br from-slate-800/60 via-indigo-900/10 to-slate-800/60 border border-indigo-500/15 rounded-2xl p-6 mb-8">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>
                Your Performance
              </h2>
              <span className="text-xs text-slate-500">{userScores.length} scored session{userScores.length !== 1 ? "s" : ""}</span>
            </div>

            {/* Summary row */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-slate-700/30 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-indigo-300">{userOverallAvg.toFixed(1)}</div>
                <div className="text-xs text-slate-500">Your Average</div>
              </div>
              <div className="bg-slate-700/30 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-emerald-400">{userBest.toFixed(1)}</div>
                <div className="text-xs text-slate-500">Best Score</div>
              </div>
              <div className="bg-slate-700/30 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-amber-400">{userLatest.toFixed(1)}</div>
                <div className="text-xs text-slate-500">Latest Score</div>
              </div>
            </div>

            {/* By role */}
            <div className="space-y-4">
              {Object.entries(byRole).map(([roleLabel, scores]) => {
                const roleAvg = scores.reduce((a, b) => a + b.score, 0) / scores.length;
                const roleBest = Math.max(...scores.map((s) => s.score));
                const isPlaintiff = roleLabel.toLowerCase().includes("plaintiff");
                const bgClass = isPlaintiff ? "bg-blue-500/8 border-blue-500/15" : "bg-red-500/8 border-red-500/15";
                const textClass = isPlaintiff ? "text-blue-300" : "text-red-300";
                const barClass = isPlaintiff ? "from-blue-400 to-blue-500" : "from-red-400 to-red-500";
                const dotClass = isPlaintiff ? "bg-blue-400" : "bg-red-400";

                return (
                  <div key={roleLabel} className={`border rounded-xl p-4 ${bgClass}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${dotClass}`} />
                        <span className={`text-sm font-semibold ${textClass}`}>{roleLabel}</span>
                        <span className="text-xs text-slate-500">({scores.length} trial{scores.length !== 1 ? "s" : ""})</span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-slate-500">
                        <span>Avg: <span className={`font-bold ${textClass}`}>{roleAvg.toFixed(1)}</span></span>
                        <span>Best: <span className="font-bold text-emerald-400">{roleBest.toFixed(1)}</span></span>
                      </div>
                    </div>

                    {/* Progress bar */}
                    <div className="h-2 bg-slate-600/40 rounded-full overflow-hidden mb-3">
                      <div className={`h-full bg-gradient-to-r ${barClass} rounded-full transition-all`} style={{ width: `${(roleAvg / 10) * 100}%` }} />
                    </div>

                    {/* Individual trial scores */}
                    <div className="space-y-1.5">
                      {scores.map((s, i) => (
                        <button
                          key={`${s.sessionId}-${i}`}
                          onClick={() => router.push(`/trials/${s.sessionId}`)}
                          className="w-full flex items-center justify-between text-left px-3 py-2 bg-slate-800/40 hover:bg-slate-700/40 rounded-lg transition-colors group"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-xs text-slate-400 truncate max-w-[160px]">{s.caseName}</span>
                            {s.subRole && (
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                isPlaintiff ? "bg-blue-500/15 text-blue-400" : "bg-red-500/15 text-red-400"
                              }`}>
                                {subRoleLabel(s.subRole)}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-xs text-slate-500">{formatDate(s.date)}</span>
                            <span className={`text-sm font-bold ${
                              s.score >= 8 ? "text-emerald-400" : s.score >= 6 ? "text-amber-400" : "text-red-400"
                            }`}>
                              {s.score.toFixed(1)}
                            </span>
                            <svg className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* Quick Links */}
      <div className="grid md:grid-cols-3 gap-4">
        <button onClick={() => router.push("/cases")} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5 text-left hover:bg-slate-800/70 hover:border-slate-600/50 transition-all group">
          <div className="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center mb-3"><DocumentIcon className="w-6 h-6" /></div>
          <div className="text-sm font-semibold text-white group-hover:text-blue-300 transition-colors">Case Library</div>
          <div className="text-xs text-slate-500 mt-0.5">Browse and upload practice cases</div>
        </button>
        <button onClick={() => router.push("/tools")} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5 text-left hover:bg-slate-800/70 hover:border-slate-600/50 transition-all group">
          <div className="w-10 h-10 rounded-lg bg-amber-500/15 flex items-center justify-center mb-3"><ScalesOfJusticeIcon className="w-6 h-6" /></div>
          <div className="text-sm font-semibold text-white group-hover:text-amber-300 transition-colors">Practice Tools</div>
          <div className="text-xs text-slate-500 mt-0.5">Rules reference, AI coach, voice practice</div>
        </button>
        <button onClick={() => router.push("/history")} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5 text-left hover:bg-slate-800/70 hover:border-slate-600/50 transition-all group">
          <div className="w-10 h-10 rounded-lg bg-purple-500/15 flex items-center justify-center mb-3">
            <svg className="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          </div>
          <div className="text-sm font-semibold text-white group-hover:text-purple-300 transition-colors">Trial History</div>
          <div className="text-xs text-slate-500 mt-0.5">View transcripts from past sessions</div>
        </button>
      </div>
    </div>
  );
}

// =============================================================================
// LANDING VIEW (Unauthenticated)
// =============================================================================

function LandingView({
  router,
  cases,
  featuredCases,
  isLoadingCases,
  selectedCase,
  setSelectedCase,
  selectedRole,
  setSelectedRole,
  selectedSubRole,
  setSelectedSubRole,
  handleStartTrial,
  isLoading,
  error,
}: {
  router: ReturnType<typeof useRouter>;
  cases: CaseMetadata[];
  featuredCases: CaseMetadata[];
  isLoadingCases: boolean;
  selectedCase: string;
  setSelectedCase: (v: string) => void;
  selectedRole: Role;
  setSelectedRole: (v: Role) => void;
  selectedSubRole: "opening" | "direct_cross" | "closing";
  setSelectedSubRole: (v: "opening" | "direct_cross" | "closing") => void;
  handleStartTrial: () => void;
  isLoading: boolean;
  error: string | null;
}) {
  const roleOptions: { value: Role; label: string; description: string; illustration: React.ReactNode }[] = [
    { value: "attorney_plaintiff", label: "Plaintiff Attorney", description: "Represent the prosecution side", illustration: <AttorneyIllustration side="plaintiff" /> },
    { value: "attorney_defense", label: "Defense Attorney", description: "Defend against the charges", illustration: <AttorneyIllustration side="defense" /> },
    { value: "witness", label: "Witness", description: "Take the stand and respond", illustration: <WitnessIllustration /> },
    { value: "spectator", label: "Spectator", description: "Watch AI vs AI trial", illustration: (
      <svg viewBox="0 0 96 96" className="w-full h-full p-4">
        <circle cx="48" cy="40" r="20" fill="none" stroke="currentColor" strokeWidth="3" className="text-amber-400" />
        <circle cx="48" cy="40" r="8" fill="currentColor" className="text-amber-400" />
        <path d="M12 40 C 12 20, 84 20, 84 40 C 84 60, 12 60, 12 40Z" fill="none" stroke="currentColor" strokeWidth="3" className="text-amber-300" />
        <text x="48" y="78" textAnchor="middle" fill="currentColor" className="text-slate-400" fontSize="10" fontWeight="bold">WATCH</text>
      </svg>
    )},
  ];

  const difficultyColors: Record<string, string> = {
    beginner: "bg-emerald-100 text-emerald-800 border-emerald-200",
    intermediate: "bg-amber-100 text-amber-800 border-amber-200",
    advanced: "bg-rose-100 text-rose-800 border-rose-200",
  };

  const displayCases = featuredCases.length > 0 ? featuredCases : cases.slice(0, 3);

  return (
    <>
      {/* Hero */}
      <div className="max-w-7xl mx-auto px-4 pt-12 pb-4">
        <div className="text-center max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-amber-500/15 to-orange-500/15 border border-amber-500/25 rounded-full text-amber-300 text-sm mb-8 backdrop-blur-sm">
            <ScalesOfJusticeIcon className="w-4 h-4" />
            AI-Powered Mock Trial Preparation Platform
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6 leading-tight">
            <span className="bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">Prepare. Practice.</span>
            <br />
            <span className="bg-gradient-to-r from-amber-300 via-yellow-200 to-amber-400 bg-clip-text text-transparent">Win Your Case.</span>
          </h1>
          <p className="text-lg text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
            The complete mock trial preparation platform. Run full trial simulations with AI attorneys,
            witnesses, and judges. Get real-time scoring, strategic prep materials, and detailed performance feedback.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10 max-w-3xl mx-auto">
            {[
              { icon: <DocumentIcon className="w-6 h-6" />, label: "Case Analysis", sub: "Auto-generated briefs" },
              { icon: <GavelIcon className="w-6 h-6" />, label: "Full Trials", sub: "Opening to verdict" },
              { icon: <MicrophoneIcon className="w-6 h-6" />, label: "Voice or Text", sub: "Speak or type" },
              { icon: <ScalesOfJusticeIcon className="w-6 h-6" />, label: "AI Scoring", sub: "Judge feedback" },
            ].map((item, i) => (
              <div key={i} className="bg-slate-800/40 border border-slate-700/40 rounded-xl p-4 text-center">
                <div className="w-10 h-10 mx-auto mb-2 rounded-lg bg-slate-700/50 flex items-center justify-center text-amber-400">{item.icon}</div>
                <div className="text-sm font-semibold text-white">{item.label}</div>
                <div className="text-xs text-slate-500 mt-0.5">{item.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Try It Out CTA */}
      <div className="pb-16">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-3">Ready to Try It Out?</h2>
          <p className="text-slate-400 mb-8 max-w-xl mx-auto">Create a free account and run your first AI-powered mock trial in minutes. No credit card required.</p>
          <div className="flex items-center justify-center gap-4">
            <button onClick={() => router.push("/login")} className="px-8 py-3.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-amber-500/20 text-lg">
              Get Started Free
            </button>
            <button onClick={() => router.push("/trials")} className="px-8 py-3.5 bg-slate-800/50 hover:bg-slate-700/50 text-slate-300 border border-slate-700/50 rounded-xl transition-colors">
              Watch a Trial
            </button>
          </div>
        </div>
      </div>

      {/* Role & Case Selection */}
      <div className="max-w-6xl mx-auto px-4 pb-16">
        <div className="text-center mb-10">
          <h2 className="text-3xl font-bold text-white mb-3">Start a Trial Session</h2>
          <p className="text-slate-400">Select your role, pick a case, and begin your preparation</p>
        </div>
        <div className="grid md:grid-cols-4 gap-6 mb-12">
          {roleOptions.map((role) => (
            <button key={role.value} onClick={() => setSelectedRole(role.value)} className={`group relative overflow-hidden rounded-2xl transition-all duration-300 ${selectedRole === role.value ? "ring-4 ring-blue-400 ring-offset-4 ring-offset-slate-900 scale-105" : "hover:scale-102 hover:ring-2 hover:ring-slate-600"}`}>
              <div className={`absolute inset-0 transition-opacity ${selectedRole === role.value ? "bg-gradient-to-br from-blue-600 to-indigo-700" : "bg-gradient-to-br from-slate-800 to-slate-900"}`} />
              <div className="relative p-6">
                <div className={`w-24 h-24 mx-auto mb-4 rounded-xl overflow-hidden ${selectedRole === role.value ? "bg-white/10" : "bg-slate-700/50"}`}>{role.illustration}</div>
                <h3 className={`text-xl font-bold mb-2 ${selectedRole === role.value ? "text-white" : "text-slate-200"}`}>{role.label}</h3>
                <p className={`text-sm ${selectedRole === role.value ? "text-blue-100" : "text-slate-400"}`}>{role.description}</p>
                {selectedRole === role.value && (
                  <div className="absolute top-4 right-4 w-8 h-8 bg-white rounded-full flex items-center justify-center shadow-lg">
                    <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Attorney sub-role */}
        {(selectedRole === "attorney_plaintiff" || selectedRole === "attorney_defense") && (
          <div className="max-w-4xl mx-auto mb-8">
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-6">
              <h3 className="text-lg font-semibold text-white mb-1">Attorney Specialization</h3>
              <p className="text-slate-400 text-sm mb-4">Pick which attorney role you want to play.</p>
              <div className="grid md:grid-cols-3 gap-3">
                {([
                  { value: "opening" as const, label: "Opening Attorney", desc: "Delivers the opening statement", icon: "\uD83D\uDCE2" },
                  { value: "direct_cross" as const, label: "Direct/Cross Attorney", desc: "Examines witnesses, makes objections", icon: "\uD83D\uDD0D" },
                  { value: "closing" as const, label: "Closing Attorney", desc: "Delivers the closing argument", icon: "\uD83C\uDFC6" },
                ]).map((role) => (
                  <button key={role.value} onClick={() => setSelectedSubRole(role.value)} className={`p-4 rounded-xl border-2 transition-all text-left ${selectedSubRole === role.value ? "border-emerald-500 bg-emerald-500/10" : "border-slate-600 bg-slate-700/30 hover:border-slate-500"}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">{role.icon}</span>
                      <span className={`font-semibold text-sm ${selectedSubRole === role.value ? "text-emerald-300" : "text-slate-200"}`}>{role.label}</span>
                    </div>
                    <p className="text-xs text-slate-400">{role.desc}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Case selection */}
        <div className="max-w-4xl mx-auto">
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-6 mb-8">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-white flex items-center gap-2"><DocumentIcon className="w-6 h-6" /> Select a Case</h3>
              <button onClick={() => router.push("/cases")} className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors">Browse all &rarr;</button>
            </div>
            {displayCases.length > 0 ? (
              <div className="grid gap-4">
                {displayCases.map((c) => (
                  <button key={c.id} onClick={() => setSelectedCase(c.id)} className={`group relative w-full text-left transition-all duration-300 rounded-xl overflow-hidden ${selectedCase === c.id ? "ring-2 ring-blue-400 ring-offset-2 ring-offset-slate-900" : "hover:ring-1 hover:ring-slate-600"}`}>
                    <div className={`absolute inset-0 ${c.case_type === "criminal" ? "bg-gradient-to-r from-red-900/30 to-slate-800/50" : "bg-gradient-to-r from-blue-900/30 to-slate-800/50"}`} />
                    <div className="relative p-5">
                      <div className="flex items-start gap-4">
                        <div className={`flex-shrink-0 w-14 h-14 rounded-xl flex items-center justify-center ${c.case_type === "criminal" ? "bg-red-500/20" : "bg-blue-500/20"}`}>
                          {c.case_type === "criminal" ? <GavelIcon className="w-8 h-8" /> : <ScalesOfJusticeIcon className="w-8 h-8" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="text-lg font-semibold text-white group-hover:text-blue-300 transition-colors">{c.title}</h4>
                          <p className="text-sm text-slate-400 mt-1 line-clamp-2">{c.description}</p>
                          <div className="flex items-center gap-4 mt-3">
                            <span className="text-xs text-slate-500">{c.witness_count || 4} Witnesses</span>
                            <span className="text-xs text-slate-500">{c.year}</span>
                            {c.difficulty && <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${difficultyColors[c.difficulty] || difficultyColors.intermediate}`}>{c.difficulty.charAt(0).toUpperCase() + c.difficulty.slice(1)}</span>}
                          </div>
                        </div>
                        {selectedCase === c.id && (
                          <div className="absolute top-3 right-3 w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center shadow-lg">
                            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
                          </div>
                        )}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            ) : !isLoadingCases ? (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6 text-center">
                <div className="font-semibold text-amber-200">No Cases Available</div>
                <div className="text-sm text-amber-300/70 mt-1">Ensure the backend server is running.</div>
              </div>
            ) : null}
          </div>
          {error && <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6 text-red-200 text-sm">{error}</div>}
          <button onClick={handleStartTrial} disabled={isLoading} className={`w-full py-5 px-8 rounded-2xl font-bold text-xl transition-all duration-300 ${isLoading ? "bg-slate-700 text-slate-400 cursor-not-allowed" : "bg-gradient-to-r from-amber-400 via-amber-500 to-orange-500 text-slate-900 hover:from-amber-300 hover:via-amber-400 hover:to-orange-400 shadow-lg shadow-amber-500/25 hover:shadow-xl hover:scale-[1.02]"}`}>
            {isLoading ? "Preparing Courtroom..." : (
              <span className="flex items-center justify-center gap-3"><GavelIcon className="w-7 h-7" /> Enter the Courtroom</span>
            )}
          </button>
        </div>
      </div>

      {/* Features */}
      <div className="bg-gradient-to-b from-transparent via-slate-800/50 to-transparent py-20">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-white mb-3">Complete Trial Preparation</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">Everything you need to prepare for mock trial competitions</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
            {[
              { title: "Case Brief & Theory", desc: "AI-generated case briefs and strategic analysis tailored to your side.", icon: <DocumentIcon className="w-8 h-8" />, color: "from-blue-500/20 to-indigo-500/20", border: "border-blue-500/20" },
              { title: "Witness Preparation", desc: "Detailed witness outlines and examination questions.", icon: <WitnessIllustration />, color: "from-emerald-500/20 to-teal-500/20", border: "border-emerald-500/20" },
              { title: "Opening & Closing", desc: "Pre-generated statements grounded in case facts.", icon: <MicrophoneIcon className="w-8 h-8" />, color: "from-purple-500/20 to-violet-500/20", border: "border-purple-500/20" },
              { title: "Objection Strategies", desc: "Learn which objections to raise and when.", icon: <GavelIcon className="w-8 h-8" />, color: "from-amber-500/20 to-orange-500/20", border: "border-amber-500/20" },
              { title: "Full Trial Simulation", desc: "Run complete trials from opening to verdict.", icon: <AttorneyIllustration side="plaintiff" />, color: "from-red-500/20 to-rose-500/20", border: "border-red-500/20" },
              { title: "Scoring & Feedback", desc: "AI judges score across AMTA categories.", icon: <ScalesOfJusticeIcon className="w-8 h-8" />, color: "from-cyan-500/20 to-sky-500/20", border: "border-cyan-500/20" },
            ].map((item, i) => (
              <div key={i} className={`bg-gradient-to-br ${item.color} backdrop-blur-sm rounded-2xl border ${item.border} p-6 transition-all hover:scale-[1.02]`}>
                <div className="w-12 h-12 rounded-xl overflow-hidden bg-slate-800/60 flex items-center justify-center mb-4">{item.icon}</div>
                <h3 className="text-lg font-semibold text-white mb-2">{item.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* How It Works */}
      <div className="py-20">
        <div className="max-w-5xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-white mb-3">How It Works</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">Get started in minutes with four simple steps</p>
          </div>
          <div className="grid md:grid-cols-4 gap-6">
            {[
              { step: "1", title: "Choose a Case", desc: "Browse our case library or upload your own AMTA/MYLaw case materials.", icon: <DocumentIcon className="w-6 h-6" /> },
              { step: "2", title: "Pick Your Role", desc: "Plaintiff attorney, defense attorney, witness, or spectator — your choice.", icon: <GavelIcon className="w-6 h-6" /> },
              { step: "3", title: "Run the Trial", desc: "AI agents play all other roles. Speak or type your arguments in real time.", icon: <MicrophoneIcon className="w-6 h-6" /> },
              { step: "4", title: "Get Scored", desc: "AI judges evaluate every participant across AMTA scoring categories.", icon: <ScalesOfJusticeIcon className="w-6 h-6" /> },
            ].map((item, i) => (
              <div key={i} className="relative text-center">
                <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/20 flex items-center justify-center text-amber-400">
                  {item.icon}
                </div>
                <div className="absolute -top-2 -right-2 w-7 h-7 rounded-full bg-amber-500 text-slate-900 text-xs font-bold flex items-center justify-center">{item.step}</div>
                <h3 className="text-base font-semibold text-white mb-1">{item.title}</h3>
                <p className="text-sm text-slate-400">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="py-10 border-t border-slate-800/60">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center"><ScalesOfJusticeIcon className="w-5 h-5" /></div>
              <span className="text-sm font-bold text-white">MockPrep<span className="text-amber-400">AI</span></span>
            </div>
            <div className="flex items-center gap-6 text-xs text-slate-600">
              <button onClick={() => router.push("/trials")} className="hover:text-slate-400 transition-colors">Recorded Trials</button>
              <button onClick={() => router.push("/about")} className="hover:text-slate-400 transition-colors">About</button>
              <button onClick={() => router.push("/contact")} className="hover:text-slate-400 transition-colors">Contact</button>
            </div>
            <p className="text-xs text-slate-600">AI-powered preparation for mock trial excellence.</p>
          </div>
        </div>
      </footer>
    </>
  );
}

// =============================================================================
// PAGE COMPONENT
// =============================================================================

export default function HomePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getUser().then(({ data }) => { setUser(data.user); setAuthChecked(true); });
    const onFocus = () => {
      sb.auth.getUser().then(({ data }) => {
        if (data.user) setUser(data.user);
      });
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);

  const handleLogout = async () => {
    const sb = createClient();
    await sb.auth.signOut();
    setUser(null);
    router.push("/login");
  };

  const [cases, setCases] = useState<CaseMetadata[]>([]);
  const [featuredCases, setFeaturedCases] = useState<CaseMetadata[]>([]);
  const [selectedCase, setSelectedCase] = useState<string>("");
  const [selectedRole, setSelectedRole] = useState<Role>("spectator");
  const [selectedSubRole, setSelectedSubRole] = useState<"opening" | "direct_cross" | "closing">("direct_cross");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingCases, setIsLoadingCases] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadCases() {
      try {
        const [homepageRes, demoRes] = await Promise.all([
          apiFetch(`${API_BASE}/api/case/user/homepage`),
          apiFetch(`${API_BASE}/api/case/demo`),
        ]);
        if (homepageRes.ok) {
          const homepage = await homepageRes.json();
          const hCases = homepage.cases || [];
          setFeaturedCases(hCases);
          if (hCases.length > 0) setSelectedCase(hCases[0].id);
        } else {
          const featuredRes = await apiFetch(`${API_BASE}/api/case/featured?limit=3`);
          if (featuredRes.ok) {
            const featured = await featuredRes.json();
            setFeaturedCases(featured || []);
            if (featured?.length > 0) setSelectedCase(featured[0].id);
          }
        }
        if (demoRes.ok) {
          const demoCases = await demoRes.json();
          setCases(demoCases || []);
          if (!selectedCase && demoCases?.length > 0) setSelectedCase(demoCases[0].id);
        }
      } catch { /* ignore */ } finally { setIsLoadingCases(false); }
    }
    loadCases();
  }, []);

  const handleStartTrial = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await apiFetch(`${API_BASE}/api/session/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: selectedCase || undefined,
          human_role: selectedRole,
          attorney_sub_role: (selectedRole === "attorney_plaintiff" || selectedRole === "attorney_defense") ? selectedSubRole : undefined,
        }),
      });
      if (!resp.ok) throw new Error("Failed to create session");
      const data = await resp.json();
      apiFetch(`${API_BASE}/api/session/${data.session_id}/initialize`, { method: "POST", headers: { "Content-Type": "application/json" } }).catch(() => {});
      router.push(`/courtroom/${data.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start trial");
      setIsLoading(false);
    }
  };

  const sharedProps = {
    router, cases, featuredCases, isLoadingCases, selectedCase, setSelectedCase,
    selectedRole, setSelectedRole, selectedSubRole, setSelectedSubRole,
    handleStartTrial, isLoading, error,
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-indigo-950">
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-10 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
      </div>

      {/* Header */}
      <header className="relative z-20 border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-md sticky top-0">
        <div className="max-w-7xl mx-auto px-4 py-0">
          <div className="flex items-center justify-between h-16">
            <button onClick={() => router.push("/")} className="flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                <ScalesOfJusticeIcon className="w-6 h-6" />
              </div>
              <div className="flex flex-col leading-tight">
                <span className="text-lg font-bold tracking-tight">MockPrep<span className="text-amber-400">AI</span></span>
                <span className="text-[10px] text-slate-500 uppercase tracking-widest font-medium -mt-0.5">Trial Preparation</span>
              </div>
            </button>
            {authChecked && user ? (
              <nav className="hidden md:flex items-center gap-1">
                <button onClick={() => router.push("/")} className="px-4 py-2 text-sm font-medium text-white bg-slate-800/60 rounded-lg transition-colors">Dashboard</button>
                <button onClick={() => router.push("/about")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Who We Are</button>
                <button onClick={() => router.push("/contact")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Contact</button>
              </nav>
            ) : authChecked ? (
              <nav className="hidden md:flex items-center gap-1">
                <button onClick={() => router.push("/")} className="px-4 py-2 text-sm font-medium text-white bg-slate-800/60 rounded-lg transition-colors">Home</button>
                <button onClick={() => router.push("/trials")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Recorded Trials</button>
                <button onClick={() => router.push("/about")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Who We Are</button>
                <button onClick={() => router.push("/contact")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Contact</button>
              </nav>
            ) : null}
            <div className="flex items-center gap-3">
              {authChecked && user ? (
                <div className="flex items-center gap-3">
                  <button onClick={() => router.push("/profile")} className="hidden sm:flex items-center gap-2 hover:opacity-80 transition-opacity" title="Profile">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
                      {(user.user_metadata?.display_name || user.email || "U")[0].toUpperCase()}
                    </div>
                    <span className="text-sm text-slate-400 max-w-[140px] truncate">{user.user_metadata?.display_name || user.email}</span>
                  </button>
                  <button onClick={handleLogout} className="px-3 py-1.5 text-xs text-slate-500 hover:text-red-400 border border-slate-700/50 hover:border-red-500/30 rounded-lg transition-colors">Sign Out</button>
                </div>
              ) : authChecked ? (
                <div className="flex items-center gap-2">
                  <button onClick={() => router.push("/login")} className="px-4 py-2 text-sm font-medium bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-white rounded-lg transition-all shadow-lg shadow-amber-500/20">Try It Out</button>
                  <button onClick={() => router.push("/login")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white border border-slate-700/50 hover:border-slate-600 rounded-lg transition-colors">Sign In</button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="relative z-10">
        {!authChecked ? (
          <div className="flex items-center justify-center py-32">
            <svg className="animate-spin w-8 h-8 text-slate-500" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
          </div>
        ) : user ? (
          <DashboardView user={user} {...sharedProps} />
        ) : (
          <LandingView {...sharedProps} />
        )}
      </div>
    </div>
  );
}
