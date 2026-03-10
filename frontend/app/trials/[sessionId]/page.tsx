"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";

interface TranscriptEntry {
  role: string;
  speaker: string;
  content?: string;
  text?: string;
  timestamp?: string;
  phase?: string;
}

const SPEAKER_COLORS: Record<string, string> = {
  attorney_plaintiff: "text-blue-400",
  attorney_defense: "text-red-400",
  witness: "text-emerald-400",
  judge: "text-purple-400",
  clerk: "text-slate-400",
  bailiff: "text-slate-400",
  narrator: "text-amber-400",
};

const CATEGORY_LABELS: Record<string, string> = {
  opening_clarity: "Opening Clarity",
  direct_examination_effectiveness: "Direct Exam",
  cross_examination_control: "Cross Exam Control",
  objection_accuracy: "Objection Accuracy",
  responsiveness: "Responsiveness",
  courtroom_presence: "Courtroom Presence",
  case_theory_consistency: "Case Theory",
  persuasiveness: "Persuasiveness",
  factual_foundation: "Factual Foundation",
  closing_persuasiveness: "Closing Persuasiveness",
  evidence_integration: "Evidence Integration",
  rebuttal_effectiveness: "Rebuttal",
  testimony_consistency: "Testimony Consistency",
  credibility: "Credibility",
  composure_under_pressure: "Composure Under Pressure",
};

function ScoreBar({ score, max = 10 }: { score: number; max?: number }) {
  const pct = (score / max) * 100;
  const bg = score >= 8 ? "bg-emerald-500" : score >= 6 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="flex-1 h-2 bg-slate-700/60 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${bg} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-bold w-6 text-right ${score >= 8 ? "text-emerald-400" : score >= 6 ? "text-amber-400" : "text-red-400"}`}>{score}</span>
    </div>
  );
}

