"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ChevronDownIcon } from "@/components/ui/icons";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export default function ScoreDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [report, setReport] = useState<FullReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
  const [expandedMember, setExpandedMember] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    fetch(`${API_BASE}/api/scoring/${sessionId}/full-report`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data) => setReport(data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sessionId]);

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
  const prosMembers = allMembers.filter(([, v]) => v.side === "Prosecution");
  const defMembers = allMembers.filter(([, v]) => v.side === "Defense");

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
      <header className="border-b border-slate-700/50 bg-slate-900/60 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <button onClick={() => router.back()} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
            Back to Courtroom
          </button>
          <h1 className="text-white font-semibold">Score Details</h1>
          <div className="w-32" />
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Case Info */}
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-white mb-1">{report.case_name}</h2>
          <p className="text-slate-400 text-sm">Phase: {report.phase}</p>
        </div>

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
                .map(([key, m]) => ({
                  key,
                  name: m.name,
                  subRole: m.attorney_sub_role || m.witness_role || "",
                  side: m.side,
                  score: getCatScore(m.categories?.[cat]),
                  justification: getCatJustification(m.categories?.[cat]),
                }))
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
    </div>
  );
}


function MemberCard({ mKey, data, expanded, onToggle }: { mKey: string; data: LiveScore; expanded: boolean; onToggle: () => void }) {
  const label = data.attorney_sub_role || data.witness_role || "";
  const sideColor = data.side === "Prosecution" ? "border-blue-500/30" : "border-red-500/30";
  const sideBg = data.side === "Prosecution" ? "bg-blue-500/15" : "bg-red-500/15";

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
