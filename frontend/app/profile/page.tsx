"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, API_BASE } from "@/lib/api";
import type { User } from "@supabase/supabase-js";

// =============================================================================
// TYPES
// =============================================================================

interface TranscriptHistoryItem {
  session_id: string;
  case_name: string;
  human_role: string;
  started_at: string;
  updated_at: string;
  entry_count: number;
  phases_completed: string[];
}

interface SessionScoreData {
  scores: Record<string, { side?: string; average?: number; name?: string }>;
}

interface ProfileStats {
  totalTrials: number;
  completedTrials: number;
  overallAvg: number;
  bestScore: number;
  prosAvg: number;
  defAvg: number;
  roleBreakdown: Record<string, number>;
  recentCases: string[];
}

const ROLE_LABELS: Record<string, string> = {
  attorney_plaintiff: "Plaintiff Attorney",
  attorney_defense: "Defense Attorney",
  witness: "Witness",
  spectator: "Spectator",
};

// =============================================================================
// PAGE
// =============================================================================

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<ProfileStats | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ current: "", new1: "", new2: "" });
  const [pwMsg, setPwMsg] = useState<string | null>(null);
  const [pwError, setPwError] = useState<string | null>(null);
  const [changingPw, setChangingPw] = useState(false);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getUser().then(({ data }) => {
      if (!data.user) { router.push("/login"); return; }
      setUser(data.user);
      setDisplayName(data.user.user_metadata?.display_name || data.user.email?.split("@")[0] || "");
    });
  }, [router]);

  const loadStats = useCallback(async () => {
    setLoading(true);
    try {
      const histResp = await apiFetch(`${API_BASE}/api/trial/transcripts/history`);
      if (!histResp.ok) { setLoading(false); return; }
      const { transcripts }: { transcripts: TranscriptHistoryItem[] } = await histResp.json();

      const roleBreakdown: Record<string, number> = {};
      const caseSet = new Set<string>();
      let completedCount = 0;
      transcripts.forEach((t) => {
        roleBreakdown[t.human_role] = (roleBreakdown[t.human_role] || 0) + 1;
        if (t.case_name) caseSet.add(t.case_name);
        const last = (t.phases_completed || []).slice(-1)[0]?.toLowerCase();
        if (last === "scoring" || last === "completed") completedCount++;
      });

      const allAvgs: number[] = [];
      const prosAvgs: number[] = [];
      const defAvgs: number[] = [];

      const top = transcripts.slice(0, 10);
      const scoreResults = await Promise.all(
        top.map((t) =>
          apiFetch(`${API_BASE}/api/scoring/${t.session_id}/live-scores`)
            .then((r) => (r.ok ? r.json() : null))
            .catch(() => null)
        )
      );
      scoreResults.forEach((sr: SessionScoreData | null) => {
        if (!sr?.scores) return;
        Object.values(sr.scores).forEach((s) => {
          if (s.average && s.average > 0) {
            allAvgs.push(s.average);
            if (s.side === "Prosecution") prosAvgs.push(s.average);
            if (s.side === "Defense") defAvgs.push(s.average);
          }
        });
      });

      setStats({
        totalTrials: transcripts.length,
        completedTrials: completedCount,
        overallAvg: allAvgs.length ? allAvgs.reduce((a, b) => a + b, 0) / allAvgs.length : 0,
        bestScore: allAvgs.length ? Math.max(...allAvgs) : 0,
        prosAvg: prosAvgs.length ? prosAvgs.reduce((a, b) => a + b, 0) / prosAvgs.length : 0,
        defAvg: defAvgs.length ? defAvgs.reduce((a, b) => a + b, 0) / defAvgs.length : 0,
        roleBreakdown,
        recentCases: Array.from(caseSet).slice(0, 5),
      });
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (user) loadStats(); }, [user, loadStats]);

  const handleSaveProfile = async () => {
    if (!user) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const sb = createClient();
      const { error } = await sb.auth.updateUser({ data: { display_name: displayName } });
      if (error) throw error;
      setSaveMsg("Profile updated successfully");
      setTimeout(() => setSaveMsg(null), 3000);
    } catch {
      setSaveMsg("Failed to update profile");
    } finally { setSaving(false); }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwMsg(null);
    setPwError(null);
    if (passwordForm.new1 !== passwordForm.new2) { setPwError("New passwords do not match"); return; }
    if (passwordForm.new1.length < 6) { setPwError("Password must be at least 6 characters"); return; }
    setChangingPw(true);
    try {
      const sb = createClient();
      const { error } = await sb.auth.updateUser({ password: passwordForm.new1 });
      if (error) throw error;
      setPwMsg("Password changed successfully");
      setPasswordForm({ current: "", new1: "", new2: "" });
      setTimeout(() => setPwMsg(null), 3000);
    } catch {
      setPwError("Failed to change password");
    } finally { setChangingPw(false); }
  };

  const handleLogout = async () => {
    const sb = createClient();
    await sb.auth.signOut();
    router.push("/login");
  };

  if (!user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
        <svg className="animate-spin w-8 h-8 text-slate-500" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
      </div>
    );
  }

  const joinDate = user.created_at ? new Date(user.created_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }) : "Unknown";
  const lastSignIn = user.last_sign_in_at ? new Date(user.last_sign_in_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Unknown";

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-0">
          <div className="flex items-center justify-between h-16">
            <button onClick={() => router.push("/")} className="flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                <svg viewBox="0 0 100 100" className="w-5 h-5" fill="none"><defs><linearGradient id="sg" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stopColor="#fbbf24" /><stop offset="100%" stopColor="#b45309" /></linearGradient></defs><rect x="35" y="85" width="30" height="8" rx="2" fill="url(#sg)" /><rect x="45" y="30" width="10" height="58" fill="url(#sg)" /><rect x="10" y="25" width="80" height="6" rx="2" fill="url(#sg)" /><circle cx="50" cy="20" r="8" fill="url(#sg)" /></svg>
              </div>
              <span className="text-base font-bold tracking-tight">MockPrep<span className="text-amber-400">AI</span></span>
            </button>
            <nav className="hidden md:flex items-center gap-1">
              <button onClick={() => router.push("/")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Dashboard</button>
              <button onClick={() => router.push("/about")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Who We Are</button>
              <button onClick={() => router.push("/contact")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Contact</button>
            </nav>
            <button onClick={handleLogout} className="px-3 py-1.5 text-xs text-slate-500 hover:text-red-400 border border-slate-700/50 hover:border-red-500/30 rounded-lg transition-colors">Sign Out</button>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Profile Header */}
        <div className="bg-gradient-to-r from-slate-800/80 via-indigo-900/20 to-slate-800/80 border border-slate-700/50 rounded-2xl p-8 mb-8">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-3xl font-bold shadow-xl shadow-indigo-500/20">
              {(user.email || "U")[0].toUpperCase()}
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-white">{displayName || user.email?.split("@")[0]}</h1>
              <p className="text-slate-400 text-sm mt-0.5">{user.email}</p>
              <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                <span>Joined {joinDate}</span>
                <span className="text-slate-700">&middot;</span>
                <span>Last sign-in: {lastSignIn}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* Trial Statistics */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6">
            <h2 className="text-lg font-bold text-white mb-5">Trial Statistics</h2>
            {loading ? (
              <div className="flex items-center justify-center py-8 text-slate-500 text-sm">
                <svg className="animate-spin w-5 h-5 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                Loading...
              </div>
            ) : stats ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-700/30 rounded-xl p-4 text-center">
                    <div className="text-2xl font-bold text-white">{stats.totalTrials}</div>
                    <div className="text-xs text-slate-500">Total Trials</div>
                  </div>
                  <div className="bg-slate-700/30 rounded-xl p-4 text-center">
                    <div className="text-2xl font-bold text-emerald-400">{stats.completedTrials}</div>
                    <div className="text-xs text-slate-500">Completed</div>
                  </div>
                  <div className="bg-slate-700/30 rounded-xl p-4 text-center">
                    <div className="text-2xl font-bold text-amber-400">{stats.overallAvg ? stats.overallAvg.toFixed(1) : "--"}</div>
                    <div className="text-xs text-slate-500">Avg Score</div>
                  </div>
                  <div className="bg-slate-700/30 rounded-xl p-4 text-center">
                    <div className="text-2xl font-bold text-blue-400">{stats.bestScore ? stats.bestScore.toFixed(1) : "--"}</div>
                    <div className="text-xs text-slate-500">Best Score</div>
                  </div>
                </div>

                {/* Side averages */}
                <div className="flex gap-3">
                  <div className="flex-1 bg-blue-500/10 border border-blue-500/15 rounded-xl p-3 text-center">
                    <div className="text-lg font-bold text-blue-300">{stats.prosAvg ? stats.prosAvg.toFixed(1) : "--"}</div>
                    <div className="text-xs text-slate-500">Prosecution Avg</div>
                  </div>
                  <div className="flex-1 bg-red-500/10 border border-red-500/15 rounded-xl p-3 text-center">
                    <div className="text-lg font-bold text-red-300">{stats.defAvg ? stats.defAvg.toFixed(1) : "--"}</div>
                    <div className="text-xs text-slate-500">Defense Avg</div>
                  </div>
                </div>

                {/* Role breakdown */}
                {Object.keys(stats.roleBreakdown).length > 0 && (
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Roles Played</div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(stats.roleBreakdown).map(([role, count]) => (
                        <span key={role} className="px-3 py-1.5 bg-slate-700/40 border border-slate-600/30 rounded-lg text-xs text-slate-300">
                          {ROLE_LABELS[role] || role}: <span className="font-bold text-white">{count}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recent cases */}
                {stats.recentCases.length > 0 && (
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Cases Practiced</div>
                    <div className="space-y-1">
                      {stats.recentCases.map((c, i) => (
                        <div key={i} className="text-sm text-slate-400 flex items-center gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                          {c}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500 text-center py-6">No trial data yet. Start your first trial!</p>
            )}
          </div>

          {/* Account Settings */}
          <div className="space-y-6">
            {/* Display Name */}
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6">
              <h2 className="text-lg font-bold text-white mb-4">Profile Settings</h2>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-1.5">Display Name</label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                    placeholder="Your name"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-1.5">Email</label>
                  <input
                    type="email"
                    value={user.email || ""}
                    disabled
                    className="w-full px-4 py-2.5 bg-slate-700/30 border border-slate-700/30 rounded-xl text-slate-500 text-sm cursor-not-allowed"
                  />
                </div>
                <button
                  onClick={handleSaveProfile}
                  disabled={saving}
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-xl text-sm font-medium transition-colors"
                >
                  {saving ? "Saving..." : "Save Changes"}
                </button>
                {saveMsg && <p className={`text-xs text-center ${saveMsg.includes("Failed") ? "text-red-400" : "text-emerald-400"}`}>{saveMsg}</p>}
              </div>
            </div>

            {/* Change Password */}
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6">
              <h2 className="text-lg font-bold text-white mb-4">Change Password</h2>
              <form onSubmit={handleChangePassword} className="space-y-3">
                <input
                  type="password"
                  value={passwordForm.new1}
                  onChange={(e) => setPasswordForm((p) => ({ ...p, new1: e.target.value }))}
                  className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                  placeholder="New password"
                />
                <input
                  type="password"
                  value={passwordForm.new2}
                  onChange={(e) => setPasswordForm((p) => ({ ...p, new2: e.target.value }))}
                  className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                  placeholder="Confirm new password"
                />
                <button
                  type="submit"
                  disabled={changingPw || !passwordForm.new1}
                  className="w-full py-2.5 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-xl text-sm font-medium transition-colors"
                >
                  {changingPw ? "Updating..." : "Update Password"}
                </button>
                {pwMsg && <p className="text-xs text-center text-emerald-400">{pwMsg}</p>}
                {pwError && <p className="text-xs text-center text-red-400">{pwError}</p>}
              </form>
            </div>

            {/* Danger Zone */}
            <div className="bg-red-500/5 border border-red-500/15 rounded-2xl p-6">
              <h2 className="text-lg font-bold text-red-300 mb-2">Danger Zone</h2>
              <p className="text-xs text-slate-500 mb-4">Sign out of your account or delete all session data.</p>
              <div className="flex gap-3">
                <button
                  onClick={handleLogout}
                  className="flex-1 py-2.5 bg-slate-700/50 hover:bg-slate-600/50 text-slate-300 rounded-xl text-sm font-medium transition-colors"
                >
                  Sign Out
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(!showDeleteConfirm)}
                  className="flex-1 py-2.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-xl text-sm font-medium transition-colors"
                >
                  Delete Account
                </button>
              </div>
              {showDeleteConfirm && (
                <div className="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
                  <p className="text-xs text-red-300 mb-2">Contact support to delete your account and all associated data.</p>
                  <button onClick={() => setShowDeleteConfirm(false)} className="text-xs text-slate-500 hover:text-slate-400">Dismiss</button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