function ParticipantCard({ entryKey, val, scoreColor }: { entryKey: string; val: any; scoreColor: (s: number | null | undefined) => string }) {
  const [expanded, setExpanded] = React.useState(false);
  const name = val?.name || entryKey.replace(/_/g, " ").replace(/^(attorney|witness)\s/, "");
  const displayName = name.split(" ").map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  const entryAvg = val?.average ?? val?.overall_average;
  const sub = val?.attorney_sub_role || val?.witness_role || "";
  const categories = val?.categories || {};
  const comments = val?.comments || "";
  const catEntries = Object.entries(categories);

  return (
    <div className="bg-slate-700/25 border border-slate-700/40 rounded-xl overflow-hidden">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-700/30 transition-colors text-left">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-full bg-slate-700/60 flex items-center justify-center text-sm font-bold text-slate-300 shrink-0">{displayName.charAt(0)}</div>
          <div className="min-w-0">
            <span className="text-sm font-semibold text-slate-200 block truncate">{displayName}</span>
            {sub && <span className="text-xs text-slate-500">{sub}</span>}
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className={`text-xl font-bold ${scoreColor(entryAvg)}`}>{typeof entryAvg === "number" ? entryAvg.toFixed(1) : "—"}</span>
          <svg className={`w-4 h-4 text-slate-500 transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
        </div>
      </button>
      {expanded && (
        <div className="border-t border-slate-700/40 px-4 py-4 space-y-4">
          {catEntries.length > 0 && (
            <div className="space-y-2.5">
              <h5 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Category Scores</h5>
              {catEntries.map(([cat, cv]) => {
                const score = typeof cv === "object" && cv !== null ? (cv as any).score : cv;
                const justification = typeof cv === "object" && cv !== null ? (cv as any).justification : "";
                const label = CATEGORY_LABELS[cat] || cat.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());
                return (
                  <div key={cat} className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-400 w-40 shrink-0">{label}</span>
                      {typeof score === "number" && <ScoreBar score={score} />}
                    </div>
                    {justification && <p className="text-xs text-slate-500 leading-relaxed pl-[10.5rem]">{justification}</p>}
                  </div>
                );
              })}
            </div>
          )}
          {comments && (
            <div className="space-y-1.5">
              <h5 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg>
                Judge&apos;s Comments
              </h5>
              <div className="bg-slate-800/40 rounded-lg px-4 py-3">
                <p className="text-sm text-slate-300 leading-relaxed italic">&ldquo;{comments}&rdquo;</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ScoresPanel({ scores, scoreColor }: { scores: Record<string, any>; scoreColor: (s: number | null | undefined) => string }) {
  const entries = Object.entries(scores);
  const prosEntries = entries.filter(([k, v]) => k.includes("plaintiff") || v?.side === "Prosecution" || v?.side === "prosecution");
  const defEntries = entries.filter(([k, v]) => k.includes("defense") || v?.side === "Defense" || v?.side === "defense");
  const prosKeys = new Set(prosEntries.map(([k]) => k));
  const defKeys = new Set(defEntries.map(([k]) => k));
  const otherEntries = entries.filter(([k]) => !prosKeys.has(k) && !defKeys.has(k));

  const avgScore = (list: [string, any][]) => {
    const vals = list.map(([, v]) => v?.average ?? v?.overall_average).filter((n: any) => typeof n === "number" && !isNaN(n));
    return vals.length ? (vals.reduce((a: number, b: number) => a + b, 0) / vals.length) : null;
  };
  const prosAvg = avgScore(prosEntries);
  const defAvg = avgScore(defEntries);
  const winner = prosAvg != null && defAvg != null ? (prosAvg > defAvg ? "Prosecution" : prosAvg < defAvg ? "Defense" : "Tie") : null;

  const renderSide = (label: string, list: [string, any][], avg: number | null, color: string) => (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h4 className={`text-base font-bold ${color}`}>{label}</h4>
        {avg != null && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 uppercase">Avg</span>
            <span className={`text-2xl font-bold ${scoreColor(avg)}`}>{avg.toFixed(1)}</span>
          </div>
        )}
      </div>
      <div className="space-y-2">
        {list.map(([key, val]) => (
          <ParticipantCard key={key} entryKey={key} val={val} scoreColor={scoreColor} />
        ))}
      </div>
    </div>
  );

  return (
    <div className="space-y-5 max-h-[600px] overflow-y-auto pr-1">
      {winner && (
        <div className={`text-center rounded-xl p-5 border ${winner === "Prosecution" ? "bg-blue-500/10 border-blue-500/20" : winner === "Defense" ? "bg-red-500/10 border-red-500/20" : "bg-slate-700/30 border-slate-700/50"}`}>
          <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Verdict</div>
          <div className={`text-xl font-bold ${winner === "Prosecution" ? "text-blue-400" : winner === "Defense" ? "text-red-400" : "text-slate-300"}`}>{winner === "Tie" ? "Tie" : `${winner} Wins`}</div>
          <div className="flex items-center justify-center gap-6 mt-2 text-sm">
            <span className="text-blue-400">Prosecution: {prosAvg?.toFixed(1)}</span>
            <span className="text-slate-600">vs</span>
            <span className="text-red-400">Defense: {defAvg?.toFixed(1)}</span>
          </div>
        </div>
      )}
      {prosAvg != null && defAvg != null && (
        <div className="bg-slate-800/40 border border-slate-700/40 rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-3 text-center">Score Comparison</div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-blue-400 font-medium w-10 text-right">{prosAvg.toFixed(1)}</span>
            <div className="flex-1 flex h-3 rounded-full overflow-hidden bg-slate-700/50">
              <div className="bg-blue-500/70 transition-all" style={{ width: `${(prosAvg / (prosAvg + defAvg)) * 100}%` }} />
              <div className="bg-red-500/70 transition-all" style={{ width: `${(defAvg / (prosAvg + defAvg)) * 100}%` }} />
            </div>
            <span className="text-xs text-red-400 font-medium w-10">{defAvg.toFixed(1)}</span>
          </div>
          <div className="flex justify-between mt-1.5">
            <span className="text-[10px] text-blue-400/70">Prosecution</span>
            <span className="text-[10px] text-red-400/70">Defense</span>
          </div>
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-5">
        {prosEntries.length > 0 && renderSide("Prosecution", prosEntries, prosAvg, "text-blue-400")}
        {defEntries.length > 0 && renderSide("Defense", defEntries, defAvg, "text-red-400")}
      </div>
      {otherEntries.length > 0 && (
        <div>{renderSide("Other Participants", otherEntries, avgScore(otherEntries), "text-slate-300")}</div>
      )}
    </div>
  );
}

export default function TrialDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [caseName, setCaseName] = useState<string>("");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"transcript" | "scores">("transcript");

  const [playingIndex, setPlayingIndex] = useState<number | null>(null);
  const [audioLoading, setAudioLoading] = useState(false);
  const [autoPlay, setAutoPlay] = useState(false);
  const [paused, setPaused] = useState(false);
  const [audioCacheKeys, setAudioCacheKeys] = useState<Record<number, string>>({});
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  const autoPlayRef = React.useRef(false);

  const [scores, setScores] = useState<Record<string, any> | null>(null);
  const [loadingScores, setLoadingScores] = useState(false);

  const hasAudio = Object.keys(audioCacheKeys).length > 0;

  const scoreColor = (s: number | null | undefined) => {
    if (s == null) return "text-slate-500";
    if (s >= 8) return "text-emerald-400";
    if (s >= 6) return "text-amber-400";
    return "text-red-400";
  };

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
      audioRef.current = null;
    }
    setPlayingIndex(null);
    setAudioLoading(false);
    autoPlayRef.current = false;
    setAutoPlay(false);
    setPaused(false);
  }, []);

  useEffect(() => {
    return () => { if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; } };
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    setLoading(true);

    const loadData = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/trial/transcripts/${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          setCaseName(data.case_name || data.title || "");

          const raw: TranscriptEntry[] = data.transcript || data.entries || [];
          const filtered = raw.filter((e) => {
            const role = (e.role || "").toLowerCase();
            return role !== "system" && (e.content || e.text || "").trim().length > 0;
          });
          setTranscript(filtered);

          const keys: Record<number, string> = {};
          const audioMap = data.audio_keys || {};
          let filteredIdx = 0;
          for (let rawIdx = 0; rawIdx < raw.length; rawIdx++) {
            const e = raw[rawIdx];
            const role = (e.role || "").toLowerCase();
            const hasContent = role !== "system" && (e.content || e.text || "").trim().length > 0;
            if (hasContent) {
              if (audioMap[String(rawIdx)]) keys[filteredIdx] = audioMap[String(rawIdx)];
              filteredIdx++;
            }
          }
          setAudioCacheKeys(keys);
        }
      } catch { /* transcript not available — non-fatal */ }
    };

    const loadScores = async () => {
      setLoadingScores(true);
      try {
        const res = await fetch(`${API_BASE}/api/scoring/${sessionId}/live-scores`);
        if (res.ok) {
          const data = await res.json();
          setScores(data.scores && Object.keys(data.scores).length > 0 ? data.scores : null);
        }
      } catch { /* ignore */ }
      finally { setLoadingScores(false); }
    };

    const loadMeta = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/scoring/${sessionId}/full-report`);
        if (res.ok) {
          const data = await res.json();
          if (data.case_name && data.case_name !== sessionId) {
            setCaseName((prev) => prev || data.case_name);
          }
        }
      } catch { /* ignore */ }
    };

    Promise.all([loadData(), loadScores(), loadMeta()]).finally(() => setLoading(false));
  }, [sessionId]);

  const playEntry = useCallback(async (index: number) => {
    if (playingIndex === index) { stopAudio(); return; }
    const cacheKey = audioCacheKeys[index];
    if (!cacheKey) return;

    stopAudio();
    setPlayingIndex(index);
    setAudioLoading(true);

    try {
      const audioUrl = `${API_BASE}/api/public/tts/audio/${cacheKey}`;
      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      setAudioLoading(false);

      audio.onended = () => {
        setPlayingIndex(null);
        if (autoPlayRef.current) {
          let next = index + 1;
          while (next < transcript.length && !audioCacheKeys[next]) next++;
          if (next < transcript.length) playEntry(next);
          else stopAudio();
        }
      };
      audio.onerror = () => { setPlayingIndex(null); setAudioLoading(false); };
      await audio.play();
    } catch {
      setPlayingIndex(null);
      setAudioLoading(false);
    }
  }, [playingIndex, audioCacheKeys, transcript.length, stopAudio]);

  const toggleAutoPlay = useCallback(() => {
    if (autoPlay) {
      stopAudio();
    } else {
      autoPlayRef.current = true;
      setAutoPlay(true);
      const first = Object.keys(audioCacheKeys).map(Number).sort((a, b) => a - b)[0];
      if (first != null) playEntry(first);
    }
  }, [autoPlay, audioCacheKeys, playEntry, stopAudio]);

  const pauseAudio = () => {
    if (audioRef.current && !audioRef.current.paused) { audioRef.current.pause(); setPaused(true); }
  };
  const resumeAudio = () => {
    if (audioRef.current && audioRef.current.paused) { audioRef.current.play(); setPaused(false); }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-slate-400">
          <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
          Loading trial...
        </div>
      </div>
    );
  }

  const hasTranscript = transcript.length > 0;
  const hasScores = scores && Object.keys(scores).length > 0;

  // Auto-switch to scores tab if no transcript but scores exist
  const effectiveTab = activeTab === "transcript" && !hasTranscript && hasScores ? "scores" : activeTab;

  if (!loading && !hasTranscript && !hasScores && !loadingScores) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-400 mb-4">No data available for this trial yet.</p>
          <button onClick={() => router.push("/")} className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors">Back to Dashboard</button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-4 flex items-center justify-between h-14">
          <button onClick={() => router.back()} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" /></svg>
            Back
          </button>
          <h1 className="text-white font-semibold text-sm truncate max-w-md">
            {caseName || "Trial Detail"}
          </h1>
          <div className="w-20" />
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="flex items-center gap-1 mb-6">
          <button onClick={() => setActiveTab("transcript")} className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === "transcript" ? "bg-slate-700/60 text-white" : "text-slate-400 hover:text-white hover:bg-slate-700/30"}`}>
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
              Transcript
            </span>
          </button>
          <button onClick={() => setActiveTab("scores")} className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === "scores" ? "bg-slate-700/60 text-white" : "text-slate-400 hover:text-white hover:bg-slate-700/30"}`}>
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" /></svg>
              Scores
            </span>
          </button>
        </div>

        {effectiveTab === "transcript" ? (
          <>
            {transcript.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-12">No transcript available for this trial.</p>
            ) : (
              <>
                {/* Audio controls */}
                <div className="flex items-center justify-between mb-4 bg-slate-800/50 border border-slate-700/40 rounded-xl px-4 py-3">
                  <div className="flex items-center gap-3">
                    {hasAudio && !autoPlay && (
                      <button onClick={toggleAutoPlay} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30">
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg> Play Full Trial
                      </button>
                    )}
                    {autoPlay && (
                      <>
                        {paused ? (
                          <button onClick={resumeAudio} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30 transition-all">
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg> Resume
                          </button>
                        ) : (
                          <button onClick={pauseAudio} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30 transition-all">
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" /></svg> Pause
                          </button>
                        )}
                        <button onClick={stopAudio} className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-all">
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><rect x="6" y="4" width="12" height="16" rx="2" /></svg> Stop
                        </button>
                      </>
                    )}
                    {!hasAudio && !autoPlay && (
                      <span className="text-xs text-slate-500">Audio not available for this trial</span>
                    )}
                    {playingIndex !== null && (
                      <span className="text-xs text-slate-500">
                        {paused ? "Paused" : "Playing"} {playingIndex + 1} of {transcript.length}
                        {audioLoading && " (loading...)"}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-slate-600">{transcript.length} exchanges</span>
                </div>

                {/* Transcript entries */}
                <div className="space-y-3">
                  {transcript.map((entry, i) => {
                    const roleLower = (entry.role || "").toLowerCase();
                    const roleKey = roleLower.includes("plaintiff") ? "attorney_plaintiff"
                      : roleLower.includes("defense") ? "attorney_defense"
                      : roleLower.includes("witness") ? "witness"
                      : roleLower.includes("judge") ? "judge"
                      : roleLower.includes("clerk") ? "clerk"
                      : roleLower.includes("narrator") ? "narrator"
                      : roleLower;
                    const roleColor = SPEAKER_COLORS[roleKey] || "text-slate-400";
                    const speakerName = (entry.speaker || entry.role || "").replace(/^Role\./, "").replace(/_/g, " ");
                    const displayName = speakerName.split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
                    const bodyText = entry.content || entry.text || "";
                    const isPlaying = playingIndex === i;
                    const isLoadingThis = isPlaying && audioLoading;
                    const isCached = !!audioCacheKeys[i];
                    return (
                      <div key={i} className={`flex gap-3 transition-colors ${isPlaying ? "bg-amber-500/5 rounded-lg -mx-1 px-1" : ""}`}>
                        <div className="shrink-0 w-32 text-right pt-2">
                          <span className={`text-xs font-semibold ${roleColor}`}>{displayName}</span>
                          {entry.phase && <div className="text-[10px] text-slate-600">{entry.phase}</div>}
                        </div>
                        <div className="flex-1 text-sm text-slate-300 leading-relaxed bg-slate-800/40 rounded-lg px-4 py-2.5 flex gap-2 items-start">
                          <p className="flex-1">{bodyText}</p>
                          {isCached && (
                            <button
                              onClick={() => playEntry(i)}
                              title={isPlaying ? "Stop" : "Play"}
                              className={`shrink-0 mt-0.5 w-7 h-7 rounded-full flex items-center justify-center transition-all ${
                                isPlaying
                                  ? "bg-amber-500/30 text-amber-300 hover:bg-red-500/30 hover:text-red-300"
                                  : "bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30"
                              }`}
                            >
                              {isLoadingThis ? (
                                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                              ) : isPlaying ? (
                                <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" /></svg>
                              ) : (
                                <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                              )}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </>
        ) : (
          <div className="space-y-4">
            {loadingScores ? (
              <div className="flex items-center justify-center py-12 text-slate-500 text-sm">
                <svg className="animate-spin w-5 h-5 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                Loading scores...
              </div>
            ) : !scores || Object.keys(scores).length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-12">No scoring data available for this trial.</p>
            ) : (
              <ScoresPanel scores={scores} scoreColor={scoreColor} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
