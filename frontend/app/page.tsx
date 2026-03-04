/**
 * Homepage
 * 
 * Per ARCHITECTURE.md Section 1:
 * - Frontend responsible for UI rendering
 * - All trial logic handled by backend
 */

"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
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

// =============================================================================
// SVG ILLUSTRATIONS
// =============================================================================

const CourthouseIllustration = () => (
  <svg viewBox="0 0 400 300" className="w-full h-auto" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Sky gradient */}
    <defs>
      <linearGradient id="skyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#1e3a5f" />
        <stop offset="100%" stopColor="#0f172a" />
      </linearGradient>
      <linearGradient id="buildingGradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#e2e8f0" />
        <stop offset="100%" stopColor="#94a3b8" />
      </linearGradient>
      <linearGradient id="goldGradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#fbbf24" />
        <stop offset="100%" stopColor="#d97706" />
      </linearGradient>
    </defs>
    
    {/* Background */}
    <rect width="400" height="300" fill="url(#skyGradient)" />
    
    {/* Stars */}
    {[...Array(20)].map((_, i) => (
      <circle
        key={i}
        cx={30 + (i * 19) % 340}
        cy={20 + (i * 7) % 80}
        r={0.5 + (i % 3) * 0.3}
        fill="white"
        opacity={0.3 + (i % 5) * 0.15}
      />
    ))}
    
    {/* Moon */}
    <circle cx="340" cy="50" r="25" fill="#fef3c7" opacity="0.9" />
    <circle cx="350" cy="45" r="22" fill="url(#skyGradient)" />
    
    {/* Courthouse base */}
    <rect x="80" y="150" width="240" height="130" fill="url(#buildingGradient)" />
    
    {/* Columns */}
    {[100, 150, 200, 250, 300].map((x, i) => (
      <g key={i}>
        <rect x={x} y="160" width="16" height="90" fill="#f1f5f9" />
        <rect x={x - 2} y="155" width="20" height="8" fill="#e2e8f0" />
        <rect x={x - 2} y="248" width="20" height="8" fill="#e2e8f0" />
      </g>
    ))}
    
    {/* Pediment (triangle roof) */}
    <polygon points="200,100 70,155 330,155" fill="url(#buildingGradient)" />
    <polygon points="200,110 90,152 310,152" fill="#f8fafc" />
    
    {/* Justice symbol in pediment */}
    <circle cx="200" cy="132" r="12" fill="url(#goldGradient)" />
    <rect x="197" y="125" width="6" height="20" fill="#92400e" />
    <rect x="188" y="128" width="24" height="3" fill="#92400e" />
    
    {/* Doors */}
    <rect x="175" y="220" width="50" height="60" fill="#1e293b" rx="3" />
    <rect x="180" y="225" width="18" height="50" fill="#334155" rx="2" />
    <rect x="202" y="225" width="18" height="50" fill="#334155" rx="2" />
    <circle cx="196" cy="250" r="2" fill="url(#goldGradient)" />
    <circle cx="204" cy="250" r="2" fill="url(#goldGradient)" />
    
    {/* Steps */}
    <rect x="60" y="280" width="280" height="8" fill="#cbd5e1" />
    <rect x="70" y="272" width="260" height="8" fill="#e2e8f0" />
    <rect x="80" y="264" width="240" height="8" fill="#f1f5f9" />
    
    {/* Windows */}
    {[110, 270].map((x, i) => (
      <g key={i}>
        <rect x={x} y="180" width="30" height="40" fill="#1e293b" rx="2" />
        <rect x={x + 3} y="183" width="11" height="34" fill="#334155" opacity="0.7" />
        <rect x={x + 16} y="183" width="11" height="34" fill="#334155" opacity="0.7" />
        <rect x={x + 3} y="183" width="24" height="2" fill="#fef3c7" opacity="0.3" />
      </g>
    ))}
    
    {/* Flag */}
    <rect x="335" y="90" width="3" height="70" fill="#64748b" />
    <rect x="338" y="92" width="30" height="20" fill="#dc2626" />
    <rect x="338" y="97" width="30" height="4" fill="white" />
    <rect x="338" y="105" width="30" height="4" fill="white" />
    <rect x="338" y="92" width="12" height="11" fill="#1e3a8a" />
  </svg>
);

const ScalesOfJusticeIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 100 100" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="scaleGold" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#fbbf24" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
    </defs>
    {/* Base */}
    <rect x="35" y="85" width="30" height="8" rx="2" fill="url(#scaleGold)" />
    <rect x="45" y="30" width="10" height="58" fill="url(#scaleGold)" />
    {/* Top beam */}
    <rect x="10" y="25" width="80" height="6" rx="2" fill="url(#scaleGold)" />
    {/* Center ornament */}
    <circle cx="50" cy="20" r="8" fill="url(#scaleGold)" />
    <circle cx="50" cy="20" r="4" fill="#fef3c7" />
    {/* Left chain */}
    <line x1="20" y1="31" x2="20" y2="50" stroke="#d97706" strokeWidth="2" />
    {/* Right chain */}
    <line x1="80" y1="31" x2="80" y2="45" stroke="#d97706" strokeWidth="2" />
    {/* Left pan */}
    <ellipse cx="20" cy="55" rx="15" ry="5" fill="url(#scaleGold)" />
    <path d="M5 55 Q20 70 35 55" fill="url(#scaleGold)" />
    {/* Right pan (higher) */}
    <ellipse cx="80" cy="50" rx="15" ry="5" fill="url(#scaleGold)" />
    <path d="M65 50 Q80 65 95 50" fill="url(#scaleGold)" />
  </svg>
);

const GavelIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 100 100" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="woodGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#92400e" />
        <stop offset="50%" stopColor="#78350f" />
        <stop offset="100%" stopColor="#451a03" />
      </linearGradient>
      <linearGradient id="metalGradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#d4d4d8" />
        <stop offset="100%" stopColor="#71717a" />
      </linearGradient>
    </defs>
    {/* Sound block */}
    <ellipse cx="70" cy="75" rx="25" ry="8" fill="url(#woodGradient)" />
    <rect x="45" y="65" width="50" height="10" rx="2" fill="url(#woodGradient)" />
    {/* Handle */}
    <rect x="15" y="35" width="45" height="8" rx="2" fill="url(#woodGradient)" transform="rotate(-30 35 40)" />
    {/* Gavel head */}
    <rect x="5" y="15" width="30" height="18" rx="4" fill="url(#woodGradient)" transform="rotate(-30 20 24)" />
    {/* Metal bands */}
    <rect x="8" y="18" width="4" height="12" rx="1" fill="url(#metalGradient)" transform="rotate(-30 10 24)" />
    <rect x="28" y="18" width="4" height="12" rx="1" fill="url(#metalGradient)" transform="rotate(-30 30 24)" />
  </svg>
);

const MicrophoneIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 100 100" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="micGradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#3b82f6" />
        <stop offset="100%" stopColor="#1d4ed8" />
      </linearGradient>
    </defs>
    {/* Mic body */}
    <rect x="35" y="15" width="30" height="45" rx="15" fill="url(#micGradient)" />
    {/* Mic grille */}
    {[25, 32, 39, 46].map((y, i) => (
      <line key={i} x1="42" y1={y} x2="58" y2={y} stroke="#1e40af" strokeWidth="2" opacity="0.5" />
    ))}
    {/* Stand arc */}
    <path d="M25 55 Q25 80 50 80 Q75 80 75 55" stroke="#6b7280" strokeWidth="4" fill="none" />
    {/* Stand pole */}
    <rect x="47" y="80" width="6" height="12" fill="#6b7280" />
    {/* Base */}
    <ellipse cx="50" cy="95" rx="18" ry="4" fill="#4b5563" />
  </svg>
);

const DocumentIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 100 100" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="paperGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#fef9c3" />
        <stop offset="100%" stopColor="#fde68a" />
      </linearGradient>
    </defs>
    {/* Back paper */}
    <rect x="25" y="8" width="55" height="70" rx="3" fill="#d4d4d8" />
    {/* Middle paper */}
    <rect x="20" y="13" width="55" height="70" rx="3" fill="#e5e7eb" />
    {/* Front paper */}
    <rect x="15" y="18" width="55" height="70" rx="3" fill="url(#paperGradient)" />
    {/* Lines */}
    {[30, 40, 50, 60, 70].map((y, i) => (
      <line key={i} x1="25" y1={y} x2={i === 4 ? 45 : 60} y2={y} stroke="#92400e" strokeWidth="2" opacity="0.3" />
    ))}
    {/* Seal */}
    <circle cx="55" cy="75" r="10" fill="#dc2626" opacity="0.8" />
    <circle cx="55" cy="75" r="6" fill="#fef2f2" opacity="0.5" />
  </svg>
);

const AttorneyIllustration = ({ side }: { side: "plaintiff" | "defense" }) => (
  <svg viewBox="0 0 80 100" className="w-full h-auto" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Head */}
    <circle cx="40" cy="25" r="15" fill="#fcd5b8" />
    {/* Hair */}
    <path 
      d={side === "plaintiff" 
        ? "M25 20 Q25 8 40 8 Q55 8 55 20 Q55 15 40 15 Q25 15 25 20" 
        : "M28 18 Q28 10 40 10 Q52 10 52 18 L52 22 Q52 18 40 18 Q28 18 28 22 Z"
      }
      fill={side === "plaintiff" ? "#451a03" : "#1f2937"}
    />
    {/* Suit */}
    <path 
      d="M20 45 L25 100 L55 100 L60 45 Q60 35 40 35 Q20 35 20 45" 
      fill={side === "plaintiff" ? "#1e3a8a" : "#1f2937"}
    />
    {/* Shirt/tie */}
    <polygon points="35,40 40,70 45,40" fill={side === "plaintiff" ? "#dc2626" : "#1e3a8a"} />
    <polygon points="33,38 40,45 47,38" fill="white" />
    {/* Lapels */}
    <path d="M32 40 L25 55 L32 50 Z" fill={side === "plaintiff" ? "#1e40af" : "#374151"} />
    <path d="M48 40 L55 55 L48 50 Z" fill={side === "plaintiff" ? "#1e40af" : "#374151"} />
    {/* Face features */}
    <circle cx="35" cy="23" r="2" fill="#451a03" />
    <circle cx="45" cy="23" r="2" fill="#451a03" />
    <path d="M36 30 Q40 33 44 30" stroke="#92400e" strokeWidth="1.5" fill="none" />
    {/* Briefcase */}
    <rect x="58" y="70" width="18" height="14" rx="2" fill="#78350f" />
    <rect x="64" y="68" width="6" height="4" rx="1" fill="#92400e" />
  </svg>
);

const WitnessIllustration = () => (
  <svg viewBox="0 0 100 100" className="w-full h-auto" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Witness stand */}
    <rect x="20" y="50" width="60" height="45" fill="#78350f" rx="3" />
    <rect x="18" y="48" width="64" height="5" fill="#92400e" rx="2" />
    {/* Wood grain */}
    <line x1="25" y1="60" x2="75" y2="60" stroke="#451a03" strokeWidth="1" opacity="0.3" />
    <line x1="25" y1="75" x2="75" y2="75" stroke="#451a03" strokeWidth="1" opacity="0.3" />
    {/* Person */}
    <circle cx="50" cy="28" r="14" fill="#e0c8a8" />
    {/* Hair */}
    <ellipse cx="50" cy="18" rx="12" ry="8" fill="#6b7280" />
    {/* Face */}
    <circle cx="45" cy="26" r="2" fill="#374151" />
    <circle cx="55" cy="26" r="2" fill="#374151" />
    <path d="M46 33 Q50 35 54 33" stroke="#78350f" strokeWidth="1.5" fill="none" />
    {/* Shoulders/shirt */}
    <path d="M30 55 Q30 42 50 40 Q70 42 70 55" fill="#60a5fa" />
    {/* Microphone */}
    <rect x="72" y="35" width="4" height="20" fill="#374151" />
    <ellipse cx="74" cy="33" rx="5" ry="7" fill="#1f2937" />
  </svg>
);

// =============================================================================
// API CONFIG
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// =============================================================================
// PAGE COMPONENT
// =============================================================================

