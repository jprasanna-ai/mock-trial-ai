"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, API_BASE } from "@/lib/api";

interface TestResult {
  name: string;
  passed: boolean;
  duration_ms: number;
  details: string;
  category: string;
}

interface TestReport {
  total: number;
  passed: number;
  failed: number;
  duration_ms: number;
  results: TestResult[];
}

const CATEGORY_META: Record<string, { label: string; icon: string; color: string }> = {
  infrastructure: { label: "Infrastructure", icon: "🏗️", color: "text-slate-400" },
  case_management: { label: "Case Management", icon: "📁", color: "text-blue-400" },
  session: { label: "Session", icon: "🔗", color: "text-purple-400" },
  trial_flow: { label: "Trial Flow", icon: "⚖️", color: "text-amber-400" },
  scoring: { label: "Scoring", icon: "📊", color: "text-emerald-400" },
  audio: { label: "Audio / TTS", icon: "🔊", color: "text-cyan-400" },
  objections: { label: "Objections", icon: "🙋", color: "text-red-400" },
};

export default function TestSuitePage() {
  const router = useRouter();
  const [isRunning, setIsRunning] = useState(false);
  const [report, setReport] = useState<TestReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);

  const runTests = useCallback(async () => {
    setIsRunning(true);
    setError(null);
    setReport(null);
    try {
      const body = selectedCategories.length > 0
        ? JSON.stringify(selectedCategories)
        : null;
      const res = await apiFetch(`${API_BASE}/api/tests/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      if (!res.ok) throw new Error(`Server responded ${res.status}`);
      const data: TestReport = await res.json();
      setReport(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setIsRunning(false);
    }
  }, [selectedCategories]);

  const toggleCategory = (cat: string) => {
    setSelectedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const grouped = report
    ? report.results.reduce<Record<string, TestResult[]>>((acc, r) => {
        (acc[r.category] = acc[r.category] || []).push(r);
        return acc;
      }, {})
    : {};

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 text-white">
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/")}
              className="text-slate-400 hover:text-white transition-colors text-sm"
            >
              ← Home
            </button>
            <div className="h-6 w-px bg-slate-700" />
            <span className="text-xl">🧪</span>
            <h1 className="text-lg font-bold">Automated Test Suite</h1>
          </div>
          <button
            onClick={runTests}
            disabled={isRunning}
            className="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:from-slate-700 disabled:to-slate-700 text-white font-medium rounded-xl transition-all flex items-center gap-2"
          >
            {isRunning ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Running Tests...
              </>
            ) : (
              <>
                <span>▶</span> Run All Tests
              </>
            )}
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Category filters */}
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-4">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Filter by Category (leave empty for all)</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(CATEGORY_META).map(([key, meta]) => {
              const active = selectedCategories.includes(key);
              return (
                <button
                  key={key}
                  onClick={() => toggleCategory(key)}
                  className={`px-3 py-1.5 text-xs rounded-lg border transition-colors flex items-center gap-1.5 ${
                    active
                      ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300"
                      : "bg-slate-700/30 border-slate-600/30 text-slate-400 hover:border-slate-500"
                  }`}
                >
                  <span>{meta.icon}</span>
                  {meta.label}
                </button>
              );
            })}
          </div>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-300 text-sm">
            Failed to run tests: {error}
          </div>
        )}

        {/* Running animation */}
        {isRunning && (
          <div className="bg-slate-800/50 border border-blue-500/30 rounded-2xl p-8 text-center">
            <div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-blue-300 font-medium">Running test suite...</p>
            <p className="text-xs text-slate-500 mt-2">
              Some tests create sessions which may take up to 90 seconds to initialise
            </p>
          </div>
        )}

        {/* Report summary */}
        {report && (
          <>
            <div className={`rounded-2xl p-6 border ${
              report.failed === 0
                ? "bg-emerald-500/10 border-emerald-500/30"
                : "bg-amber-500/10 border-amber-500/30"
            }`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{report.failed === 0 ? "✅" : "⚠️"}</span>
                  <div>
                    <h2 className="text-lg font-bold">
                      {report.failed === 0 ? "All Tests Passed!" : `${report.failed} Test(s) Failed`}
                    </h2>
                    <p className="text-sm text-slate-400">
                      {report.passed}/{report.total} passed in {(report.duration_ms / 1000).toFixed(1)}s
                    </p>
                  </div>
                </div>
                <div className="flex gap-4 text-center">
                  <div>
                    <div className="text-2xl font-bold text-emerald-400">{report.passed}</div>
                    <div className="text-[10px] text-slate-500 uppercase">Passed</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-red-400">{report.failed}</div>
                    <div className="text-[10px] text-slate-500 uppercase">Failed</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-slate-300">{report.total}</div>
                    <div className="text-[10px] text-slate-500 uppercase">Total</div>
                  </div>
                </div>
              </div>

              {/* Pass rate bar */}
              <div className="w-full bg-slate-700/50 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${
                    report.failed === 0 ? "bg-emerald-500" : "bg-amber-500"
                  }`}
                  style={{ width: `${(report.passed / report.total) * 100}%` }}
                />
              </div>
            </div>

            {/* Results by category */}
            <div className="space-y-4">
              {Object.entries(grouped).map(([category, results]) => {
                const meta = CATEGORY_META[category] || {
                  label: category, icon: "📋", color: "text-slate-400",
                };
                const catPassed = results.filter((r) => r.passed).length;
                return (
                  <div
                    key={category}
                    className="bg-slate-800/50 border border-slate-700/50 rounded-2xl overflow-hidden"
                  >
                    <div className="px-5 py-3 border-b border-slate-700/50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span>{meta.icon}</span>
                        <span className={`font-medium text-sm ${meta.color}`}>{meta.label}</span>
                      </div>
                      <span className="text-xs text-slate-500">
                        {catPassed}/{results.length} passed
                      </span>
                    </div>
                    <div className="divide-y divide-slate-700/30">
                      {results.map((r, i) => (
                        <div
                          key={i}
                          className="px-5 py-3 flex items-start gap-3"
                        >
                          <span className="mt-0.5 text-base">
                            {r.passed ? "✅" : "❌"}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-white">{r.name}</span>
                              <span className="text-[10px] text-slate-500">
                                {r.duration_ms.toFixed(0)}ms
                              </span>
                            </div>
                            <p className={`text-xs mt-0.5 ${
                              r.passed ? "text-slate-400" : "text-red-400"
                            }`}>
                              {r.details}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* Empty state */}
        {!report && !isRunning && !error && (
          <div className="bg-slate-800/30 border border-slate-700/30 rounded-2xl p-12 text-center">
            <span className="text-5xl block mb-4">🧪</span>
            <h2 className="text-lg font-medium text-slate-300 mb-2">Ready to Test</h2>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              The test suite validates all major features: session management, trial flow,
              TTS audio, objection detection, scoring, and more.
              Click &ldquo;Run All Tests&rdquo; to begin.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
