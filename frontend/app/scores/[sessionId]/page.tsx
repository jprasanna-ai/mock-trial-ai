"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ChevronDownIcon } from "@/components/ui/icons";
import { apiFetch, API_BASE } from "@/lib/api";

function EmailDialog({
  open,
  onClose,
  sessionId,
}: {
  open: boolean;
  onClose: () => void;
  sessionId: string;
}) {
  const [emails, setEmails] = useState("");
  const [includeTranscript, setIncludeTranscript] = useState(true);
  const [includeScores, setIncludeScores] = useState(true);
  const [senderName, setSenderName] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const handleSend = useCallback(async () => {
    const recipients = emails
      .split(/[,;\n]+/)
      .map((e) => e.trim())
      .filter((e) => e.includes("@"));
    if (recipients.length === 0) {
      setResult({ ok: false, msg: "Enter at least one valid email address" });
      return;
    }
    setSending(true);
    setResult(null);
    try {
      const resp = await apiFetch(`${API_BASE}/api/trial/${sessionId}/email-report`, {
        method: "POST",
        body: JSON.stringify({
          recipients,
          include_transcript: includeTranscript,
          include_scores: includeScores,
          sender_name: senderName || undefined,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setResult({ ok: true, msg: data.message || "Sent!" });
      setTimeout(() => onClose(), 2000);
    } catch (e: any) {
      setResult({ ok: false, msg: e.message || "Failed to send" });
    } finally {
      setSending(false);
    }
  }, [emails, includeTranscript, includeScores, senderName, sessionId, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
            </svg>
            Email Report
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Recipient Emails</label>
            <textarea
              value={emails}
              onChange={(e) => setEmails(e.target.value)}
              placeholder="Enter email addresses (comma or newline separated)"
              rows={3}
              className="w-full bg-slate-900/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Your Name (optional)</label>
            <input
              value={senderName}
              onChange={(e) => setSenderName(e.target.value)}
              placeholder="Shown as sender name"
              className="w-full bg-slate-900/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includeTranscript}
                onChange={(e) => setIncludeTranscript(e.target.checked)}
                className="w-4 h-4 rounded border-slate-500 bg-slate-700 text-blue-500 focus:ring-blue-500"
              />
              <span className="text-sm text-slate-300">Include Transcript</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includeScores}
                onChange={(e) => setIncludeScores(e.target.checked)}
                className="w-4 h-4 rounded border-slate-500 bg-slate-700 text-blue-500 focus:ring-blue-500"
              />
              <span className="text-sm text-slate-300">Include Scores</span>
            </label>
          </div>

          {result && (
            <div className={`p-3 rounded-lg text-sm ${result.ok ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400" : "bg-red-500/10 border border-red-500/30 text-red-400"}`}>
              {result.msg}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-slate-700 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={sending || !emails.trim()}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
          >
            {sending ? (
              <>
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-20" /><path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" /></svg>
                Sending...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                </svg>
                Send Report
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

interface CategoryDetail {
  score: number;
  justification: string;
}

interface LiveScore {
  role: string;
  name: string;
  side: string;
  average: number;
  total: number;
  categories?: Record<string, CategoryDetail | number>;
  comments?: string;
  attorney_sub_role?: string;
  witness_role?: string;
}

interface FullReport {
  session_id: string;
  case_name: string;
  case_id: string;
  phase: string;
  live_scores: Record<string, LiveScore>;
  category_descriptions: Record<string, string>;
}

const CATEGORY_LABELS: Record<string, string> = {
  opening_clarity: "Opening Clarity",
  direct_examination_effectiveness: "Direct Examination",
  cross_examination_control: "Cross-Examination Control",
  objection_accuracy: "Objection Accuracy",
  responsiveness: "Responsiveness",
  courtroom_presence: "Courtroom Presence",
  case_theory_consistency: "Case Theory Consistency",
  persuasiveness: "Persuasiveness",
  factual_foundation: "Factual Foundation",
  closing_persuasiveness: "Closing Persuasiveness",
  evidence_integration: "Evidence Integration",
  rebuttal_effectiveness: "Rebuttal Effectiveness",
  testimony_consistency: "Testimony Consistency",
  credibility: "Credibility",
  composure_under_pressure: "Composure Under Pressure",
};

function getCatScore(cat: CategoryDetail | number | undefined): number {
  if (!cat) return 0;
  if (typeof cat === "number") return cat;
  return cat.score ?? 0;
}

function getCatJustification(cat: CategoryDetail | number | undefined): string {
  if (!cat || typeof cat === "number") return "";
  return cat.justification ?? "";
}

function ScoreBar({ score, max = 10, compact = false }: { score: number; max?: number; compact?: boolean }) {
  const pct = Math.min((score / max) * 100, 100);
  const color =
    score >= 8 ? "bg-emerald-500" : score >= 6 ? "bg-amber-500" : score >= 4 ? "bg-orange-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2 w-full">
      <div className={`flex-1 ${compact ? "h-2" : "h-2.5"} bg-slate-700 rounded-full overflow-hidden`}>
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`${compact ? "text-xs" : "text-sm"} font-mono text-slate-300 w-10 text-right`}>{score.toFixed(1)}</span>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 8 ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
    : score >= 6 ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
    : score >= 4 ? "bg-orange-500/20 text-orange-400 border-orange-500/30"
    : "bg-red-500/20 text-red-400 border-red-500/30";
  return (
    <span className={`inline-flex items-center justify-center w-10 h-7 rounded-md border text-sm font-bold ${color}`}>
      {score.toFixed(1)}
    </span>
  );
}

interface Verdict {
  winner: string;
  prosecution_avg: number;
  defense_avg: number;
  margin: number;
  verdict_text: string;
  prosecution_categories: Record<string, number>;
  defense_categories: Record<string, number>;
}

export default function ScoreDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [report, setReport] = useState<FullReport | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
  const [expandedMember, setExpandedMember] = useState<string | null>(null);
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    Promise.all([
      apiFetch(`${API_BASE}/api/scoring/${sessionId}/full-report`)
        .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      apiFetch(`${API_BASE}/api/scoring/${sessionId}/verdict`)
        .then((r) => r.ok ? r.json() : null)
        .catch(() => null),
    ])
      .then(([reportData, verdictData]) => {
        setReport(reportData);
        if (verdictData) setVerdict(verdictData);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sessionId]);

  const handleRefreshScores = useCallback(async () => {
    if (!sessionId || refreshing) return;
    setRefreshing(true);
    try {
      await apiFetch(`${API_BASE}/api/scoring/${sessionId}/live-score`, { method: "POST" });
      const [reportData, verdictData] = await Promise.all([
        apiFetch(`${API_BASE}/api/scoring/${sessionId}/full-report`)
          .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
        apiFetch(`${API_BASE}/api/scoring/${sessionId}/verdict`)
          .then((r) => r.ok ? r.json() : null)
          .catch(() => null),
      ]);
      setReport(reportData);
      if (verdictData) setVerdict(verdictData);
    } catch (e: any) {
      console.error("Refresh failed:", e);
    } finally {
      setRefreshing(false);
    }
  }, [sessionId, refreshing]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
        <p className="text-slate-400">Loading scores...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error || "Failed to load scores"}</p>
          <button onClick={() => router.back()} className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600">Go Back</button>
        </div>
      </div>
    );
  }

  const allMembers = Object.entries(report.live_scores);
  const prosMembers = allMembers.filter(([k, v]) => {
    if (k.startsWith("attorney_")) return k.startsWith("attorney_plaintiff");
    return v.side === "Prosecution";
  });
  const prosKeys = new Set(prosMembers.map(([k]) => k));
  const defMembers = allMembers.filter(([k, v]) => {
    if (prosKeys.has(k)) return false;
    if (k.startsWith("attorney_")) return k.startsWith("attorney_defense");
    return true;
  });

  const discoveredCategories = Array.from(
    new Set(
      allMembers.flatMap(([, m]) =>
        m.categories ? Object.keys(m.categories).filter((c) => getCatScore(m.categories![c]) > 0) : []
      )
    )
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-4 py-0 flex items-center justify-between h-14">
          <button onClick={() => { if (window.history.length > 1) { router.back(); } else { router.push(`/courtroom/${sessionId}`); } }} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
            Back to Courtroom
          </button>
          <h1 className="text-white font-semibold flex items-center gap-2">
            <span className="text-amber-400 font-bold text-sm">MockPrep<span className="text-amber-300">AI</span></span>
            <span className="text-slate-600">|</span>
            Score Details
          </h1>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefreshScores}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700/50 border border-slate-600/50 text-slate-300 hover:bg-slate-600/50 hover:text-white disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
              title="Regenerate all scores from transcript"
            >
              <svg className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
              </svg>
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
            <button
              onClick={() => setEmailDialogOpen(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-blue-600/20 border border-blue-500/30 text-blue-400 hover:bg-blue-600/30 hover:text-blue-300 rounded-lg text-sm font-medium transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
              </svg>
              Email Report
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Case Info */}
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-white mb-1">{report.case_name}</h2>
          <p className="text-slate-400 text-sm">Phase: {report.phase}</p>
          {report.phase?.toLowerCase() !== "scoring" && report.phase?.toLowerCase() !== "completed" && (
            <p className="text-yellow-400 text-xs mt-2">Trial is still in progress. Scores shown are partial. Verdict will be available after the trial is complete.</p>
          )}
        </div>

        {/* Verdict Banner — only show when trial is done */}
        {verdict && (report.phase?.toLowerCase() === "scoring" || report.phase?.toLowerCase() === "completed") && (
          <div className="mb-10 bg-gradient-to-r from-amber-900/30 via-amber-800/20 to-amber-900/30 border border-amber-500/30 rounded-2xl overflow-hidden">
            <div className="px-6 py-5 text-center border-b border-amber-500/20">
              <div className="flex items-center justify-center gap-3 mb-3">
                <svg className="w-7 h-7 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
                </svg>
                <h3 className="text-xl font-bold text-amber-300 uppercase tracking-wider">Verdict</h3>
              </div>
              <div className="flex items-center justify-center gap-8 mb-4">
                <div className={`text-center ${verdict.winner === "Prosecution" ? "ring-2 ring-amber-400 rounded-xl px-4 py-2" : "px-4 py-2"}`}>
                  <p className="text-xs text-blue-400 uppercase tracking-wider font-semibold">Prosecution</p>
                  <p className="text-3xl font-bold text-white">{verdict.prosecution_avg}</p>
                </div>
                <div className="text-slate-500 text-sm font-medium">vs</div>
                <div className={`text-center ${verdict.winner === "Defense" ? "ring-2 ring-amber-400 rounded-xl px-4 py-2" : "px-4 py-2"}`}>
                  <p className="text-xs text-red-400 uppercase tracking-wider font-semibold">Defense</p>
                  <p className="text-3xl font-bold text-white">{verdict.defense_avg}</p>
                </div>
              </div>
              <p className="text-amber-300 font-semibold text-lg">
                {verdict.winner} wins by {verdict.margin} points
              </p>
            </div>
            <div className="px-6 py-5">
              <p className="text-slate-300 leading-relaxed text-sm italic">
                &ldquo;{verdict.verdict_text}&rdquo;
              </p>
            </div>
          </div>
        )}

        {/* ── SECTION 1: Category-by-Category Breakdown ── */}
        <div className="mb-12">
          <h3 className="text-lg font-semibold text-white mb-5 flex items-center gap-2">
            <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
            </svg>
            Score Breakdown by Category
          </h3>

          <div className="space-y-3">
            {discoveredCategories.map((cat) => {
              const isExpanded = expandedCategory === cat;
              const desc = report.category_descriptions?.[cat] || "";
              const memberScores = allMembers
                .map(([key, m]) => {
                  const derivedSide = key.startsWith("attorney_plaintiff") ? "Prosecution"
                    : key.startsWith("attorney_defense") ? "Defense"
                    : m.side;
                  return {
                    key,
                    name: m.name,
                    subRole: m.attorney_sub_role || m.witness_role || "",
                    side: derivedSide,
                    score: getCatScore(m.categories?.[cat]),
                    justification: getCatJustification(m.categories?.[cat]),
                  };
                })
                .filter((ms) => ms.score > 0);

              const avgScore = memberScores.length > 0
                ? memberScores.reduce((s, m) => s + m.score, 0) / memberScores.length : 0;

              return (
                <div key={cat} className="bg-slate-800/50 border border-slate-700/40 rounded-xl overflow-hidden">
                  <button
                    onClick={() => setExpandedCategory(isExpanded ? null : cat)}
                    className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-700/20 transition-colors text-left"
                  >
                    <div className="flex items-center gap-4 flex-1 min-w-0">
                      <ScoreBadge score={avgScore} />
                      <div className="min-w-0">
                        <div className="text-white font-medium">{CATEGORY_LABELS[cat]}</div>
                        {desc && <div className="text-xs text-slate-500 truncate">{desc}</div>}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 ml-3">
                      <span className="text-xs text-slate-500">{memberScores.length} scored</span>
                      <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-slate-700/50 px-5 py-4">
                      {memberScores.length === 0 ? (
                        <p className="text-slate-500 text-sm">No participants scored in this category yet.</p>
                      ) : (
                        <div className="space-y-4">
                          {memberScores.map((ms) => {
                            const sideColor = ms.side === "Prosecution" ? "text-blue-400" : "text-red-400";
                            return (
                              <div key={ms.key} className="bg-slate-900/40 rounded-lg p-4">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-white">{ms.name}</span>
                                    <span className={`text-xs ${sideColor}`}>{ms.side}</span>
                                    {ms.subRole && <span className="text-xs text-slate-500">({ms.subRole})</span>}
                                  </div>
                                </div>
                                <ScoreBar score={ms.score} compact />
                                {ms.justification && (
                                  <p className="text-xs text-slate-400 mt-2 leading-relaxed border-l-2 border-slate-600 pl-3">
                                    {ms.justification}
                                  </p>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── SECTION 2: Per Team Member Detail ── */}
        <div className="mb-12">
          <h3 className="text-lg font-semibold text-white mb-5 flex items-center gap-2">
            <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
            </svg>
            Individual Performance
          </h3>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Prosecution Column */}
            <div>
              <h4 className="text-sm font-semibold text-blue-400 mb-3 flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-blue-500" />
                Prosecution
              </h4>
              <div className="space-y-3">
                {prosMembers.length === 0 ? (
                  <p className="text-slate-500 text-sm">No scores yet</p>
                ) : prosMembers.map(([key, data]) => (
                  <MemberCard key={key} mKey={key} data={data} expanded={expandedMember === key} onToggle={() => setExpandedMember(expandedMember === key ? null : key)} />
                ))}
              </div>
            </div>

            {/* Defense Column */}
            <div>
              <h4 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
                Defense
              </h4>
              <div className="space-y-3">
                {defMembers.length === 0 ? (
                  <p className="text-slate-500 text-sm">No scores yet</p>
                ) : defMembers.map(([key, data]) => (
                  <MemberCard key={key} mKey={key} data={data} expanded={expandedMember === key} onToggle={() => setExpandedMember(expandedMember === key ? null : key)} />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Category Legend */}
        {report.category_descriptions && (
          <div className="bg-slate-800/30 border border-slate-700/30 rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Scoring Categories Reference</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(report.category_descriptions).map(([cat, desc]) => (
                <div key={cat} className="flex gap-2">
                  <span className="text-sm font-medium text-slate-300 whitespace-nowrap">{CATEGORY_LABELS[cat] || cat}:</span>
                  <span className="text-sm text-slate-500">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <EmailDialog open={emailDialogOpen} onClose={() => setEmailDialogOpen(false)} sessionId={sessionId} />
    </div>
  );
}


function MemberCard({ mKey, data, expanded, onToggle }: { mKey: string; data: LiveScore; expanded: boolean; onToggle: () => void }) {
  const label = data.attorney_sub_role || data.witness_role || "";
  const isPros = mKey.startsWith("attorney_plaintiff") || (!mKey.startsWith("attorney_defense") && data.side === "Prosecution");
  const sideColor = isPros ? "border-blue-500/30" : "border-red-500/30";
  const sideBg = isPros ? "bg-blue-500/15" : "bg-red-500/15";

  const catEntries = data.categories
    ? Object.entries(data.categories).filter(([, v]) => getCatScore(v) > 0)
    : [];

  const strengths: { cat: string; score: number; text: string }[] = [];
  const improvements: { cat: string; score: number; text: string }[] = [];

  for (const [cat, detail] of catEntries) {
    const score = getCatScore(detail);
    const just = getCatJustification(detail);
    if (score >= 7 && just) {
      strengths.push({ cat, score, text: just });
    } else if (score < 7 && just) {
      improvements.push({ cat, score, text: just });
    }
  }

  return (
    <div className={`bg-slate-800/50 border ${sideColor} rounded-xl overflow-hidden`}>
      <button
        onClick={onToggle}
        className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-700/20 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl ${sideBg} flex items-center justify-center`}>
            <span className="text-xl font-bold text-white">{data.average.toFixed(1)}</span>
          </div>
          <div>
            <div className="text-white font-medium">{data.name}</div>
            {label && <div className="text-xs text-slate-500">{label}</div>}
          </div>
        </div>
        <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>

      {expanded && (
        <div className="border-t border-slate-700/50 px-5 py-4 space-y-5">
          {/* Category scores with justifications */}
          {catEntries.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Category Scores</h4>
              {catEntries.map(([cat, detail]) => (
                <div key={cat} className="bg-slate-900/40 rounded-lg p-3">
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-sm text-slate-300">{CATEGORY_LABELS[cat] || cat.replace(/_/g, " ")}</span>
                  </div>
                  <ScoreBar score={getCatScore(detail)} compact />
                  {getCatJustification(detail) && (
                    <p className="text-xs text-slate-400 mt-2 leading-relaxed border-l-2 border-slate-600 pl-3">
                      {getCatJustification(detail)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Strengths */}
          {strengths.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                Strengths
              </h4>
              <div className="space-y-2">
                {strengths.map((s, i) => (
                  <div key={i} className="bg-emerald-500/5 border border-emerald-500/10 rounded-lg px-3 py-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-emerald-400">{CATEGORY_LABELS[s.cat] || s.cat}</span>
                      <span className="text-xs text-emerald-500/70">({s.score}/10)</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{s.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Areas to Improve */}
          {improvements.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" /></svg>
                Suggestions to Improve
              </h4>
              <div className="space-y-2">
                {improvements.map((s, i) => (
                  <div key={i} className="bg-amber-500/5 border border-amber-500/10 rounded-lg px-3 py-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-amber-400">{CATEGORY_LABELS[s.cat] || s.cat}</span>
                      <span className="text-xs text-amber-500/70">({s.score}/10)</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{s.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Overall Judge Comments */}
          {data.comments && (
            <div>
              <h4 className="text-xs font-semibold text-purple-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg>
                Overall Judge Comments
              </h4>
              <p className="text-sm text-slate-300 leading-relaxed bg-slate-900/50 rounded-lg p-3">{data.comments}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