export default function HomePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getUser().then(({ data }) => setUser(data.user));
  }, []);

  const handleLogout = async () => {
    const sb = createClient();
    await sb.auth.signOut();
    router.push("/login");
  };

  const [cases, setCases] = useState<CaseMetadata[]>([]);
  const [featuredCases, setFeaturedCases] = useState<CaseMetadata[]>([]);
  const [selectedCase, setSelectedCase] = useState<string>("");
  const [selectedRole, setSelectedRole] = useState<Role>("attorney_plaintiff");
  const [selectedSubRole, setSelectedSubRole] = useState<"opening" | "direct_cross" | "closing">("direct_cross");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingCases, setIsLoadingCases] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadCases() {
      try {
        // Fetch homepage cases (favorites + recent + featured) and all demo cases
        const [homepageRes, demoRes] = await Promise.all([
          fetch(`${API_BASE}/api/case/user/homepage`),
          fetch(`${API_BASE}/api/case/demo`),
        ]);
        
        if (homepageRes.ok) {
          const homepage = await homepageRes.json();
          const homepageCases = homepage.cases || [];
          setFeaturedCases(homepageCases);
          if (homepageCases.length > 0) {
            setSelectedCase(homepageCases[0].id);
          }
        } else {
          // Fallback to featured endpoint
          const featuredRes = await fetch(`${API_BASE}/api/case/featured?limit=3`);
          if (featuredRes.ok) {
            const featured = await featuredRes.json();
            setFeaturedCases(featured || []);
            if (featured?.length > 0) {
              setSelectedCase(featured[0].id);
            }
          }
        }
        
        if (demoRes.ok) {
          const demoCases = await demoRes.json();
          setCases(demoCases || []);
          if (!featuredCases.length && demoCases?.length > 0) {
            setSelectedCase(demoCases[0].id);
          }
        }
      } catch {
        console.log("Failed to load cases from API");
      } finally {
        setIsLoadingCases(false);
      }
    }
    loadCases();
  }, []);

  const handleStartTrial = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const sessionResponse = await fetch(`${API_BASE}/api/session/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: selectedCase || undefined,
          human_role: selectedRole,
          attorney_sub_role: (selectedRole === "attorney_plaintiff" || selectedRole === "attorney_defense") ? selectedSubRole : undefined,
        }),
      });

      if (!sessionResponse.ok) {
        throw new Error("Failed to create session");
      }

      const sessionData = await sessionResponse.json();
      const sessionId = sessionData.session_id;

      // Fire initialization without blocking navigation — the courtroom page
      // polls for readiness and shows a loading state until initialized.
      fetch(`${API_BASE}/api/session/${sessionId}/initialize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }).catch((err) => console.error("Background initialization error:", err));

      router.push(`/courtroom/${sessionId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start trial");
      setIsLoading(false);
    }
  };

  const roleOptions: { value: Role; label: string; description: string; illustration: React.ReactNode }[] = [
    {
      value: "attorney_plaintiff",
      label: "Plaintiff Attorney",
      description: "Represent the prosecution side and present your case",
      illustration: <AttorneyIllustration side="plaintiff" />,
    },
    {
      value: "attorney_defense",
      label: "Defense Attorney",
      description: "Defend against the charges and cross-examine witnesses",
      illustration: <AttorneyIllustration side="defense" />,
    },
    {
      value: "witness",
      label: "Witness",
      description: "Take the stand and respond to examination",
      illustration: <WitnessIllustration />,
    },
    {
      value: "spectator",
      label: "Spectator",
      description: "Watch a full AI vs AI trial unfold without participating",
      illustration: (
        <svg viewBox="0 0 96 96" className="w-full h-full p-4">
          <circle cx="48" cy="40" r="20" fill="none" stroke="currentColor" strokeWidth="3" className="text-amber-400" />
          <circle cx="48" cy="40" r="8" fill="currentColor" className="text-amber-400" />
          <path d="M12 40 C 12 20, 84 20, 84 40 C 84 60, 12 60, 12 40Z" fill="none" stroke="currentColor" strokeWidth="3" className="text-amber-300" />
          <text x="48" y="78" textAnchor="middle" fill="currentColor" className="text-slate-400" fontSize="10" fontWeight="bold">WATCH</text>
        </svg>
      ),
    },
  ];

  const difficultyColors = {
    beginner: "bg-emerald-100 text-emerald-800 border-emerald-200",
    intermediate: "bg-amber-100 text-amber-800 border-amber-200",
    advanced: "bg-rose-100 text-rose-800 border-rose-200",
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-800 to-indigo-950">
      {/* Animated background elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-10 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-500/5 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative z-20 border-b border-slate-700/50 bg-slate-900/60 backdrop-blur-sm sticky top-0">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <button
              onClick={() => router.push("/")}
              className="flex items-center gap-2 text-white hover:text-amber-300 transition-colors"
            >
              <ScalesOfJusticeIcon className="w-6 h-6 text-amber-400" />
              <span className="text-lg font-bold">AI Mock Trial</span>
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={() => router.push("/cases")}
                className="flex items-center gap-2 px-4 py-2 text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors"
              >
                <DocumentIcon className="w-5 h-5" />
                <span className="hidden sm:inline">Case Library</span>
              </button>
              <button
                onClick={() => router.push("/history")}
                className="flex items-center gap-2 px-3 py-2 text-slate-400 hover:text-sky-300 hover:bg-slate-800/50 rounded-lg transition-colors text-sm"
                title="View past trial transcripts"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span className="hidden sm:inline">History</span>
              </button>
              <button
                onClick={() => router.push("/tests")}
                className="flex items-center gap-2 px-3 py-2 text-slate-400 hover:text-emerald-300 hover:bg-slate-800/50 rounded-lg transition-colors text-sm"
                title="Run automated test suite"
              >
                <span>🧪</span>
                <span className="hidden sm:inline">Tests</span>
              </button>
              {user && (
                <div className="flex items-center gap-2 ml-2 pl-2 border-l border-slate-700/50">
                  <span className="text-sm text-slate-400 hidden sm:inline">{user.email}</span>
                  <button
                    onClick={handleLogout}
                    className="px-3 py-1.5 text-xs text-slate-400 hover:text-red-400 hover:bg-slate-800/50 rounded-lg transition-colors"
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="relative z-10">
        {/* Hero Section */}
        <div className="max-w-7xl mx-auto px-4 pt-8 pb-16">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: Text content */}
            <div className="text-center lg:text-left">
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-500/20 to-purple-500/20 border border-blue-400/30 rounded-full text-blue-300 text-sm mb-6 backdrop-blur-sm">
                <ScalesOfJusticeIcon className="w-5 h-5" />
                AI-Powered Legal Practice Platform
              </div>
              
              <h1 className="text-5xl lg:text-6xl font-bold mb-6">
                <span className="bg-gradient-to-r from-white via-blue-100 to-purple-200 bg-clip-text text-transparent">
                  Master the Art of
                </span>
                <br />
                <span className="bg-gradient-to-r from-amber-300 via-yellow-200 to-amber-400 bg-clip-text text-transparent">
                  Trial Advocacy
                </span>
              </h1>
              
              <p className="text-xl text-slate-300 mb-8 max-w-xl mx-auto lg:mx-0">
                Practice with AI attorneys, witnesses, and judges. Receive real-time 
                feedback and scoring to sharpen your courtroom skills.
              </p>

              {/* Quick stats */}
              <div className="flex flex-wrap justify-center lg:justify-start gap-6 mb-8">
                <div className="flex items-center gap-2">
                  <MicrophoneIcon className="w-8 h-8" />
                  <div className="text-left">
                    <div className="text-white font-semibold">Voice-First</div>
                    <div className="text-slate-400 text-sm">Speak naturally</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <GavelIcon className="w-8 h-8" />
                  <div className="text-left">
                    <div className="text-white font-semibold">Real Trials</div>
                    <div className="text-slate-400 text-sm">Full proceedings</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <DocumentIcon className="w-8 h-8" />
                  <div className="text-left">
                    <div className="text-white font-semibold">Scored</div>
                    <div className="text-slate-400 text-sm">Expert feedback</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Courthouse illustration */}
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent z-10 pointer-events-none" />
              <div className="rounded-2xl overflow-hidden shadow-2xl shadow-blue-500/20 border border-slate-700/50">
                <CourthouseIllustration />
              </div>
              {/* Floating elements */}
              <div className="absolute -top-4 -right-4 w-20 h-20 bg-gradient-to-br from-amber-400 to-amber-600 rounded-2xl shadow-lg flex items-center justify-center rotate-12 animate-bounce" style={{ animationDuration: "3s" }}>
                <ScalesOfJusticeIcon className="w-12 h-12" />
              </div>
              <div className="absolute -bottom-4 -left-4 w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl shadow-lg flex items-center justify-center -rotate-12">
                <GavelIcon className="w-10 h-10" />
              </div>
            </div>
          </div>
        </div>

        {/* Role Selection Section */}
        <div className="max-w-6xl mx-auto px-4 pb-16">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-white mb-3">Choose Your Role</h2>
            <p className="text-slate-400">Select how you want to participate in the trial</p>
          </div>

          <div className="grid md:grid-cols-4 gap-6 mb-12">
            {roleOptions.map((role) => (
              <button
                key={role.value}
                onClick={() => setSelectedRole(role.value)}
                className={`group relative overflow-hidden rounded-2xl transition-all duration-300 ${
                  selectedRole === role.value
                    ? "ring-4 ring-blue-400 ring-offset-4 ring-offset-slate-900 scale-105"
                    : "hover:scale-102 hover:ring-2 hover:ring-slate-600"
                }`}
              >
                {/* Card background */}
                <div className={`absolute inset-0 transition-opacity ${
                  selectedRole === role.value 
                    ? "bg-gradient-to-br from-blue-600 to-indigo-700" 
                    : "bg-gradient-to-br from-slate-800 to-slate-900"
                }`} />
                
                {/* Card content */}
                <div className="relative p-6">
                  {/* Illustration */}
                  <div className={`w-24 h-24 mx-auto mb-4 rounded-xl overflow-hidden ${
                    selectedRole === role.value ? "bg-white/10" : "bg-slate-700/50"
                  }`}>
                    {role.illustration}
                  </div>
                  
                  {/* Text */}
                  <h3 className={`text-xl font-bold mb-2 ${
                    selectedRole === role.value ? "text-white" : "text-slate-200"
                  }`}>
                    {role.label}
                  </h3>
                  <p className={`text-sm ${
                    selectedRole === role.value ? "text-blue-100" : "text-slate-400"
                  }`}>
                    {role.description}
                  </p>

                  {/* Selected indicator */}
                  {selectedRole === role.value && (
                    <div className="absolute top-4 right-4 w-8 h-8 bg-white rounded-full flex items-center justify-center shadow-lg">
                      <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>

          {/* Attorney Sub-Role Selection - only for attorney roles */}
          {(selectedRole === "attorney_plaintiff" || selectedRole === "attorney_defense") && (
            <div className="max-w-4xl mx-auto mb-8">
              <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-6">
                <h3 className="text-lg font-semibold text-white mb-1">Attorney Specialization</h3>
                <p className="text-slate-400 text-sm mb-4">Pick which attorney role you want to play. AI teammates will handle the others.</p>
                <div className="grid md:grid-cols-3 gap-3">
                  {[
                    {
                      value: "opening" as const,
                      label: "Opening Attorney",
                      desc: "Delivers the opening statement and sets the narrative",
                      icon: "\uD83D\uDCE2",
                    },
                    {
                      value: "direct_cross" as const,
                      label: "Direct/Cross Attorney",
                      desc: "Examines witnesses, makes objections, argues evidence",
                      icon: "\uD83D\uDD0D",
                    },
                    {
                      value: "closing" as const,
                      label: "Closing Attorney",
                      desc: "Delivers the closing argument and connects evidence to law",
                      icon: "\uD83C\uDFC6",
                    },
                  ].map((role) => (
                    <button
                      key={role.value}
                      onClick={() => setSelectedSubRole(role.value)}
                      className={`p-4 rounded-xl border-2 transition-all text-left ${
                        selectedSubRole === role.value
                          ? "border-emerald-500 bg-emerald-500/10"
                          : "border-slate-600 bg-slate-700/30 hover:border-slate-500"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg">{role.icon}</span>
                        <span className={`font-semibold text-sm ${selectedSubRole === role.value ? "text-emerald-300" : "text-slate-200"}`}>
                          {role.label}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400">{role.desc}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Spectator mode info */}
          {selectedRole === "spectator" && (
            <div className="max-w-4xl mx-auto mb-8">
              <div className="bg-amber-500/10 backdrop-blur-sm rounded-2xl border border-amber-500/20 p-6">
                <h3 className="text-lg font-semibold text-amber-300 mb-2">Spectator Mode</h3>
                <p className="text-slate-400 text-sm">
                  All roles will be handled by AI agents. You will watch the entire trial proceeding
                  without participating &mdash; both prosecution and defense teams are fully AI-controlled.
                  Just select a case below and click Start Trial.
                </p>
              </div>
            </div>
          )}

          {/* Featured Cases Selection */}
          <div className="max-w-4xl mx-auto">
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-6 mb-8">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-semibold text-white flex items-center gap-2">
                  <DocumentIcon className="w-6 h-6" />
                  Popular Practice Cases
                </h3>
                <div className="flex items-center gap-4">
                  {isLoadingCases && (
                    <div className="flex items-center gap-2 text-slate-400 text-sm">
                      <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Loading...
                    </div>
                  )}
                  <button
                    onClick={() => router.push("/cases")}
                    className="flex items-center gap-1 text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    Browse all {cases.length} cases
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>
              
              {(featuredCases.length > 0 ? featuredCases : cases.slice(0, 3)).length > 0 ? (
                <div className="grid gap-4">
                  {(featuredCases.length > 0 ? featuredCases : cases.slice(0, 3)).map((caseItem) => (
                    <button
                      key={caseItem.id}
                      onClick={() => setSelectedCase(caseItem.id)}
                      className={`group relative w-full text-left transition-all duration-300 rounded-xl overflow-hidden ${
                        selectedCase === caseItem.id
                          ? "ring-2 ring-blue-400 ring-offset-2 ring-offset-slate-900"
                          : "hover:ring-1 hover:ring-slate-600"
                      }`}
                    >
                      {/* Background gradient based on case type */}
                      <div className={`absolute inset-0 ${
                        caseItem.case_type === "criminal" 
                          ? "bg-gradient-to-r from-red-900/30 to-slate-800/50"
                          : "bg-gradient-to-r from-blue-900/30 to-slate-800/50"
                      }`} />
                      
                      <div className="relative p-5">
                        <div className="flex items-start gap-4">
                          {/* Case type icon */}
                          <div className={`flex-shrink-0 w-14 h-14 rounded-xl flex items-center justify-center ${
                            caseItem.case_type === "criminal"
                              ? "bg-red-500/20"
                              : "bg-blue-500/20"
                          }`}>
                            {caseItem.case_type === "criminal" ? (
                              <GavelIcon className="w-8 h-8" />
                            ) : (
                              <ScalesOfJusticeIcon className="w-8 h-8" />
                            )}
                          </div>
                          
                          {/* Case details */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-4">
                              <div>
                                <h4 className="text-lg font-semibold text-white group-hover:text-blue-300 transition-colors">
                                  {caseItem.title}
                                </h4>
                                <p className="text-sm text-slate-400 mt-1 line-clamp-2">
                                  {caseItem.description}
                                </p>
                              </div>
                              
                              {/* Badges */}
                              <div className="flex flex-col items-end gap-2 flex-shrink-0">
                                {caseItem.featured && (
                                  <span className="px-2 py-1 bg-amber-500/20 text-amber-300 text-xs rounded-full border border-amber-500/30 flex items-center gap-1">
                                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                    </svg>
                                    Popular
                                  </span>
                                )}
                                {caseItem.difficulty && (
                                  <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${difficultyColors[caseItem.difficulty] || difficultyColors.intermediate}`}>
                                    {caseItem.difficulty.charAt(0).toUpperCase() + caseItem.difficulty.slice(1)}
                                  </span>
                                )}
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                  caseItem.case_type === "criminal"
                                    ? "bg-red-500/20 text-red-300 border border-red-500/30"
                                    : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                                }`}>
                                  {caseItem.case_type === "criminal" ? "Criminal" : "Civil"}
                                </span>
                              </div>
                            </div>
                            
                            {/* Stats */}
                            <div className="flex items-center gap-4 mt-3">
                              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                                </svg>
                                <span>{caseItem.witness_count || 4} Witnesses</span>
                              </div>
                              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                <span>{caseItem.exhibit_count || 5} Exhibits</span>
                              </div>
                              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                                <span>{caseItem.year}</span>
                              </div>
                            </div>
                          </div>
                          
                          {/* Selection indicator */}
                          {selectedCase === caseItem.id && (
                            <div className="absolute top-3 right-3 w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center shadow-lg">
                              <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                            </div>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : !isLoadingCases ? (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center">
                      <DocumentIcon className="w-7 h-7" />
                    </div>
                    <div>
                      <div className="font-semibold text-amber-200 text-lg">No Cases Available</div>
                      <div className="text-sm text-amber-300/70 mt-1">
                        Please ensure the backend server is running. Demo cases will appear here automatically.
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>

            {/* Error Display */}
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center text-red-400">
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <div className="text-red-200">{error}</div>
                </div>
              </div>
            )}

            {/* Start Button */}
            <button
              onClick={handleStartTrial}
              disabled={isLoading}
              className={`w-full py-5 px-8 rounded-2xl font-bold text-xl transition-all duration-300 ${
                isLoading
                  ? "bg-slate-700 text-slate-400 cursor-not-allowed"
                  : "bg-gradient-to-r from-amber-400 via-amber-500 to-orange-500 text-slate-900 hover:from-amber-300 hover:via-amber-400 hover:to-orange-400 shadow-lg shadow-amber-500/25 hover:shadow-xl hover:shadow-amber-500/30 hover:scale-[1.02]"
              }`}
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-3">
                  <svg className="animate-spin w-6 h-6" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Preparing Courtroom...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-3">
                  <GavelIcon className="w-7 h-7" />
                  Enter the Courtroom
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Features Section */}
        <div className="bg-gradient-to-b from-transparent via-slate-800/50 to-transparent py-20">
          <div className="max-w-6xl mx-auto px-4">
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-white mb-3">How It Works</h2>
              <p className="text-slate-400">Experience realistic courtroom proceedings</p>
            </div>

            <div className="grid md:grid-cols-4 gap-6">
              {[
                { 
                  step: "1", 
                  title: "Choose Role", 
                  desc: "Select attorney or witness",
                  icon: <AttorneyIllustration side="plaintiff" />
                },
                { 
                  step: "2", 
                  title: "Review Case", 
                  desc: "Study facts and evidence",
                  icon: <DocumentIcon className="w-full h-full p-2" />
                },
                { 
                  step: "3", 
                  title: "Present & Argue", 
                  desc: "Speak using your microphone",
                  icon: <MicrophoneIcon className="w-full h-full p-2" />
                },
                { 
                  step: "4", 
                  title: "Get Scored", 
                  desc: "Receive expert feedback",
                  icon: <ScalesOfJusticeIcon className="w-full h-full p-2" />
                },
              ].map((item, i) => (
                <div key={i} className="relative group">
                  <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-6 text-center h-full transition-all group-hover:border-blue-500/50 group-hover:bg-slate-800/70">
                    <div className="absolute -top-3 -left-3 w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center text-white font-bold text-sm shadow-lg">
                      {item.step}
                    </div>
                    <div className="w-16 h-16 mx-auto mb-4 rounded-xl overflow-hidden bg-slate-700/50">
                      {item.icon}
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-1">{item.title}</h3>
                    <p className="text-slate-400 text-sm">{item.desc}</p>
                  </div>
                  {i < 3 && (
                    <div className="hidden md:block absolute top-1/2 -right-3 transform -translate-y-1/2 text-slate-600 z-10">
                      <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="py-8 border-t border-slate-800">
          <div className="max-w-6xl mx-auto px-4 text-center text-slate-500 text-sm">
            <div className="flex items-center justify-center gap-2 mb-2">
              <ScalesOfJusticeIcon className="w-5 h-5 opacity-50" />
              <span>AI Mock Trial</span>
            </div>
            <p>Practice makes perfect. Train with AI to become a better advocate.</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
