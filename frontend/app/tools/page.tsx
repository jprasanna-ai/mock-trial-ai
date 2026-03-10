"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, API_BASE } from "@/lib/api";
import VoicePracticeInput, { SpeechAnalysis } from "@/components/VoicePracticeInput";
import type { User } from "@supabase/supabase-js";

type ToolsTab = "rules" | "coach" | "practice";

const ScaleIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0012 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 01-2.031.352 5.988 5.988 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.971zm-16.5.52c.99-.203 1.99-.377 3-.52m0 0l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 01-2.031.352 5.989 5.989 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 4.971z" />
  </svg>
);

const MessageIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
  </svg>
);

const MicrophoneIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
  </svg>
);

const ScalesOfJusticeIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0012 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 01-2.031.352 5.988 5.988 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.971zm-16.5.52c.99-.203 1.99-.377 3-.52m0 0l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 01-2.031.352 5.989 5.989 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 4.971z" />
  </svg>
);

const DocumentIcon = ({ className }: { className?: string }) => (
  <svg className={className || "w-5 h-5"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
  </svg>
);

export default function ToolsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState<ToolsTab>("rules");
  const [rules, setRules] = useState<string[]>([]);
  const [rulesLoading, setRulesLoading] = useState(false);

  // Coach state
  const [chatMessages, setChatMessages] = useState<{ role: string; content: string }[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);
  const chatEndRef = React.useRef<HTMLDivElement>(null);

  // Voice practice state
  const [practiceType, setPracticeType] = useState("opening");
  const [practiceHistory, setPracticeHistory] = useState<{ type: string; transcript: string; analysis: SpeechAnalysis }[]>([]);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setUser(data.user));
  }, []);

  useEffect(() => {
    if (activeTab === "rules" && rules.length === 0) {
      setRulesLoading(true);
      apiFetch(`${API_BASE}/api/prep/mock-trial-rules`)
        .then((r) => r.json())
        .then((data) => setRules(data.rules || []))
        .catch(() => setRules(["Failed to load rules."]))
        .finally(() => setRulesLoading(false));
    }
  }, [activeTab, rules.length]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleLogout = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  };

  const handleSendCoachMessage = async (messageText?: string) => {
    const text = messageText || chatInput.trim();
    if (!text) return;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: text }]);
    setIsChatLoading(true);

    try {
      const resp = await apiFetch(`${API_BASE}/api/prep/coach-general`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await resp.json();
      setChatMessages((prev) => [...prev, { role: "assistant", content: data.response || "No response." }]);
    } catch {
      setChatMessages((prev) => [...prev, { role: "assistant", content: "Sorry, I couldn't connect. Please try again." }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const tabs: { id: ToolsTab; label: string; icon: React.ReactNode }[] = [
    { id: "rules", label: "Mock Trial Rules", icon: <ScaleIcon /> },
    { id: "coach", label: "Coach", icon: <MessageIcon /> },
    { id: "practice", label: "Voice Practice", icon: <MicrophoneIcon /> },
  ];

  const practiceTips: Record<string, string[]> = {
    opening: [
      "Introduce yourself and state who you represent",
      "Present your theory of the case clearly",
      "Preview the evidence you will present",
      "Speak at 130-150 WPM for clarity",
      "Make eye contact with the jury (look at camera)",
    ],
    closing: [
      "Summarize the key evidence presented",
      "Remind the jury of your theme",
      "Address weaknesses in your case",
      "End with a clear call to action",
      "Vary your pace for emphasis",
    ],
    direct: [
      "Use open-ended questions (who, what, when, where, why)",
      "Let the witness tell the story",
      "Avoid leading questions",
      "Establish foundation before key testimony",
      "Listen actively and follow up",
    ],
    cross: [
      "Use leading questions that suggest the answer",
      "One fact per question",
      "Control the witness \u2014 don\u2019t let them explain",
      "Know the answer before you ask",
      "Build to your strongest points",
    ],
    objection: [
      "Stand immediately when objecting",
      'State "Objection" clearly and firmly',
      "Give the specific ground (hearsay, leading, etc.)",
      "Be ready to explain if the judge asks",
      "Accept rulings gracefully",
    ],
    witness: [
      "Answer only the question asked",
      "Pause before answering to allow objections",
      "Speak clearly and at a measured pace",
      "Stay in character throughout",
      "Don\u2019t volunteer extra information",
    ],
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Header */}
      <header className="relative z-20 border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-md sticky top-0">
        <div className="max-w-7xl mx-auto px-4 py-0">
          <div className="flex items-center justify-between h-16">
            <button onClick={() => router.push("/")} className="flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                <ScalesOfJusticeIcon className="w-5 h-5" />
              </div>
              <div className="flex flex-col leading-tight">
                <span className="text-base font-bold tracking-tight">MockPrep<span className="text-amber-400">AI</span></span>
              </div>
            </button>
            <nav className="hidden md:flex items-center gap-1">
              <button onClick={() => router.push("/")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Dashboard</button>
              <button className="px-4 py-2 text-sm font-medium text-white bg-slate-800/60 rounded-lg transition-colors">Practice Tools</button>
              <button onClick={() => router.push("/about")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Who We Are</button>
              <button onClick={() => router.push("/contact")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Contact</button>
            </nav>
            <div className="flex items-center gap-3">
              {user && (
                <div className="flex items-center gap-3">
                  <button onClick={() => router.push("/profile")} className="hidden sm:flex items-center gap-2 hover:opacity-80 transition-opacity" title="Profile">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
                      {(user.email || "U")[0].toUpperCase()}
                    </div>
                    <span className="text-sm text-slate-400 max-w-[140px] truncate">{user.email}</span>
                  </button>
                  <button onClick={handleLogout} className="px-3 py-1.5 text-xs text-slate-500 hover:text-red-400 border border-slate-700/50 hover:border-red-500/30 rounded-lg transition-colors">Sign Out</button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold mb-2">Practice Tools</h1>
          <p className="text-slate-400">General tools for mock trial preparation — not tied to a specific case.</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-800/50 rounded-xl p-1 mb-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "bg-indigo-600 text-white shadow-lg"
                  : "text-slate-400 hover:text-white hover:bg-slate-700/50"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-slate-900/80 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-6">
          {/* Mock Trial Rules */}
          {activeTab === "rules" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 mb-4">
                <ScaleIcon />
                <h3 className="font-semibold text-white text-lg">Mock Trial Rules</h3>
              </div>
              <p className="text-sm text-slate-400 mb-4">
                These rules apply to all mock trial competitions and are essential for proper courtroom conduct.
              </p>
              {rulesLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-8 h-8 border-2 border-indigo-400/30 border-t-indigo-400 rounded-full animate-spin" />
                </div>
              ) : (
                rules.map((rule, i) => (
                  <div key={i} className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center flex-shrink-0">
                      <span className="text-sm font-bold text-indigo-400">{i + 1}</span>
                    </div>
                    <p className="text-sm text-slate-300">{rule}</p>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Coach Chat */}
          {activeTab === "coach" && (
            <div className="flex flex-col" style={{ minHeight: 480 }}>
              <div className="flex-1 overflow-y-auto space-y-4 mb-4">
                {chatMessages.length === 0 && (
                  <div className="text-center py-8">
                    <div className="w-16 h-16 rounded-full bg-indigo-500/20 flex items-center justify-center mx-auto mb-4">
                      <MessageIcon />
                    </div>
                    <h3 className="font-semibold text-white mb-2">MockPrepAI Coach</h3>
                    <p className="text-sm text-slate-400 max-w-md mx-auto">
                      Ask me anything about trial strategy, objections, witness examination, or mock trial rules.
                    </p>
                    <div className="flex flex-wrap justify-center gap-2 mt-4">
                      {["How do I handle a hostile witness?", "What objections should I watch for?", "Tips for opening statements"].map((q) => (
                        <button key={q} onClick={() => handleSendCoachMessage(q)} className="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors">
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {chatMessages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${msg.role === "user" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300"}`}>
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))}

                {isChatLoading && (
                  <div className="flex justify-start">
                    <div className="bg-slate-800 rounded-2xl px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" />
                        <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
                        <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSendCoachMessage()}
                  placeholder="Ask the coach anything about mock trial..."
                  className="flex-1 px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  disabled={isChatLoading}
                />
                <button
                  onClick={() => handleSendCoachMessage()}
                  disabled={isChatLoading || !chatInput.trim()}
                  className="px-5 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-xl transition-colors text-sm font-medium"
                >
                  Send
                </button>
              </div>
            </div>
          )}

          {/* Voice Practice */}
          {activeTab === "practice" && (
            <div className="space-y-6">
              <div className="text-center mb-4">
                <div className="w-16 h-16 rounded-full bg-indigo-500/20 flex items-center justify-center mx-auto mb-4">
                  <MicrophoneIcon />
                </div>
                <h3 className="font-semibold text-white mb-2">Voice Practice</h3>
                <p className="text-sm text-slate-400 max-w-md mx-auto">
                  Practice speaking and get AI feedback on delivery, pacing, and filler words.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">What do you want to practice?</label>
                  <select
                    value={practiceType}
                    onChange={(e) => setPracticeType(e.target.value)}
                    className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="opening">Opening Statement</option>
                    <option value="closing">Closing Argument</option>
                    <option value="direct">Direct Examination Questions</option>
                    <option value="cross">Cross-Examination Questions</option>
                    <option value="objection">Making Objections</option>
                    <option value="witness">Witness Testimony</option>
                  </select>
                </div>
              </div>

              {/* Tips */}
              <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                <h4 className="text-sm font-semibold text-slate-300 mb-3">Practice Tips</h4>
                <ul className="space-y-2 text-sm text-slate-400">
                  {(practiceTips[practiceType] || []).map((tip, i) => (
                    <li key={i}>• {tip}</li>
                  ))}
                </ul>
              </div>

              {/* Voice Input */}
              <div className="bg-gradient-to-br from-indigo-500/10 to-purple-500/10 rounded-xl p-5 border border-indigo-500/30">
                <h4 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                  <MicrophoneIcon />
                  Practice Your Delivery
                </h4>
                <p className="text-xs text-slate-400 mb-4">
                  Tap the mic and speak. Recording will auto-stop when you pause, then analyze your delivery.
                </p>
                <VoicePracticeInput
                  sessionId="general"
                  placeholder="Tap the mic and start speaking..."
                  context={
                    practiceType === "opening" ? "opening_statement" :
                    practiceType === "closing" ? "closing_argument" :
                    practiceType === "direct" ? "direct_examination" :
                    practiceType === "cross" ? "cross_examination" :
                    practiceType === "objection" ? "objection" :
                    practiceType === "witness" ? "witness_interview" : "general"
                  }
                  showAnalysis={true}
                  autoSubmit={false}
                  silenceTimeout={2000}
                  onAnalysis={(analysis) => {
                    setPracticeHistory((prev) => [...prev, { type: practiceType, transcript: analysis.transcript, analysis }]);
                  }}
                />
              </div>

              {/* History */}
              {practiceHistory.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-slate-300">Practice History</h4>
                    <button onClick={() => setPracticeHistory([])} className="text-xs text-slate-500 hover:text-slate-300">Clear History</button>
                  </div>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {practiceHistory.slice().reverse().map((entry, i) => (
                      <div key={i} className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs text-indigo-400 capitalize">{entry.type.replace("_", " ")}</span>
                          <span className="text-xs text-slate-500">Score: {entry.analysis.clarity_score}/100 | WPM: {entry.analysis.words_per_minute}</span>
                        </div>
                        <p className="text-xs text-slate-400 line-clamp-2">{entry.transcript}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
