/**
 * Courtroom Page
 * 
 * Per ARCHITECTURE.md Section 1:
 * - Frontend responsible for audio capture, playback, UI rendering
 * - Frontend must NEVER call LLMs directly, make scoring decisions, or control trial logic
 */

"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";

import MicInput, {
  type TrialState,
  type SpeakerPermissions,
  type Role,
  type TrialPhase,
} from "@/components/MicInput";
import { type Speaker } from "@/components/AudioPlayer";
import TranscriptPanel, { type TranscriptEntry } from "@/components/TranscriptPanel";
import ObjectionPanel from "@/components/ObjectionPanel";
import CaseMaterialsModal, { type ModalTab } from "@/components/CaseMaterialsModal";
import PreparationPanel from "@/components/PreparationPanel";
import PersonaCustomizer from "@/components/PersonaCustomizer";
import { ChevronDownIcon } from "@/components/ui/icons";

// =============================================================================
// SVG ICONS
// =============================================================================

const GavelIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14.5 3.5L20.5 9.5M3 21L10 14M8.5 8.5L15.5 15.5M5.5 11.5L12.5 4.5" strokeLinecap="round" />
  </svg>
);

const ScalesIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 3V21M12 3L3 8L6 14H0M12 3L21 8L18 14H24M3 8V8.01M21 8V8.01" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const MicIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor">
    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5z"/>
    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
  </svg>
);

const VolumeIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor">
    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
  </svg>
);

const DocumentIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>
);

const UserIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const AlertIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
);

const PlayIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor">
    <path d="M8 5v14l11-7z"/>
  </svg>
);

const CheckIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="3">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const FolderIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
  </svg>
);

const HomeIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" strokeLinecap="round" strokeLinejoin="round" />
    <polyline points="9 22 9 12 15 12 15 22" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// =============================================================================
// TYPES
// =============================================================================

type AttorneySubRole = "opening" | "direct_cross" | "closing";

interface SessionStatus {
  sessionId: string;
  phase: TrialPhase;
  humanRole: Role | null;
  attorneySubRole: AttorneySubRole | null;
  caseId: string | null;
  caseName?: string;
  initialized: boolean;
}

interface TrialStateResponse {
  session_id: string;
  phase: string;
  current_speaker: string | null;
  is_objection_pending: boolean;
  is_judge_interrupting: boolean;
  human_role: string | null;
}

// =============================================================================
// PHASE DISPLAY CONFIG
// =============================================================================

const phaseConfig: Record<TrialPhase, { 
  label: string; 
  description: string; 
  color: string;
  bgGradient: string;
  icon: string;
  tips: string[];
}> = {
  prep: {
    label: "Preparation",
    description: "Review case materials and prepare your strategy",
    color: "bg-slate-500",
    bgGradient: "from-slate-600 to-slate-800",
    icon: "📋",
    tips: [
      "Review the case facts and witness statements",
      "Identify key evidence and exhibits",
      "Prepare your opening statement outline",
      "Anticipate opposing arguments"
    ]
  },
  opening: {
    label: "Opening Statements",
    description: "Present your case theory to the court",
    color: "bg-blue-500",
    bgGradient: "from-blue-600 to-indigo-800",
    icon: "🎤",
    tips: [
      "State your case theme clearly",
      "Preview the evidence you will present",
      "Don't argue - save that for closing",
      "Make eye contact with the judges"
    ]
  },
  direct: {
    label: "Direct Examination",
    description: "Examine your own witness",
    color: "bg-emerald-500",
    bgGradient: "from-emerald-600 to-teal-800",
    icon: "❓",
    tips: [
      "Use open-ended questions (who, what, when, where, why)",
      "Let the witness tell the story",
      "Avoid leading questions",
      "Build credibility before key testimony"
    ]
  },
  cross: {
    label: "Cross Examination",
    description: "Question the opposing witness",
    color: "bg-orange-500",
    bgGradient: "from-orange-600 to-red-800",
    icon: "⚔️",
    tips: [
      "Use leading questions (yes/no answers)",
      "Control the witness",
      "Only ask questions you know the answer to",
      "Don't ask 'one question too many'"
    ]
  },
  redirect: {
    label: "Redirect Examination",
    description: "Rehabilitate your witness after cross",
    color: "bg-teal-500",
    bgGradient: "from-teal-600 to-cyan-800",
    icon: "🔄",
    tips: [
      "Only address matters raised on cross",
      "Clarify any confusion",
      "Restore witness credibility",
      "Keep it brief and focused"
    ]
  },
  recross: {
    label: "Recross Examination",
    description: "Follow up on redirect testimony",
    color: "bg-amber-500",
    bgGradient: "from-amber-600 to-orange-800",
    icon: "🔁",
    tips: [
      "Limited to matters on redirect",
      "Be strategic - often best to waive",
      "Don't repeat cross examination",
      "End on a strong point"
    ]
  },
  closing: {
    label: "Closing Arguments",
    description: "Summarize your case and argue to the judges",
    color: "bg-purple-500",
    bgGradient: "from-purple-600 to-violet-800",
    icon: "⚖️",
    tips: [
      "Summarize the evidence that supports your theory",
      "Address weaknesses in your case",
      "Explain why your side should prevail",
      "End with a powerful conclusion"
    ]
  },
  scoring: {
    label: "Scoring",
    description: "Judges are evaluating the performances",
    color: "bg-indigo-500",
    bgGradient: "from-indigo-600 to-purple-800",
    icon: "📊",
    tips: [
      "Scoring is in progress",
      "Results will be available shortly",
      "Review your performance mentally",
      "Prepare for feedback"
    ]
  },
};

const roleConfig: Record<Role, { label: string; icon: string; color: string }> = {
  attorney_plaintiff: { label: "Plaintiff Attorney", icon: "⚖️", color: "text-blue-400" },
  attorney_defense: { label: "Defense Attorney", icon: "🛡️", color: "text-emerald-400" },
  witness: { label: "Witness", icon: "👤", color: "text-amber-400" },
  judge: { label: "Judge", icon: "👨‍⚖️", color: "text-purple-400" },
  coach: { label: "Coach", icon: "📋", color: "text-slate-400" },
  spectator: { label: "Spectator", icon: "👁️", color: "text-amber-400" },
};

// Helper to normalize phase from API (may be uppercase) to lowercase
const normalizePhase = (phase: string | undefined | null): TrialPhase => {
  const normalized = (phase?.toLowerCase() || "prep") as TrialPhase;
  if (normalized in phaseConfig) {
    return normalized;
  }
  return "prep";
};

// =============================================================================
// API HELPERS
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function saveTranscript(sessionId: string) {
  fetch(`${API_BASE}/api/trial/${sessionId}/save-transcript`, { method: "POST" }).catch(() => {});
}

async function fetchTrialState(sessionId: string): Promise<TrialStateResponse> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/state`);
  if (!response.ok) {
    throw new Error("Failed to fetch trial state");
  }
  return response.json();
}

async function fetchSessionStatus(sessionId: string): Promise<SessionStatus> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}/status`);
  if (!response.ok) {
    throw new Error("Failed to fetch session status");
  }
  const data = await response.json();
  return {
    sessionId: data.session_id,
    phase: data.phase as TrialPhase,
    humanRole: data.human_role as Role | null,
    attorneySubRole: (data.attorney_sub_role as AttorneySubRole) || null,
    caseId: data.case_id,
    caseName: data.case_name,
    initialized: data.initialized,
  };
}

async function fetchSpeakerPermissions(
  sessionId: string,
  role: Role
): Promise<SpeakerPermissions> {
  const response = await fetch(
    `${API_BASE}/api/trial/${sessionId}/validate-speaker`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    }
  );
  if (!response.ok) {
    return { canSpeak: false, reason: "Failed to validate permissions" };
  }
  const data = await response.json();
  return {
    canSpeak: data.can_speak,
    reason: data.reason,
  };
}

async function triggerAITurn(
  sessionId: string,
  action: string,
  witnessId?: string,
  isTeammate?: boolean,
  regenerate?: boolean,
): Promise<{
  success: boolean;
  speaker: string;
  role: string;
  text: string;
  phase: string;
  attorney_name?: string;
  attorney_role?: string;
  message?: string;
  cached?: boolean;
}> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/ai-turn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action,
      witness_id: witnessId,
      is_teammate: !!isTeammate,
      regenerate: !!regenerate,
    }),
  });
  if (!response.ok) {
    return { success: false, speaker: "", role: "", text: "", phase: "", message: "Request failed" };
  }
  return response.json();
}

interface TranscriptHistoryEntry {
  speaker: string;
  role: string;
  text: string;
  audio_timestamp: number;
  phase: string;
  event_type?: string;
}

async function advancePhase(sessionId: string, targetPhase: string): Promise<{success: boolean; message: string; current_phase: string}> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/advance-phase`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_phase: targetPhase }),
  });
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Session expired — please start a new trial from the home page.");
    }
    const detail = await response.text().catch(() => "");
    throw new Error(`Server error (${response.status}): ${detail || "Failed to advance phase"}`);
  }
  return response.json();
}

interface WitnessInfo {
  id: string;
  name: string;
  called_by: string;
  is_current: boolean;
  is_examined: boolean;
  is_pending: boolean;
}

interface WitnessListResponse {
  session_id: string;
  current_witness_id: string | null;
  current_witness_name: string | null;
  witnesses_remaining: number;
  witnesses_examined_count: number;
  case_in_chief: string;
  prosecution_rested: boolean;
  defense_rested: boolean;
  prosecution_witnesses: string[];
  defense_witnesses: string[];
  exam_status: {
    direct_complete: boolean;
    cross_complete: boolean;
    redirect_complete: boolean;
    recross_complete: boolean;
    redirect_requested: boolean;
    recross_requested: boolean;
  };
  witnesses: WitnessInfo[];
}

async function fetchWitnesses(sessionId: string): Promise<WitnessListResponse> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/witnesses`);
  if (!response.ok) {
    throw new Error("Failed to fetch witnesses");
  }
  return response.json();
}

async function callWitness(sessionId: string, witnessId: string, callingSide: string): Promise<{
  success: boolean;
  witness_id: string;
  witness_name: string;
  calling_side: string;
  message: string;
}> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/call-witness`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ witness_id: witnessId, calling_side: callingSide }),
  });
  if (!response.ok) {
    throw new Error("Failed to call witness");
  }
  return response.json();
}

async function completeExamination(sessionId: string, examinationType: string): Promise<{
  success: boolean;
  examination_completed: string;
  witness_name: string;
  next_action: string;
  next_phase: string;
}> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/complete-examination`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ examination_type: examinationType }),
  });
  if (!response.ok) throw new Error("Failed to complete examination");
  return response.json();
}

async function requestRedirect(sessionId: string): Promise<{success: boolean; phase: string}> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/request-redirect`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to request redirect");
  return response.json();
}

async function waiveRedirect(sessionId: string): Promise<{success: boolean; next_action: string; phase: string}> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/waive-redirect`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to waive redirect");
  return response.json();
}

async function requestRecross(sessionId: string): Promise<{success: boolean; phase: string}> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/request-recross`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to request recross");
  return response.json();
}

async function waiveRecross(sessionId: string): Promise<{success: boolean; next_action: string; phase: string}> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/waive-recross`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to waive recross");
  return response.json();
}

async function restCase(sessionId: string, side: string): Promise<{
  success: boolean;
  side: string;
  next_action: string;
  case_in_chief: string;
  prosecution_rested: boolean;
  defense_rested: boolean;
}> {
  const response = await fetch(`${API_BASE}/api/trial/${sessionId}/rest-case`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ side }),
  });
  if (!response.ok) throw new Error("Failed to rest case");
  return response.json();
}

interface ExamQAPair {
  question: string;
  answer: string;
  attorney_name: string;
  attorney_role: string;
  objection?: string;
  sustained?: boolean;
  ruling?: string;
}

interface AutoExamResult {
  success: boolean;
  examination: {
    witness_id: string;
    witness_name: string;
    calling_side: string;
    direct: ExamQAPair[];
    cross: ExamQAPair[];
    redirect: ExamQAPair[];
    recross: ExamQAPair[];
    human_cross?: boolean;
    human_direct?: boolean;
  };
  live_scores?: Record<string, { role: string; name?: string; average: number; total: number }>;
  witnesses_remaining: number;
  total_witnesses_for_side: number;
  witnesses_examined: number;
  case_in_chief: string;
}

async function autoExamineWitness(
  sessionId: string,
  witnessId: string,
  callingSide: string,
): Promise<AutoExamResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 300_000); // 5 min max
  try {
    const response = await fetch(`${API_BASE}/api/trial/${sessionId}/auto-examine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        witness_id: witnessId,
        calling_side: callingSide,
        num_direct_questions: 5,
        num_cross_questions: 4,
        num_redirect_questions: 3,
        num_recross_questions: 2,
        skip_redirect: false,
        skip_recross: false,
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!response.ok) {
      const err = await response.text();
      throw new Error(`Auto-examine failed: ${err}`);
    }
    return response.json();
  } catch (e) {
    clearTimeout(timer);
    throw e;
  }
}

async function fetchTranscriptHistory(sessionId: string): Promise<TranscriptEntry[]> {
  try {
    const response = await fetch(`${API_BASE}/api/trial/${sessionId}/transcript`);
    if (!response.ok) {
      return [];
    }
    const data = await response.json();
    return (data.transcript || [])
      .filter((entry: TranscriptHistoryEntry) => entry.role !== "system")
      .map((entry: TranscriptHistoryEntry, index: number) => ({
        id: `history-${index}-${Date.now()}`,
        timestamp: entry.audio_timestamp * 1000 || index * 1000,
        role: normalizeRole(entry.role),
        speakerName: entry.speaker || formatRoleName(entry.role),
        text: entry.text,
        phase: normalizePhase(entry.phase),
        isHuman: false,
        isFinal: true,
      }));
  } catch {
    return [];
  }
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function normalizeRole(role: string): Role {
  if (role.startsWith("judge")) return "judge";
  if (role.startsWith("witness")) return "witness";
  if (role === "attorney_plaintiff" || role === "attorney_defense") return role;
  if (role === "coach") return "coach";
  return "witness"; // fallback
}

function formatRoleName(role: string): string {
  switch (role) {
    case "attorney_plaintiff":
      return "Plaintiff Attorney";
    case "attorney_defense":
      return "Defense Attorney";
    case "witness":
      return "Witness";
    case "judge":
      return "Judge";
    case "coach":
      return "Coach";
    default:
      // Handle prefixed roles like "judge_1", "witness_abc"
      if (role.startsWith("judge")) return "Judge";
      if (role.startsWith("witness")) return "Witness";
      return role;
  }
}

// =============================================================================
// PAGE COMPONENT
// =============================================================================

export default function CourtroomPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  // State
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);
  const [trialState, setTrialState] = useState<TrialState>({
    sessionId,
    phase: "prep",
    currentSpeaker: null,
    humanRole: null,
    canSpeak: false,
    isObjectionPending: false,
    isJudgeInterrupting: false,
  });
  const [permissions, setPermissions] = useState<SpeakerPermissions>({
    canSpeak: false,
    reason: "Loading...",
  });
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [currentSpeaker, setCurrentSpeaker] = useState<Speaker | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTips, setShowTips] = useState(true);
  
  // Modal state
  const [isMaterialsModalOpen, setIsMaterialsModalOpen] = useState(false);
  const [materialsModalTab, setMaterialsModalTab] = useState<ModalTab>("overview");
  const [isPersonaModalOpen, setIsPersonaModalOpen] = useState(false);
  
  // Phase advancement state
  const [isAdvancingPhase, setIsAdvancingPhase] = useState(false);
  const [phaseError, setPhaseError] = useState<string | null>(null);
  const [openingsReady, setOpeningsReady] = useState<boolean | null>(null);
  const [prepComplete, setPrepComplete] = useState<boolean | null>(null);
  
  // Witness & examination state
  const [witnesses, setWitnesses] = useState<WitnessInfo[]>([]);
  const [currentWitnessId, setCurrentWitnessId] = useState<string | null>(null);
  const [currentWitnessName, setCurrentWitnessName] = useState<string | null>(null);
  const [caseInChief, setCaseInChief] = useState<string>("prosecution");
  const [prosecutionRested, setProsecutionRested] = useState(false);
  const [defenseRested, setDefenseRested] = useState(false);
  const [examStatus, setExamStatus] = useState({
    direct_complete: false,
    cross_complete: false,
    redirect_complete: false,
    recross_complete: false,
  });
  const [examAction, setExamAction] = useState<string | null>(null); // "offer_redirect", "offer_recross", "witness_done"
  const [currentExamPhase, setCurrentExamPhase] = useState<string>("direct");
  const [witnessWindowCollapsed, setWitnessWindowCollapsed] = useState(false);

  // Live scoring state
  const [liveScores, setLiveScores] = useState<Record<string, any>>({});
  const [scoresCollapsed, setScoresCollapsed] = useState(false);
  const [phaseBarCollapsed, setPhaseBarCollapsed] = useState(false);
  const [teamMemory, setTeamMemory] = useState<Record<string, any> | null>(null);
  const [teamMemoryOpen, setTeamMemoryOpen] = useState(false);
  const [teamMemorySide, setTeamMemorySide] = useState<"plaintiff" | "defense">("plaintiff");

  // Objection tracking
  const [objectionCounts, setObjectionCounts] = useState<{ prosecution: number; defense: number; sustained: number; overruled: number }>({
    prosecution: 0, defense: 0, sustained: 0, overruled: 0,
  });

  // AI turn state
  const [isAITurnInProgress, setIsAITurnInProgress] = useState(false);
  const [aiTurnMessage, setAiTurnMessage] = useState<string | null>(null);
  const [isAISpeaking, setIsAISpeaking] = useState(false);
  const [aiSpeakerName, setAiSpeakerName] = useState<string | null>(null);
  const currentUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const currentAudioRef = useRef<any>(null);
  const activeSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const isSpeakingRef = useRef(false);
  const ttsAbortRef = useRef<AbortController | null>(null);
  const [speechProgress, setSpeechProgress] = useState(0);
  const [speechDuration, setSpeechDuration] = useState(0);
  const [speechSpeed, setSpeechSpeed] = useState(1.0);
  const speechSpeedRef = useRef(1.0);
  const speedChangeSignalRef = useRef<number | null>(null);
  const speechCompleteRef = useRef(true);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  
  // Track if transcript has been initialized with history
  const transcriptInitialized = useRef(false);

  // Keep an AudioContext alive so the browser doesn't revoke autoplay permissions
  // after periods of silence between speech segments.
  useEffect(() => {
    const initAudioCtx = () => {
      if (!audioContextRef.current || audioContextRef.current.state === "closed") {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      if (audioContextRef.current.state === "suspended") {
        audioContextRef.current.resume();
      }
    };
    document.addEventListener("click", initAudioCtx, { once: false });
    document.addEventListener("keydown", initAudioCtx, { once: false });
    return () => {
      document.removeEventListener("click", initAudioCtx);
      document.removeEventListener("keydown", initAudioCtx);
    };
  }, []);

  // Fetch initial state
  useEffect(() => {
    async function loadState() {
      try {
        setIsLoading(true);
        setError(null);

        const [status, state, history] = await Promise.all([
          fetchSessionStatus(sessionId),
          fetchTrialState(sessionId),
          fetchTranscriptHistory(sessionId),
        ]);

        setSessionStatus(status);
        setTrialState({
          sessionId,
          phase: normalizePhase(state.phase),
          currentSpeaker: state.current_speaker as Role | null,
          humanRole: state.human_role as Role | null,
          canSpeak: false,
          isObjectionPending: state.is_objection_pending,
          isJudgeInterrupting: state.is_judge_interrupting,
        });

        // Load transcript history if not already initialized
        if (!transcriptInitialized.current && history.length > 0) {
          setTranscript(history);
          transcriptInitialized.current = true;
        }

        if (status.humanRole) {
          const perms = await fetchSpeakerPermissions(sessionId, status.humanRole);
          setPermissions(perms);
          setTrialState((prev) => ({ ...prev, canSpeak: perms.canSpeak }));
        }

        // Check if opening statements are ready (for prep phase gating)
        try {
          const openingsResp = await fetch(`${API_BASE}/api/prep/${sessionId}/opening-statements`);
          if (openingsResp.ok) {
            const openingsData = await openingsResp.json();
            setOpeningsReady(openingsData.ready);
          }
        } catch {
          // Non-critical, don't block on this
        }

        // Load witnesses and case-in-chief status
        try {
          const witnessData = await fetchWitnesses(sessionId);
          setWitnesses(witnessData.witnesses);
          setCurrentWitnessId(witnessData.current_witness_id);
          setCurrentWitnessName(witnessData.current_witness_name || null);
          setCaseInChief(witnessData.case_in_chief || "prosecution");
          setProsecutionRested(witnessData.prosecution_rested || false);
          setDefenseRested(witnessData.defense_rested || false);
          if (witnessData.exam_status) setExamStatus(witnessData.exam_status);
        } catch {
          // Non-critical
        }

        // Load live scores if any
        try {
          const liveResp = await fetch(`${API_BASE}/api/scoring/${sessionId}/live-scores`);
          if (liveResp.ok) {
            const liveData = await liveResp.json();
            if (liveData.scores && Object.keys(liveData.scores).length > 0) {
              setLiveScores(liveData.scores);
            }
          }
        } catch {
          // Non-critical
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load courtroom");
      } finally {
        setIsLoading(false);
      }
    }

    loadState();
  }, [sessionId]);

  // Poll for trial state updates
  useEffect(() => {
    if (!sessionStatus?.initialized) return;

    const interval = setInterval(async () => {
      try {
        const state = await fetchTrialState(sessionId);
        setTrialState((prev) => ({
          ...prev,
          phase: normalizePhase(state.phase),
          currentSpeaker: state.current_speaker as Role | null,
          isObjectionPending: state.is_objection_pending,
          isJudgeInterrupting: state.is_judge_interrupting,
        }));

        if (sessionStatus.humanRole) {
          const perms = await fetchSpeakerPermissions(sessionId, sessionStatus.humanRole);
          setPermissions(perms);
          setTrialState((prev) => ({ ...prev, canSpeak: perms.canSpeak }));
        }
      } catch {
        // Silently ignore polling errors
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [sessionId, sessionStatus?.initialized, sessionStatus?.humanRole]);

  // Poll for opening statements readiness during prep phase
  useEffect(() => {
    const normalizedPhase = normalizePhase(trialState.phase);
    if (normalizedPhase !== "prep" || openingsReady === true) return;

    const pollOpenings = async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/prep/${sessionId}/opening-statements`);
        if (resp.ok) {
          const data = await resp.json();
          setOpeningsReady(data.ready);
        }
      } catch {
        // Non-critical
      }
    };

    pollOpenings();
    const interval = setInterval(pollOpenings, 3000);
    return () => clearInterval(interval);
  }, [sessionId, trialState.phase, openingsReady]);

  // Cleanup speech on unmount
  useEffect(() => {
    return () => {
      window.speechSynthesis?.cancel();
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      }
    };
  }, []);

  // Handle transcription from MicInput
  const handleTranscription = useCallback(
    (text: string, isFinal: boolean) => {
      if (!sessionStatus?.humanRole) return;

      const entry: TranscriptEntry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        timestamp: Date.now(),
        role: sessionStatus.humanRole,
        speakerName: "You",
        text,
        phase: trialState.phase,
        isHuman: true,
        isFinal,
      };

      setTranscript((prev) => {
        if (!isFinal && prev.length > 0 && !prev[prev.length - 1].isFinal) {
          return [...prev.slice(0, -1), entry];
        }
        return [...prev, entry];
      });
    },
    [sessionStatus?.humanRole, trialState.phase]
  );

  const handleObjectionRaised = useCallback(() => {
    setTrialState((prev) => ({ ...prev, isObjectionPending: true }));
  }, []);

  const handleObjectionResult = useCallback((sustained: boolean, explanation: string) => {
    setTrialState((prev) => ({ ...prev, isObjectionPending: false }));
    const entry: TranscriptEntry = {
      id: `${Date.now()}-ruling`,
      timestamp: Date.now(),
      role: "judge",
      speakerName: "Judge",
      text: `${sustained ? "Sustained" : "Overruled"}. ${explanation}`,
      phase: trialState.phase,
      isHuman: false,
      isFinal: true,
    };
    setTranscript((prev) => [...prev, entry]);
  }, [trialState.phase]);

  const stopAISpeech = useCallback(() => {
    if (ttsAbortRef.current) {
      ttsAbortRef.current.abort();
      ttsAbortRef.current = null;
    }
    if (currentUtteranceRef.current) {
      window.speechSynthesis.cancel();
      currentUtteranceRef.current = null;
    }
    if (activeSourceRef.current) {
      try { activeSourceRef.current.stop(); } catch { /* ok */ }
      activeSourceRef.current = null;
    }
    if (currentAudioRef.current) {
      try { currentAudioRef.current.pause(); } catch { /* ok */ }
      currentAudioRef.current = null;
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
    isSpeakingRef.current = false;
    setIsAISpeaking(false);
    setAiSpeakerName(null);
    setCurrentSpeaker(null);
    setSpeechProgress(0);
    setSpeechDuration(0);
  }, []);

  const speakWithBrowserAndWait = useCallback((text: string, speakerName: string): Promise<void> => {
    return new Promise<void>((resolve) => {
      if (!window.speechSynthesis) {
        resolve();
        return;
      }

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      utterance.rate = 1.05;
      utterance.pitch = 1.3;

      const allVoices = window.speechSynthesis.getVoices();
      const englishVoices = allVoices.filter(
        (v) => v.lang.startsWith("en")
      );
      if (englishVoices.length > 1) {
        const nameHash = speakerName.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
        utterance.voice = englishVoices[nameHash % englishVoices.length];
      } else if (englishVoices.length === 1) {
        utterance.voice = englishVoices[0];
      }

      currentUtteranceRef.current = utterance;
      let resolved = false;
      const finish = () => {
        if (resolved) return;
        resolved = true;
        currentUtteranceRef.current = null;
        resolve();
      };

      utterance.onend = finish;
      utterance.onerror = finish;

      window.speechSynthesis.speak(utterance);

      const safetyMs = Math.max(30_000, text.length * 100);
      setTimeout(() => {
        if (!resolved && currentUtteranceRef.current === utterance) {
          console.warn("Browser TTS safety timeout reached, cleaning up");
          window.speechSynthesis.cancel();
          finish();
        }
      }, safetyMs);
    });
  }, []);

  // Fetch cached opening audio from backend. Returns Blob or null (404 = not cached).
  const fetchCachedOpeningAudio = useCallback(async (
    side: "plaintiff" | "defense"
  ): Promise<Blob | null> => {
    try {
      const res = await fetch(`${API_BASE}/api/prep/${sessionId}/opening-audio/${side}`);
      if (res.ok) {
        const raw = await res.blob();
        return new Blob([raw], { type: "audio/mpeg" });
      }
    } catch (e) {
      console.warn(`No cached opening audio for ${side}:`, e);
    }
    return null;
  }, [sessionId]);

  // Pre-fetch TTS audio without playing. Returns a Blob or null.
  const prefetchTTSAudio = useCallback(async (
    text: string, role: string, speakerName: string
  ): Promise<Blob | null> => {
    try {
      const controller = new AbortController();
      const ttsTimeout = Math.max(45_000, text.length * 30);
      const timer = setTimeout(() => controller.abort(), ttsTimeout);
      const res = await fetch(`${API_BASE}/api/trial/${sessionId}/ai-tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, role, speaker_name: speakerName }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (res.ok) {
        const raw = await res.blob();
        return new Blob([raw], { type: "audio/mpeg" });
      }
      console.warn(`TTS prefetch returned ${res.status} for ${speakerName}`);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        console.warn("TTS prefetch failed:", e);
      }
    }
    return null;
  }, [sessionId]);

  // Play TTS audio with cascading fallbacks:
  //   1. Preloaded blob from prefetch → 2. Live backend TTS fetch
  //   → 3. Browser speech synthesis → 4. Reading delay
  const speakAIText = useCallback(async (
    text: string, role: string, speakerName: string,
    preloadedBlob?: Blob | null,
  ): Promise<void> => {
    speechCompleteRef.current = false;

    // Stop any previous speech but don't abort the whole TTS pipeline
    if (activeSourceRef.current) {
      try { activeSourceRef.current.stop(); } catch { /* ok */ }
      activeSourceRef.current = null;
    }
    if (currentAudioRef.current) {
      try { currentAudioRef.current.pause(); } catch { /* ok */ }
      currentAudioRef.current = null;
    }
    if (currentUtteranceRef.current) {
      window.speechSynthesis.cancel();
      currentUtteranceRef.current = null;
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }

    isSpeakingRef.current = true;
    setIsAISpeaking(true);
    setAiSpeakerName(speakerName);
    setCurrentSpeaker({ role: role as Role, name: speakerName, isAI: true });

    // Ensure AudioContext is active so the browser allows playback
    if (audioContextRef.current?.state === "suspended") {
      try { await audioContextRef.current.resume(); } catch { /* ok */ }
    }

    const cleanUp = () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
      isSpeakingRef.current = false;
      speechCompleteRef.current = true;
      setIsAISpeaking(false);
      setAiSpeakerName(null);
      setCurrentSpeaker(null);
      setSpeechProgress(0);
      setSpeechDuration(0);
    };

    const MAX_SPEAK_WAIT_MS = Math.max(300_000, text.length * 80);

    const withTimeout = <T,>(inner: Promise<T>, ms = MAX_SPEAK_WAIT_MS): Promise<T> => {
      let timer: ReturnType<typeof setTimeout>;
      return Promise.race([
        inner.finally(() => clearTimeout(timer)),
        new Promise<T>((_, reject) => {
          timer = setTimeout(() => {
            if (activeSourceRef.current) {
              try { activeSourceRef.current.stop(); } catch { /* ok */ }
              activeSourceRef.current = null;
            }
            if (currentAudioRef.current) {
              try { currentAudioRef.current.pause(); } catch { /* ok */ }
              currentAudioRef.current = null;
            }
            reject(new Error("speakAIText timeout"));
          }, ms);
        }),
      ]);
    };

    // AudioContext-based playback: decodes MP3 into PCM for accurate duration.
    // Handles the browser bug where changing playbackRate on a running
    // AudioBufferSourceNode causes onended to fire prematurely — if detected,
    // the source is automatically restarted from the current buffer position.
    const playBlobViaAudioContext = async (blob: Blob): Promise<boolean> => {
      let ctx: AudioContext;
      let audioBuffer: AudioBuffer;
      try {
        ctx = audioContextRef.current!;
        if (!ctx) throw new Error("No AudioContext");
        if (ctx.state === "suspended") await ctx.resume();
        const arrayBuffer = await blob.arrayBuffer();
        audioBuffer = await ctx.decodeAudioData(arrayBuffer);
      } catch (err) {
        console.warn("[TTS] AudioContext decode failed, will use HTMLAudioElement:", err);
        return false;
      }

      return new Promise<boolean>((resolve) => {
        let resolved = false;
        let stoppedManually = false;
        let progInterval: ReturnType<typeof setInterval> | null = null;
        const finish = (success: boolean) => {
          if (resolved) return;
          resolved = true;
          if (progInterval) { clearInterval(progInterval); progInterval = null; }
          activeSourceRef.current = null;
          currentAudioRef.current = null;
          resolve(success);
        };

        let playbackStartWall = Date.now();
        let currentOffset = 0;
        let currentSource: AudioBufferSourceNode;

        setSpeechDuration(audioBuffer.duration);

        const getEstimatedPos = () => {
          const wallElapsed = (Date.now() - playbackStartWall) / 1000;
          return Math.min(currentOffset + wallElapsed * speechSpeedRef.current, audioBuffer.duration);
        };

        const buildWrapper = () => ({
          pause: () => { stoppedManually = true; try { currentSource.stop(); } catch { /* ok */ } },
          get playbackRate() { return currentSource.playbackRate.value; },
          set playbackRate(v: number) { currentSource.playbackRate.value = v; },
          get currentTime() { return getEstimatedPos(); },
          set currentTime(_v: number) { /* seek not supported */ },
          get duration() { return audioBuffer.duration; },
          get paused() { return resolved; },
          get ended() { return resolved; },
        });

        const startSource = (offset: number) => {
          currentOffset = offset;
          playbackStartWall = Date.now();
          const src = ctx.createBufferSource();
          src.buffer = audioBuffer;
          src.playbackRate.value = speechSpeedRef.current;
          src.connect(ctx.destination);
          currentSource = src;
          activeSourceRef.current = src;
          currentAudioRef.current = buildWrapper();

          src.onended = () => {
            if (resolved || stoppedManually) { finish(true); return; }
            const expectedWallMs = ((audioBuffer.duration - offset) / speechSpeedRef.current) * 1000;
            const actualWallMs = Date.now() - playbackStartWall;
            if (actualWallMs >= expectedWallMs * 0.85) {
              finish(true);
            } else {
              const pos = getEstimatedPos();
              console.warn(`[TTS] Premature onended at ${pos.toFixed(1)}/${audioBuffer.duration.toFixed(1)}s (${actualWallMs}ms/${expectedWallMs.toFixed(0)}ms), restarting`);
              startSource(pos);
            }
          };

          src.start(0, offset);
        };

        startSource(0);

        progInterval = setInterval(() => {
          if (resolved) return;

          const pendingSpeed = speedChangeSignalRef.current;
          if (pendingSpeed !== null) {
            speedChangeSignalRef.current = null;
            const pos = getEstimatedPos();
            if (pos >= audioBuffer.duration - 0.05) { finish(true); return; }
            currentSource.onended = null;
            try { currentSource.stop(); } catch { /* ok */ }
            startSource(pos);
            return;
          }

          setSpeechProgress(getEstimatedPos());
        }, 200);
        if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = progInterval;

        const safetyMs = (audioBuffer.duration / Math.max(speechSpeedRef.current, 0.25)) * 1000 + 30_000;
        setTimeout(() => { if (!resolved) finish(true); }, safetyMs);
      });
    };

    const playBlobViaElement = (blob: Blob): Promise<boolean> => {
      return new Promise<boolean>((resolve) => {
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.playbackRate = speechSpeedRef.current;
        activeSourceRef.current = null;
        currentAudioRef.current = audio;
        audio.onloadedmetadata = () => { setSpeechDuration(audio.duration || 0); };

        let resolved = false;
        let lastProgress = Date.now();
        let isPlaying = false;

        const finish = (success: boolean) => {
          if (resolved) return;
          resolved = true;
          clearInterval(stallCheck);
          if (progInterval) clearInterval(progInterval);
          try { audio.pause(); } catch { /* ok */ }
          try { audio.removeAttribute("src"); audio.load(); } catch { /* ok */ }
          URL.revokeObjectURL(url);
          if (currentAudioRef.current === audio) {
            activeSourceRef.current = null;
            currentAudioRef.current = null;
          }
          resolve(success);
        };

        audio.onended = () => finish(true);
        audio.onerror = () => finish(false);

        audio.ontimeupdate = () => {
          lastProgress = Date.now();
          isPlaying = true;
        };

        const stallCheck = setInterval(() => {
          if (resolved) return;
          if (audio.ended) { finish(true); return; }
          if (isPlaying && Date.now() - lastProgress > 30_000) {
            console.warn("[TTS] HTMLAudioElement stall detected after 30s, finishing");
            finish(false);
          }
        }, 5000);

        const safetyMs = 600_000;
        setTimeout(() => { if (!resolved) finish(true); }, safetyMs);

        const progInterval = setInterval(() => {
          if (resolved || audio.paused) return;
          if (Math.abs(audio.playbackRate - speechSpeedRef.current) > 0.01) {
            audio.playbackRate = speechSpeedRef.current;
          }
          setSpeechProgress(audio.currentTime);
          setSpeechDuration(audio.duration || 0);
        }, 200);
        if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = progInterval;

        audio.play().then(() => {
          lastProgress = Date.now();
        }).catch(() => finish(false));
      });
    };

    const playBlob = async (blob: Blob): Promise<boolean> => {
      // HTMLAudioElement is the primary playback method: handles playbackRate
      // natively, fires 'ended' correctly, and avoids AudioContext bugs.
      return playBlobViaElement(blob);
    };

    let audioPlayed = false;
    const shortText = text.slice(0, 60).replace(/\n/g, " ");

    // 1. Try preloaded blob
    if (preloadedBlob && preloadedBlob.size > 0) {
      try {
        audioPlayed = await withTimeout(playBlob(preloadedBlob));
        if (!audioPlayed) console.warn(`[TTS] Preloaded blob playback failed for "${shortText}…"`);
      } catch {
        console.warn(`[TTS] Preloaded blob timeout for "${shortText}…"`);
      }
    }

    // 2. Fetch from backend TTS
    if (!audioPlayed) {
      if (preloadedBlob) console.warn(`[TTS] Falling back to live fetch for "${shortText}…"`);
      const abortCtrl = new AbortController();
      ttsAbortRef.current = abortCtrl;
      const fetchTimer = setTimeout(() => abortCtrl.abort(), 40_000);
      try {
        const ttsRes = await fetch(`${API_BASE}/api/trial/${sessionId}/ai-tts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, role, speaker_name: speakerName }),
          signal: abortCtrl.signal,
        });
        clearTimeout(fetchTimer);
        if (!abortCtrl.signal.aborted && ttsRes.ok) {
          const raw = await ttsRes.blob();
          if (!abortCtrl.signal.aborted && raw.size > 0) {
            const blob = new Blob([raw], { type: "audio/mpeg" });
            audioPlayed = await withTimeout(playBlob(blob));
            if (!audioPlayed) console.warn(`[TTS] Live-fetch blob playback failed for "${shortText}…"`);
          }
        } else if (!abortCtrl.signal.aborted) {
          console.warn(`[TTS] Live-fetch returned ${ttsRes.status} for "${shortText}…"`);
        }
      } catch (e: unknown) {
        clearTimeout(fetchTimer);
        if (!(e instanceof DOMException && e.name === "AbortError")) {
          console.warn("[TTS] Backend fetch error:", e);
        } else {
          console.warn(`[TTS] Live-fetch timed out for "${shortText}…"`);
        }
      } finally {
        ttsAbortRef.current = null;
      }
    }

    // 3. Browser speech synthesis fallback
    if (!audioPlayed && window.speechSynthesis) {
      console.warn(`[TTS] Falling back to browser speech synthesis for "${shortText}…"`);
      window.speechSynthesis.cancel();
      await new Promise((r) => setTimeout(r, 50));
      try {
        await withTimeout(speakWithBrowserAndWait(text, speakerName), 60_000);
        audioPlayed = true;
      } catch {
        console.warn(`[TTS] Browser speech synthesis failed/timed out for "${shortText}…"`);
      }
    }

    // 4. Last resort: wait so the user can read the text on screen
    if (!audioPlayed) {
      console.warn(`[TTS] All audio methods failed for "${shortText}…" — silent reading delay`);
      const readingDelayMs = Math.min(Math.max(text.length * 40, 2000), 12000);
      await new Promise((r) => setTimeout(r, readingDelayMs));
    }

    cleanUp();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, speakWithBrowserAndWait]);

  const handleSpeedChange = useCallback((newSpeed: number) => {
    setSpeechSpeed(newSpeed);
    speechSpeedRef.current = newSpeed;
    if (activeSourceRef.current) {
      speedChangeSignalRef.current = newSpeed;
    }
    if (currentAudioRef.current) {
      try { currentAudioRef.current.playbackRate = newSpeed; } catch { /* ok */ }
    }
  }, []);

  const waitForSpeechComplete = useCallback(async () => {
    const maxWait = 600_000;
    const start = Date.now();
    while (!speechCompleteRef.current && Date.now() - start < maxWait) {
      await new Promise((r) => setTimeout(r, 150));
    }
  }, []);

  const handleSeek = useCallback((time: number) => {
    if (currentAudioRef.current) {
      currentAudioRef.current.currentTime = time;
      setSpeechProgress(time);
    }
  }, []);

  // Request AI to take its turn. Awaits speech completion before returning.
  const handleAITurn = useCallback(async (action: string, witnessId?: string, isTeammate?: boolean, regenerate?: boolean) => {
    setIsAITurnInProgress(true);
    setAiTurnMessage(regenerate ? "Regenerating..." : "Requesting AI response...");
    try {
      const result = await triggerAITurn(sessionId, action, witnessId, isTeammate, regenerate);
      if (result.success && result.text) {
        setAiTurnMessage("Speaking...");
        const speakerName = result.attorney_name || result.speaker;

        if (regenerate) {
          setTranscript((prev) => {
            const idx = [...prev].reverse().findIndex(
              (e) => !e.isHuman && e.role === result.role
            );
            if (idx >= 0) {
              const realIdx = prev.length - 1 - idx;
              const updated = [...prev];
              updated[realIdx] = { ...updated[realIdx], text: result.text, id: `ai-regen-${Date.now()}` };
              return updated;
            }
            return [...prev, {
              id: `ai-${Date.now()}`, timestamp: Date.now(),
              role: result.role as Role, speakerName, text: result.text,
              phase: result.phase as TrialPhase, isHuman: false, isFinal: true,
            }];
          });
        } else {
          const entry: TranscriptEntry = {
            id: `ai-${Date.now()}`,
            timestamp: Date.now(),
            role: result.role as Role,
            speakerName,
            text: result.text,
            phase: result.phase as TrialPhase,
            isHuman: false,
            isFinal: true,
          };
          setTranscript((prev) => [...prev, entry]);
        }
        
        await speakAIText(result.text, result.role, speakerName);
        await waitForSpeechComplete();
      } else {
        setAiTurnMessage(result.message || "AI turn failed - no text generated");
      }
      return result;
    } catch (err) {
      console.error("Error during AI turn:", err);
      setAiTurnMessage(`Failed: ${err instanceof Error ? err.message : "Unknown error"}`);
      return null;
    } finally {
      setAiTurnMessage(null);
      setIsAITurnInProgress(false);
    }
  }, [sessionId, speakAIText]);

  // Speak a clerk announcement using a young female voice via backend TTS,
  // falling back to browser TTS. Returns a promise that resolves when done.
  const speakClerk = useCallback(async (text: string, preloadedBlob?: Blob | null): Promise<void> => {
    speechCompleteRef.current = false;

    if (currentAudioRef.current) { currentAudioRef.current.pause(); currentAudioRef.current = null; }
    if (currentUtteranceRef.current) { window.speechSynthesis.cancel(); currentUtteranceRef.current = null; }

    isSpeakingRef.current = true;
    setIsAISpeaking(true);
    setAiSpeakerName("Court Clerk");
    setCurrentSpeaker({ role: "judge" as Role, name: "Court Clerk", isAI: true });

    if (audioContextRef.current?.state === "suspended") {
      try { await audioContextRef.current.resume(); } catch { /* ok */ }
    }

    const done = () => {
      isSpeakingRef.current = false;
      speechCompleteRef.current = true;
      setIsAISpeaking(false);
      setAiSpeakerName(null);
      setCurrentSpeaker(null);
    };

    const MAX_CLERK_WAIT_MS = 60_000;

    const withTimeout = <T,>(inner: Promise<T>, ms = MAX_CLERK_WAIT_MS): Promise<T> => {
      let timer: ReturnType<typeof setTimeout>;
      return Promise.race([
        inner.finally(() => clearTimeout(timer)),
        new Promise<T>((_, reject) => {
          timer = setTimeout(() => {
            if (activeSourceRef.current) {
              try { activeSourceRef.current.stop(); } catch { /* ok */ }
              activeSourceRef.current = null;
            }
            if (currentAudioRef.current) {
              try { currentAudioRef.current.pause(); } catch { /* ok */ }
              currentAudioRef.current = null;
            }
            reject(new Error("speakClerk timeout"));
          }, ms);
        }),
      ]);
    };

    const playClerkBlobViaAudioContext = async (blob: Blob): Promise<boolean> => {
      let ctx: AudioContext;
      let audioBuffer: AudioBuffer;
      try {
        ctx = audioContextRef.current!;
        if (!ctx) throw new Error("No AudioContext");
        if (ctx.state === "suspended") await ctx.resume();
        const ab = await blob.arrayBuffer();
        audioBuffer = await ctx.decodeAudioData(ab);
      } catch {
        return false;
      }
      return new Promise<boolean>((resolve) => {
        let resolved = false;
        let stoppedManually = false;
        let playbackStartWall = Date.now();
        let currentOffset = 0;
        let currentSource: AudioBufferSourceNode;
        let clerkProgInterval: ReturnType<typeof setInterval> | null = null;
        const finish = (ok: boolean) => {
          if (resolved) return;
          resolved = true;
          if (clerkProgInterval) { clearInterval(clerkProgInterval); clerkProgInterval = null; }
          activeSourceRef.current = null;
          currentAudioRef.current = null;
          resolve(ok);
        };
        const getEstimatedPos = () => {
          const wallElapsed = (Date.now() - playbackStartWall) / 1000;
          return Math.min(currentOffset + wallElapsed * speechSpeedRef.current, audioBuffer.duration);
        };
        const startSource = (offset: number) => {
          currentOffset = offset;
          playbackStartWall = Date.now();
          const src = ctx.createBufferSource();
          src.buffer = audioBuffer;
          src.playbackRate.value = speechSpeedRef.current;
          src.connect(ctx.destination);
          currentSource = src;
          activeSourceRef.current = src;
          currentAudioRef.current = {
            pause: () => { stoppedManually = true; try { currentSource.stop(); } catch { /* ok */ } },
            get playbackRate() { return currentSource.playbackRate.value; },
            set playbackRate(v: number) { currentSource.playbackRate.value = v; },
          };
          src.onended = () => {
            if (resolved || stoppedManually) { finish(true); return; }
            const expectedWallMs = ((audioBuffer.duration - offset) / speechSpeedRef.current) * 1000;
            const actualWallMs = Date.now() - playbackStartWall;
            if (actualWallMs >= expectedWallMs * 0.85) {
              finish(true);
            } else {
              const pos = getEstimatedPos();
              console.warn(`[TTS] Clerk premature onended at ${pos.toFixed(1)}/${audioBuffer.duration.toFixed(1)}s, restarting`);
              startSource(pos);
            }
          };
          src.start(0, offset);
        };
        startSource(0);

        clerkProgInterval = setInterval(() => {
          if (resolved) return;
          const pendingSpeed = speedChangeSignalRef.current;
          if (pendingSpeed !== null) {
            speedChangeSignalRef.current = null;
            const pos = getEstimatedPos();
            if (pos >= audioBuffer.duration - 0.05) { finish(true); return; }
            currentSource.onended = null;
            try { currentSource.stop(); } catch { /* ok */ }
            startSource(pos);
            return;
          }
        }, 200);

        const safetyMs = (audioBuffer.duration / Math.max(speechSpeedRef.current, 0.25)) * 1000 + 30_000;
        setTimeout(() => { if (!resolved) finish(true); }, safetyMs);
      });
    };

    // HTMLAudioElement fallback for clerk
    const playClerkBlobViaElement = (blob: Blob): Promise<boolean> => {
      return new Promise<boolean>((resolve) => {
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.playbackRate = speechSpeedRef.current;
        activeSourceRef.current = null;
        currentAudioRef.current = audio;
        let resolved = false;
        let lastProgress = Date.now();
        let isPlaying = false;
        const finish = (ok: boolean) => {
          if (resolved) return;
          resolved = true;
          clearInterval(stallCheck);
          if (syncInterval) clearInterval(syncInterval);
          try { audio.pause(); } catch { /* ok */ }
          try { audio.removeAttribute("src"); audio.load(); } catch { /* ok */ }
          URL.revokeObjectURL(url);
          if (currentAudioRef.current === audio) {
            activeSourceRef.current = null;
            currentAudioRef.current = null;
          }
          resolve(ok);
        };
        audio.onended = () => finish(true);
        audio.onerror = () => finish(false);
        audio.ontimeupdate = () => { lastProgress = Date.now(); isPlaying = true; };
        const stallCheck = setInterval(() => {
          if (resolved) return;
          if (audio.ended) { finish(true); return; }
          if (isPlaying && Date.now() - lastProgress > 30_000) {
            console.warn("[TTS] Clerk HTMLAudioElement stall detected, finishing");
            finish(false);
          }
        }, 5000);
        const syncInterval = setInterval(() => {
          if (resolved || audio.paused) return;
          if (Math.abs(audio.playbackRate - speechSpeedRef.current) > 0.01) {
            audio.playbackRate = speechSpeedRef.current;
          }
        }, 200);
        setTimeout(() => { if (!resolved) finish(true); }, 300_000);
        audio.play().then(() => { lastProgress = Date.now(); }).catch(() => finish(false));
      });
    };

    const playClerkBlob = async (blob: Blob): Promise<boolean> => {
      return playClerkBlobViaElement(blob);
    };

    let played = false;

    if (preloadedBlob && preloadedBlob.size > 0) {
      try { played = await withTimeout(playClerkBlob(preloadedBlob)); } catch { /* timeout */ }
    }

    if (!played) {
      try {
        const controller = new AbortController();
        const fetchTimer = setTimeout(() => controller.abort(), 30_000);
        const ttsRes = await fetch(`${API_BASE}/api/trial/${sessionId}/ai-tts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, role: "judge", speaker_name: "Court Clerk" }),
          signal: controller.signal,
        });
        clearTimeout(fetchTimer);
        if (ttsRes.ok) {
          const raw = await ttsRes.blob();
          if (raw.size > 0) {
            played = await withTimeout(playClerkBlob(new Blob([raw], { type: "audio/mpeg" })));
          }
        } else {
          console.warn(`Clerk TTS fetch returned ${ttsRes.status}`);
        }
      } catch (e: unknown) {
        if (!(e instanceof DOMException && e.name === "AbortError")) {
          console.warn("Clerk TTS fetch failed:", e);
        }
      }
    }

    // Browser TTS — cancel queue first to avoid Chrome queueing bug
    if (!played && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      await new Promise((r) => setTimeout(r, 50));
      try {
        await withTimeout(new Promise<void>((resolve) => {
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.lang = "en-US";
          utterance.rate = 1.05 * speechSpeedRef.current;
          utterance.pitch = 1.35;
          const allVoices = window.speechSynthesis.getVoices();
          const femaleEnglish = allVoices.filter(
            (v) => v.lang.startsWith("en") && /female|samantha|victoria|karen|fiona|moira|susan|zira/i.test(v.name)
          );
          const englishVoices = femaleEnglish.length > 0
            ? femaleEnglish
            : allVoices.filter((v) => v.lang.startsWith("en"));
          if (englishVoices.length > 0) utterance.voice = englishVoices[0];
          currentUtteranceRef.current = utterance;
          utterance.onend = () => { currentUtteranceRef.current = null; resolve(); };
          utterance.onerror = () => { currentUtteranceRef.current = null; resolve(); };
          window.speechSynthesis.speak(utterance);
        }), 30_000);
        played = true;
      } catch { /* timeout */ }
    }

    if (!played) {
      await new Promise((r) => setTimeout(r, Math.min(text.length * 30, 5000)));
    }

    done();
  }, [sessionId]);

  // Add a system announcement to the transcript and optionally speak it
  const addSystemMessage = useCallback((text: string, phase?: string) => {
    const entry: TranscriptEntry = {
      id: `system-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      timestamp: Date.now(),
      role: "judge" as Role,
      speakerName: "Court Clerk",
      text,
      phase: (phase || trialState.phase) as TrialPhase,
      isHuman: false,
      isFinal: true,
    };
    setTranscript((prev) => [...prev, entry]);
  }, [trialState.phase]);

  // Wait for AI speech to finish playing (audio or browser TTS).
  // Uses isSpeakingRef to cover the window while TTS is being fetched.
  // Includes a safety timeout so it never hangs indefinitely.
  const waitForSpeechEnd = useCallback((maxWaitMs = 120_000): Promise<void> => {
    return new Promise((resolve) => {
      const startTime = Date.now();
      const check = () => {
        if (Date.now() - startTime > maxWaitMs) {
          console.warn("waitForSpeechEnd: timed out, resolving anyway");
          isSpeakingRef.current = false;
          resolve();
          return;
        }
        const refSpeaking = isSpeakingRef.current;
        const audioPlaying = currentAudioRef.current && !currentAudioRef.current.paused && !currentAudioRef.current.ended;
        const browserPlaying = window.speechSynthesis?.speaking;
        if (refSpeaking || audioPlaying || browserPlaying) {
          setTimeout(check, 300);
        } else {
          resolve();
        }
      };
      setTimeout(check, 500);
    });
  }, []);

  // Helper: add an AI result to the transcript without speaking it.
  const addAITranscriptEntry = useCallback((result: {
    role: string; text: string; phase: string; attorney_name?: string; speaker: string;
  }) => {
    const speakerName = result.attorney_name || result.speaker;
    const entry: TranscriptEntry = {
      id: `ai-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      timestamp: Date.now(),
      role: result.role as Role,
      speakerName,
      text: result.text,
      phase: result.phase as TrialPhase,
      isHuman: false,
      isFinal: true,
    };
    setTranscript((prev) => [...prev, entry]);
  }, []);

  // Run the automated opening statements sequence.
  // Text is pre-generated during preparation; all TTS audio is prefetched in
  // parallel at the start so playback is near-instant once each speaker's turn arrives.
  const runOpeningSequence = useCallback(async () => {
    const subRole = sessionStatus?.attorneySubRole || "direct_cross";
    const humanSide = sessionStatus?.humanRole?.includes("plaintiff") ? "plaintiff" : "defense";
    const humanIsOpening = subRole === "opening";

    const prosAnnouncement =
      "The Court calls upon the Prosecution to deliver their opening statement. " +
      "Counsel for the Prosecution, you may proceed.";
    const defAnnouncement =
      "Thank you, Counsel. The Court now calls upon the Defense to deliver their opening statement. " +
      "Defense Counsel, you may proceed.";

    // If human is the prosecution opening attorney, just announce and let them speak
    if (humanSide === "plaintiff" && humanIsOpening) {
      addSystemMessage(prosAnnouncement, "opening");
      await speakClerk(prosAnnouncement);
      return;
    }

    const needAIDef = !(humanSide === "defense" && humanIsOpening);

    // ──────────────────────────────────────────────────────────────────
    // PHASE 1: Fetch pre-generated opening text from prep cache
    // ──────────────────────────────────────────────────────────────────
    setIsAITurnInProgress(true);
    setAiTurnMessage("Loading opening statements...");

    let prosText: string | null = null;
    let defText: string | null = null;
    let prosAttorneyName = "Prosecution Attorney";
    let defAttorneyName = "Defense Attorney";
    let prosTextFromCache = false;
    let defTextFromCache = false;

    try {
      const openingsResp = await fetch(`${API_BASE}/api/prep/${sessionId}/opening-statements`);
      if (openingsResp.ok) {
        const data = await openingsResp.json();
        if (data.opening_plaintiff) { prosText = data.opening_plaintiff; prosTextFromCache = true; }
        if (data.opening_defense) { defText = data.opening_defense; defTextFromCache = true; }
        if (data.plaintiff_attorney_name) prosAttorneyName = data.plaintiff_attorney_name;
        if (data.defense_attorney_name) defAttorneyName = data.defense_attorney_name;
      }
    } catch {
      // Fall through to triggerAITurn fallback below
    }

    const prosIsTeammate = humanSide === "plaintiff";
    const defIsTeammate = humanSide === "defense";

    if (!prosText) {
      setAiTurnMessage("Generating prosecution opening statement...");
      const prosResult = await triggerAITurn(sessionId, "opening", undefined, prosIsTeammate);
      if (!prosResult.success) {
        setAiTurnMessage("Failed to generate prosecution opening");
        setIsAITurnInProgress(false);
        return;
      }
      prosText = prosResult.text;
      prosAttorneyName = prosResult.attorney_name || prosResult.speaker;
      prosTextFromCache = false;
    }

    if (needAIDef && !defText) {
      setAiTurnMessage("Generating defense opening statement...");
      const defResult = await triggerAITurn(sessionId, "opening", undefined, defIsTeammate);
      if (defResult.success) {
        defText = defResult.text;
        defAttorneyName = defResult.attorney_name || defResult.speaker;
        defTextFromCache = false;
      }
    }

    const prosRole = "attorney_plaintiff";
    const defRole = "attorney_defense";

    // ──────────────────────────────────────────────────────────────────
    // PHASE 2: Fetch audio — only use cached audio when the TEXT also
    // came from the same cache, otherwise generate fresh TTS from the
    // displayed text to guarantee audio matches transcript.
    // ──────────────────────────────────────────────────────────────────
    setAiTurnMessage("Loading audio...");

    const prosAudioPromise = prosTextFromCache
      ? fetchCachedOpeningAudio("plaintiff").then(
          cached => cached || prefetchTTSAudio(prosText, prosRole, prosAttorneyName)
        )
      : prefetchTTSAudio(prosText, prosRole, prosAttorneyName);
    const defAudioPromise = needAIDef && defText
      ? (defTextFromCache
          ? fetchCachedOpeningAudio("defense").then(
              cached => cached || prefetchTTSAudio(defText!, defRole, defAttorneyName)
            )
          : prefetchTTSAudio(defText!, defRole, defAttorneyName))
      : Promise.resolve(null);
    const prosClerkTTSPromise = prefetchTTSAudio(prosAnnouncement, "judge", "Court Clerk");
    const defClerkTTSPromise = needAIDef
      ? prefetchTTSAudio(defAnnouncement, "judge", "Court Clerk")
      : Promise.resolve(null);

    const prosClerkBlob = await prosClerkTTSPromise;

    // ──────────────────────────────────────────────────────────────────
    // PHASE 3: Play prosecution clerk announcement (audio already ready)
    // ──────────────────────────────────────────────────────────────────
    addSystemMessage(prosAnnouncement, "opening");
    await speakClerk(prosAnnouncement, prosClerkBlob);
    await waitForSpeechComplete();

    // Record prosecution opening to backend transcript (so it persists)
    fetch(`${API_BASE}/api/trial/${sessionId}/record-transcript`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        speaker: prosAttorneyName, role: prosRole,
        text: prosText, phase: "OPENING", event_type: "opening_statement",
      }),
    }).catch(() => {});

    addAITranscriptEntry({
      role: prosRole,
      text: prosText,
      phase: "opening",
      attorney_name: prosAttorneyName,
      speaker: prosAttorneyName,
    });

    const prosBlob = await prosAudioPromise;
    setAiTurnMessage(null);
    await speakAIText(prosText, prosRole, prosAttorneyName, prosBlob);
    await waitForSpeechComplete();

    // Score immediately after prosecution opening
    try {
      const scoreResp = await fetch(`${API_BASE}/api/scoring/${sessionId}/live-score`, { method: "POST" });
      if (scoreResp.ok) {
        const scoreData = await scoreResp.json();
        if (scoreData.scores) setLiveScores((prev) => ({ ...prev, ...scoreData.scores }));
      }
    } catch { /* non-critical */ }

    await new Promise((r) => setTimeout(r, 200));

    if (humanSide === "defense" && humanIsOpening) {
      const defClerkBlob = await defClerkTTSPromise;
      addSystemMessage(defAnnouncement, "opening");
      await speakClerk(defAnnouncement, defClerkBlob);
      await waitForSpeechComplete();
      setIsAITurnInProgress(false);
      return;
    }

    if (needAIDef && defText) {
      const defClerkBlob = await defClerkTTSPromise;
      addSystemMessage(defAnnouncement, "opening");
      await speakClerk(defAnnouncement, defClerkBlob);
      await waitForSpeechComplete();

      // Record defense opening to backend transcript
      fetch(`${API_BASE}/api/trial/${sessionId}/record-transcript`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          speaker: defAttorneyName, role: defRole,
          text: defText, phase: "OPENING", event_type: "opening_statement",
        }),
      }).catch(() => {});

      addAITranscriptEntry({
        role: defRole,
        text: defText,
        phase: "opening",
        attorney_name: defAttorneyName,
        speaker: defAttorneyName,
      });

      const defBlob = await defAudioPromise;
      await speakAIText(defText, defRole, defAttorneyName, defBlob);
      await waitForSpeechComplete();
    }

    // Trigger live scoring after openings
    try {
      const scoreResp = await fetch(`${API_BASE}/api/scoring/${sessionId}/live-score`, { method: "POST" });
      if (scoreResp.ok) {
        const scoreData = await scoreResp.json();
        if (scoreData.scores) setLiveScores((prev) => ({ ...prev, ...scoreData.scores }));
      }
    } catch { /* non-critical */ }

    saveTranscript(sessionId);
    setIsAITurnInProgress(false);
  }, [sessionStatus, sessionId, addSystemMessage, addAITranscriptEntry, speakClerk, speakAIText, prefetchTTSAudio, fetchCachedOpeningAudio, waitForSpeechComplete]);

  // Refresh all witness and exam state from backend
  const refreshWitnessState = useCallback(async () => {
    try {
      const data = await fetchWitnesses(sessionId);
      setWitnesses(data.witnesses);
      setCurrentWitnessId(data.current_witness_id);
      setCurrentWitnessName(data.current_witness_name || null);
      setCaseInChief(data.case_in_chief || "prosecution");
      setProsecutionRested(data.prosecution_rested || false);
      setDefenseRested(data.defense_rested || false);
      if (data.exam_status) setExamStatus(data.exam_status);
      return data;
    } catch (err) {
      console.error("Failed to refresh witness state:", err);
      return null;
    }
  }, [sessionId]);

  // Call a witness to the stand with clerk announcement
  const callWitnessWithAnnouncement = useCallback(async (
    witnessId: string, witnessName: string, callingSide: string
  ) => {
    setAiTurnMessage(`Calling ${witnessName} to the stand...`);
    await callWitness(sessionId, witnessId, callingSide);
    setCurrentWitnessId(witnessId);
    setCurrentWitnessName(witnessName);
    setExamStatus({ direct_complete: false, cross_complete: false, redirect_complete: false, recross_complete: false });
    setExamAction(null);

    const sideLabel = callingSide === "defense" ? "Defense" : "Prosecution";
    const clerkText = `The ${sideLabel} calls ${witnessName} to the stand. ${witnessName}, please approach the witness stand.`;
    addSystemMessage(clerkText, "direct");

    const clerkBlob = await prefetchTTSAudio(clerkText, "judge", "Court Clerk");
    await speakClerk(clerkText, clerkBlob);
    await waitForSpeechComplete();
    await new Promise((r) => setTimeout(r, 500));
  }, [sessionId, addSystemMessage, prefetchTTSAudio, speakClerk, waitForSpeechComplete]);

  // Play a batch of Q&A pairs with TTS, adding transcript entries.
  // Uses prefetch pipelining: answer TTS is fetched while the question plays,
  // and the next question TTS is fetched while the current answer plays.
  const playExamQAPairs = useCallback(async (
    pairs: ExamQAPair[],
    witnessName: string,
    phase: string,
  ) => {
    setCurrentExamPhase(phase);
    let nextQBlob: Blob | null = null;

    for (let i = 0; i < pairs.length; i++) {
      const qa = pairs[i];

      // Sustained objection entry (no Q&A, just objection info)
      if (qa.objection && qa.sustained && !qa.question) {
        nextQBlob = null;
        const objectorName = qa.attorney_name || "Attorney";
        const objectionText = `Objection, Your Honor! ${qa.objection.replace(/_/g, " ")}.`;
        addAITranscriptEntry({
          role: qa.attorney_role || "attorney_defense",
          text: objectionText,
          phase,
          speaker: objectorName,
        });
        const rulingText = qa.ruling || "Sustained. The question is struck.";
        const objBlob = await prefetchTTSAudio(objectionText, qa.attorney_role || "attorney_defense", objectorName);
        const rulPrefetch = prefetchTTSAudio(rulingText, "judge", "Judge");
        await speakAIText(objectionText, qa.attorney_role || "attorney_defense", objectorName, objBlob);
        await waitForSpeechComplete();

        addAITranscriptEntry({ role: "judge", text: rulingText, phase, speaker: "Judge" });
        const rulBlob = await rulPrefetch;
        await speakAIText(rulingText, "judge", "Judge", rulBlob);
        await waitForSpeechComplete();

        setObjectionCounts((prev) => ({
          ...prev,
          sustained: prev.sustained + 1,
          [phase.includes("direct") || phase === "redirect" ? "defense" : "prosecution"]:
            prev[phase.includes("direct") || phase === "redirect" ? "defense" : "prosecution"] + 1,
        }));
        continue;
      }

      if (!qa.question) continue;

      try {
        // Attorney question — use pipelined blob from previous iteration when available
        setAiTurnMessage(`${qa.attorney_name}: Q${i + 1}/${pairs.length}`);
        addAITranscriptEntry({
          role: qa.attorney_role,
          text: qa.question,
          phase,
          attorney_name: qa.attorney_name,
          speaker: qa.attorney_name,
        });
        const qBlob = nextQBlob || await prefetchTTSAudio(qa.question, qa.attorney_role, qa.attorney_name);
        nextQBlob = null;

        // Pipeline: start fetching answer TTS while the question plays
        const answerPrefetch = qa.answer
          ? prefetchTTSAudio(qa.answer, "witness", witnessName)
          : null;

        await speakAIText(qa.question, qa.attorney_role, qa.attorney_name, qBlob);
        await waitForSpeechComplete();

        // Overruled objection handling
        if (qa.objection && !qa.sustained) {
          const objSide = phase.includes("direct") || phase === "redirect" ? "defense" : "prosecution";
          const objRole = objSide === "defense" ? "attorney_defense" : "attorney_plaintiff";
          const objText = `Objection! ${qa.objection.replace(/_/g, " ")}.`;
          addAITranscriptEntry({ role: objRole, text: objText, phase, speaker: "Opposing Counsel" });
          const rulingText = qa.ruling || "Overruled. The witness may answer.";
          const objBlob = await prefetchTTSAudio(objText, objRole, "Opposing Counsel");
          const rulPrefetch = prefetchTTSAudio(rulingText, "judge", "Judge");
          await speakAIText(objText, objRole, "Opposing Counsel", objBlob);
          await waitForSpeechComplete();

          addAITranscriptEntry({ role: "judge", text: rulingText, phase, speaker: "Judge" });
          const rulBlob = await rulPrefetch;
          await speakAIText(rulingText, "judge", "Judge", rulBlob);
          await waitForSpeechComplete();

          setObjectionCounts((prev) => ({
            ...prev,
            overruled: prev.overruled + 1,
            [objSide]: prev[objSide as "prosecution" | "defense"] + 1,
          }));
        }

        // Witness answer — blob should already be fetched by now
        if (qa.answer) {
          setAiTurnMessage(`${witnessName} answering...`);
          addAITranscriptEntry({ role: "witness", text: qa.answer, phase, speaker: witnessName });
          const aBlob = answerPrefetch ? await answerPrefetch : null;

          // Pipeline: start fetching NEXT question TTS while this answer plays
          const nextQa = pairs[i + 1];
          const shouldPrefetchNext = nextQa?.question && !(nextQa.objection && nextQa.sustained && !nextQa.question);
          const nextQPrefetch = shouldPrefetchNext
            ? prefetchTTSAudio(nextQa!.question!, nextQa!.attorney_role, nextQa!.attorney_name)
            : null;

          await speakAIText(qa.answer, "witness", witnessName, aBlob);
          await waitForSpeechComplete();

          nextQBlob = nextQPrefetch ? await nextQPrefetch : null;
        }
      } catch (err) {
        console.error(`playExamQAPairs error at Q${i + 1}:`, err);
        nextQBlob = null;
      }
    }
  }, [addAITranscriptEntry, speakAIText, prefetchTTSAudio, waitForSpeechComplete]);

  // Run the full automated examination flow for all witnesses in the current case-in-chief.
  const runFullExaminationFlow = useCallback(async () => {
    setIsAITurnInProgress(true);
    setAiTurnMessage("Preparing examination...");

    const humanSide = sessionStatus?.humanRole?.includes("plaintiff") ? "plaintiff" : "defense";

    try {
      let witnessData = await refreshWitnessState();
      if (!witnessData) { setIsAITurnInProgress(false); return; }

      const processOneSide = async (cicLabel: string, cicSide: string) => {
        const cicWitnesses = (cicLabel === "defense"
          ? witnessData!.defense_witnesses
          : witnessData!.prosecution_witnesses) || [];
        const pending = cicWitnesses.filter((wid: string) =>
          witnessData!.witnesses.find((w) => w.id === wid && w.is_pending)
        );

        const totalForSide = cicWitnesses.length;

        for (let wi = 0; wi < pending.length; wi++) {
          const wid = pending[wi];
          const witness = witnessData!.witnesses.find((w) => w.id === wid);
          if (!witness) continue;

          const witnessNum = wi + 1 + (totalForSide - pending.length);
          setAiTurnMessage(`Examining witness ${witnessNum} of ${totalForSide}: ${witness.name}...`);

          // Clerk announces the witness
          const sideLabel = cicSide === "defense" ? "Defense" : "Prosecution";
          const callText = `The ${sideLabel} calls ${witness.name} to the stand.`;
          addSystemMessage(callText, "direct");
          const callBlob = await prefetchTTSAudio(callText, "judge", "Court Clerk");
          await speakClerk(callText, callBlob);
          await waitForSpeechComplete();

          // Rotating messages while backend generates examination Q&A
          const loadingMessages = [
            `${sideLabel} counsel preparing questions for ${witness.name}...`,
            `Attorneys reviewing case materials and affidavits...`,
            `Building examination strategy based on witness testimony...`,
            `Analyzing prior testimony for cross-examination angles...`,
            `Both sides preparing their legal arguments...`,
            `Reviewing witness credibility factors...`,
            `Formulating redirect questions based on case theory...`,
            `Checking for potential objection opportunities...`,
            `AI attorneys are crafting their examination approach...`,
            `Preparing evidence references for examination...`,
          ];
          let msgIdx = 0;
          setAiTurnMessage(loadingMessages[0]);
          const msgInterval = setInterval(() => {
            msgIdx = (msgIdx + 1) % loadingMessages.length;
            setAiTurnMessage(loadingMessages[msgIdx]);
          }, 4000);

          let result: AutoExamResult;
          try {
            result = await autoExamineWitness(sessionId, wid, cicSide);
          } finally {
            clearInterval(msgInterval);
          }
          const exam = result.examination;

          // Update witness counter state
          setCurrentWitnessId(wid);
          setCurrentWitnessName(witness.name);

          // --- DIRECT EXAMINATION ---
          if (exam.human_direct) {
            if (result.live_scores) {
              setLiveScores((prev) => ({ ...prev, ...result.live_scores }));
            }
            const directClerk = `Counsel for the ${sideLabel}, you may proceed with direct examination of ${witness.name}.`;
            addSystemMessage(directClerk, "direct");
            const dcBlob = await prefetchTTSAudio(directClerk, "judge", "Court Clerk");
            await speakClerk(directClerk, dcBlob);
            await waitForSpeechComplete();
            setAiTurnMessage(null);
            setIsAITurnInProgress(false);
            return;
          }

          const directQAPairs = (exam.direct || []).filter(
            (p: ExamQAPair) => p.question && p.answer
          );

          if (directQAPairs.length > 0) {
            setCurrentExamPhase("direct");
            const beginDirectText = `Counsel, you may begin direct examination.`;
            addSystemMessage(beginDirectText, "direct");
            const bdBlob = await prefetchTTSAudio(beginDirectText, "judge", "Court Clerk");
            await speakClerk(beginDirectText, bdBlob);
            await waitForSpeechComplete();
            await playExamQAPairs(directQAPairs, witness.name, "direct");
          } else {
            console.warn("Direct examination returned 0 valid Q&A pairs");
            addSystemMessage(`[Note: Direct examination of ${witness.name} produced no questions.]`, "direct");
          }

          setExamStatus((prev) => ({ ...prev, direct_complete: true }));
          const directDoneText = `Direct examination complete. Cross-examination may begin.`;
          addSystemMessage(directDoneText, "cross");
          const ddBlob = await prefetchTTSAudio(directDoneText, "judge", "Court Clerk");
          await speakClerk(directDoneText, ddBlob);
          await waitForSpeechComplete();

          // --- CROSS EXAMINATION ---
          if (exam.human_cross) {
            if (result.live_scores) {
              setLiveScores((prev) => ({ ...prev, ...result.live_scores }));
            }
            const crossClerk = `Counsel, you may cross-examine ${witness.name}.`;
            addSystemMessage(crossClerk, "cross");
            const ccBlob = await prefetchTTSAudio(crossClerk, "judge", "Court Clerk");
            await speakClerk(crossClerk, ccBlob);
            await waitForSpeechComplete();
            setAiTurnMessage(null);
            setIsAITurnInProgress(false);
            return;
          }

          const crossQAPairs = (exam.cross || []).filter(
            (p: ExamQAPair) => p.question && p.answer
          );

          setCurrentExamPhase("cross");
          if (crossQAPairs.length > 0) {
            await playExamQAPairs(crossQAPairs, witness.name, "cross");
          } else {
            console.warn("Cross examination returned 0 valid Q&A pairs");
            addSystemMessage(`[Note: Cross examination of ${witness.name} produced no questions.]`, "cross");
          }

          setExamStatus((prev) => ({ ...prev, cross_complete: true }));

          const redirectPairs = (exam.redirect || []).filter(
            (p: ExamQAPair) => p.question && p.answer
          );
          if (redirectPairs.length > 0) {
            setCurrentExamPhase("redirect");
            const redirectText = `Cross-examination complete. Counsel may redirect.`;
            addSystemMessage(redirectText, "redirect");
            const rdBlob = await prefetchTTSAudio(redirectText, "judge", "Court Clerk");
            await speakClerk(redirectText, rdBlob);
            await waitForSpeechComplete();
            await playExamQAPairs(redirectPairs, witness.name, "redirect");
            setExamStatus((prev) => ({ ...prev, redirect_complete: true }));
          }

          const recrossPairs = (exam.recross || []).filter(
            (p: ExamQAPair) => p.question && p.answer
          );
          if (recrossPairs.length > 0) {
            setCurrentExamPhase("recross");
            const recrossText = `Redirect complete. Opposing counsel may recross.`;
            addSystemMessage(recrossText, "recross");
            const rcBlob = await prefetchTTSAudio(recrossText, "judge", "Court Clerk");
            await speakClerk(recrossText, rcBlob);
            await waitForSpeechComplete();
            await playExamQAPairs(recrossPairs, witness.name, "recross");
            setExamStatus((prev) => ({ ...prev, recross_complete: true }));
          }

          // Witness excused
          const dismissText = `${witness.name} is excused.`;
          addSystemMessage(dismissText, "direct");
          const disBlob = await prefetchTTSAudio(dismissText, "judge", "Court Clerk");
          await speakClerk(dismissText, disBlob);
          await waitForSpeechComplete();

          setCurrentWitnessId(null);
          setCurrentWitnessName(null);

          // Update live scores from examination result
          if (result.live_scores) {
            setLiveScores((prev) => ({ ...prev, ...result.live_scores }));
          }

          // Refresh state for next iteration
          witnessData = await refreshWitnessState();
          if (!witnessData) break;

          const remainingNow = result.witnesses_remaining - 1;
          if (remainingNow > 0) {
            setAiTurnMessage(`${remainingNow} witness${remainingNow > 1 ? "es" : ""} remaining for ${sideLabel}...`);
          }
        }
      };

      // --- PROSECUTION CASE-IN-CHIEF ---
      const currentCIC = witnessData.case_in_chief || "prosecution";
      if (currentCIC === "prosecution" && !witnessData.prosecution_rested) {
        addSystemMessage("The Prosecution may present its case.", "direct");
        const paBlob = await prefetchTTSAudio("The Prosecution may present its case.", "judge", "Court Clerk");
        await speakClerk("The Prosecution may present its case.", paBlob);
        await waitForSpeechComplete();

        await processOneSide("prosecution", "plaintiff");

        witnessData = await refreshWitnessState();
        if (!witnessData) { return; }
        if (witnessData.current_witness_id) { return; }

        const restResult = await restCase(sessionId, "prosecution");
        setProsecutionRested(true);
        setCaseInChief(restResult.case_in_chief);

        addSystemMessage("The Prosecution rests.", "direct");
        const rstBlob = await prefetchTTSAudio("The Prosecution rests.", "judge", "Court Clerk");
        await speakClerk("The Prosecution rests.", rstBlob);
        await waitForSpeechComplete();

        witnessData = await refreshWitnessState();
        if (!witnessData) { setIsAITurnInProgress(false); return; }
      }

      // --- DEFENSE CASE-IN-CHIEF ---
      if (!witnessData.defense_rested) {
        addSystemMessage("The Defense may present its case.", "direct");
        const daBlob = await prefetchTTSAudio("The Defense may present its case.", "judge", "Court Clerk");
        await speakClerk("The Defense may present its case.", daBlob);
        await waitForSpeechComplete();

        await processOneSide("defense", "defense");

        witnessData = await refreshWitnessState();
        if (!witnessData) { return; }
        if (witnessData.current_witness_id) { return; }

        const defRestResult = await restCase(sessionId, "defense");
        setDefenseRested(true);
        setCaseInChief(defRestResult.case_in_chief);

        addSystemMessage("The Defense rests.", "direct");
        const drBlob = await prefetchTTSAudio("The Defense rests.", "judge", "Court Clerk");
        await speakClerk("The Defense rests.", drBlob);
        await waitForSpeechComplete();
      }

      // Both sides rested
      addSystemMessage("Both sides have rested. Ready for closing arguments.", "direct");
      const clBlob = await prefetchTTSAudio("Both sides have rested. Ready for closing arguments.", "judge", "Court Clerk");
      await speakClerk("Both sides have rested. Ready for closing arguments.", clBlob);
      await waitForSpeechComplete();

      await refreshWitnessState();
    } catch (err) {
      console.error("Examination flow error:", err);
      const errMsg = err instanceof Error ? err.message : "Unknown error";
      setAiTurnMessage(`Error during examination: ${errMsg}`);
      addSystemMessage(`Examination error: ${errMsg}. The trial will continue.`, "direct");
      await new Promise((r) => setTimeout(r, 3000));
    } finally {
      saveTranscript(sessionId);
      setAiTurnMessage(null);
      setIsAITurnInProgress(false);
    }
  }, [sessionStatus, sessionId, addSystemMessage, addAITranscriptEntry, speakAIText, speakClerk, prefetchTTSAudio, refreshWitnessState, playExamQAPairs]);

  // NOTE: Manual examination handlers removed - examination flow is now fully automated

  const runClosingSequence = useCallback(async () => {
    setIsAITurnInProgress(true);

    const prosAnnounce = "The Court calls upon the Prosecution to deliver their closing argument. Counsel, you may proceed.";
    const defAnnounce = "Thank you, Counsel. The Court now calls upon the Defense to deliver their closing argument. Defense Counsel, you may proceed.";

    setAiTurnMessage("Generating prosecution closing argument...");
    addSystemMessage(prosAnnounce, "closing");
    const prosClerkBlob = await prefetchTTSAudio(prosAnnounce, "judge", "Court Clerk");
    await speakClerk(prosAnnounce, prosClerkBlob);
    await waitForSpeechComplete();

    const prosResult = await triggerAITurn(sessionId, "closing", undefined, false);
    if (prosResult.success && prosResult.text) {
      addAITranscriptEntry({
        role: "attorney_plaintiff",
        text: prosResult.text,
        phase: "closing",
        attorney_name: prosResult.attorney_name || prosResult.speaker,
        speaker: prosResult.attorney_name || prosResult.speaker,
      });
      const prosBlob = await prefetchTTSAudio(prosResult.text, "attorney_plaintiff", prosResult.attorney_name || prosResult.speaker);
      const defClerkPrefetch = prefetchTTSAudio(defAnnounce, "judge", "Court Clerk");
      await speakAIText(prosResult.text, "attorney_plaintiff", prosResult.attorney_name || prosResult.speaker, prosBlob);
      await waitForSpeechComplete();

      await new Promise((r) => setTimeout(r, 800));

      setAiTurnMessage("Generating defense closing argument...");
      addSystemMessage(defAnnounce, "closing");
      const defClerkBlob = await defClerkPrefetch;
      await speakClerk(defAnnounce, defClerkBlob);
      await waitForSpeechComplete();
    } else {
      await new Promise((r) => setTimeout(r, 800));

      setAiTurnMessage("Generating defense closing argument...");
      addSystemMessage(defAnnounce, "closing");
      const defClerkBlob = await prefetchTTSAudio(defAnnounce, "judge", "Court Clerk");
      await speakClerk(defAnnounce, defClerkBlob);
      await waitForSpeechComplete();
    }

    const defResult = await triggerAITurn(sessionId, "closing", undefined, false);
    if (defResult.success && defResult.text) {
      addAITranscriptEntry({
        role: "attorney_defense",
        text: defResult.text,
        phase: "closing",
        attorney_name: defResult.attorney_name || defResult.speaker,
        speaker: defResult.attorney_name || defResult.speaker,
      });
      const defBlob = await prefetchTTSAudio(defResult.text, "attorney_defense", defResult.attorney_name || defResult.speaker);
      await speakAIText(defResult.text, "attorney_defense", defResult.attorney_name || defResult.speaker, defBlob);
      await waitForSpeechComplete();
    }

    // Trigger live scoring after closings
    try {
      const scoreResp = await fetch(`${API_BASE}/api/scoring/${sessionId}/live-score`, { method: "POST" });
      if (scoreResp.ok) {
        const scoreData = await scoreResp.json();
        if (scoreData.scores) setLiveScores((prev) => ({ ...prev, ...scoreData.scores }));
      }
    } catch { /* non-critical */ }

    saveTranscript(sessionId);
    setAiTurnMessage(null);
    setIsAITurnInProgress(false);
  }, [sessionId, addSystemMessage, addAITranscriptEntry, speakClerk, speakAIText, prefetchTTSAudio, waitForSpeechComplete]);

  // Handle phase advancement
  const handleAdvancePhase = useCallback(async (targetPhase: string) => {
    setIsAdvancingPhase(true);
    setPhaseError(null);
    const isSpectator = sessionStatus?.humanRole === "spectator";

    let lastAdvanceError = "";

    const tryAdvance = async (phase: string): Promise<boolean> => {
      try {
        const result = await advancePhase(sessionId, phase);
        if (result.success) {
          setTrialState((prev) => ({ ...prev, phase: result.current_phase as TrialPhase }));
          return true;
        }
        lastAdvanceError = result.message || "Phase advancement failed";
        console.warn(`Phase advance to ${phase} returned:`, lastAdvanceError);
        if (result.message?.includes("Cannot transition")) {
          try {
            const stateResp = await fetch(`${API_BASE}/api/trial/${sessionId}/state`);
            if (stateResp.ok) {
              const stateData = await stateResp.json();
              setTrialState((prev) => ({ ...prev, phase: stateData.phase as TrialPhase }));
              if (stateData.phase?.toLowerCase() === phase.toLowerCase()) return true;
            }
          } catch { /* ignore */ }
        }
        return false;
      } catch (err) {
        lastAdvanceError = err instanceof Error ? err.message : "Network error";
        console.error(`advance-phase error for ${phase}:`, lastAdvanceError);
        return false;
      }
    };

    try {
      if (targetPhase === "opening") {
        const ok = await tryAdvance("opening");
        if (!ok) { setPhaseError(lastAdvanceError || "Could not advance to opening phase"); return; }
        try {
          await runOpeningSequence();
        } catch (err) {
          console.error("Opening sequence error (continuing):", err);
        }
        if (isSpectator) {
          setIsAdvancingPhase(false);
          handleAdvancePhase("direct");
          return;
        }
      } else if (targetPhase === "direct") {
        const ok = await tryAdvance("direct");
        if (!ok) { setPhaseError(lastAdvanceError || "Could not advance to direct examination"); return; }
        try {
          await runFullExaminationFlow();
        } catch (err) {
          console.error("Examination flow error (continuing):", err);
        }
        if (isSpectator) {
          setIsAdvancingPhase(false);
          handleAdvancePhase("closing");
          return;
        }
      } else if (targetPhase === "closing") {
        const ok = await tryAdvance("closing");
        if (!ok) { setPhaseError(lastAdvanceError || "Could not advance to closing arguments"); return; }
        if (isSpectator) {
          try {
            await runClosingSequence();
          } catch (err) {
            console.error("Closing sequence error (continuing):", err);
          }
          setIsAdvancingPhase(false);
          handleAdvancePhase("scoring");
          return;
        }
      } else {
        const ok = await tryAdvance(targetPhase);
        if (!ok) { setPhaseError(lastAdvanceError || `Could not advance to ${targetPhase}`); return; }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      console.error("Error in handleAdvancePhase:", msg);
      setPhaseError(`Failed to advance: ${msg}`);
    } finally {
      setIsAdvancingPhase(false);
    }
  }, [sessionId, sessionStatus?.humanRole, runOpeningSequence, runFullExaminationFlow, runClosingSequence]);

  // Get next phase for current state
  const getNextPhase = useCallback((): string | null => {
    const phaseOrder = ["prep", "opening", "direct", "cross", "redirect", "recross", "closing", "scoring"];
    const currentIndex = phaseOrder.indexOf(normalizePhase(trialState.phase));
    if (currentIndex < 0 || currentIndex >= phaseOrder.length - 1) return null;
    return phaseOrder[currentIndex + 1];
  }, [trialState.phase]);

  // Poll for initialization (must be before any early returns to respect Rules of Hooks)
  useEffect(() => {
    if (sessionStatus?.initialized) return;
    const poll = setInterval(async () => {
      try {
        const status = await fetchSessionStatus(sessionId);
        if (status.initialized) {
          setSessionStatus(status);
          clearInterval(poll);
        }
      } catch { /* keep polling */ }
    }, 1500);
    return () => clearInterval(poll);
  }, [sessionId, sessionStatus?.initialized]);

  // Get phase config — during examination, use currentExamPhase so the header
  // updates as Direct → Cross → Redirect → Recross for the active witness.
  const rawNormalizedPhase = normalizePhase(trialState.phase);
  const isExamPhase = ["direct", "cross", "redirect", "recross"].includes(rawNormalizedPhase);
  const normalizedPhase: TrialPhase = isExamPhase
    ? (currentExamPhase as TrialPhase)
    : rawNormalizedPhase;
  const currentPhaseConfig = phaseConfig[normalizedPhase];
  const humanRoleConfig = sessionStatus?.humanRole ? roleConfig[sessionStatus.humanRole] : null;

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 flex items-center justify-center">
        <div className="text-center">
          <div className="relative w-20 h-20 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-blue-500/30 rounded-full" />
            <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin" />
            <div className="absolute inset-2 border-4 border-transparent border-t-amber-500 rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
            <GavelIcon className="absolute inset-0 m-auto w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">Entering Courtroom</h2>
          <p className="text-slate-400">Preparing your session...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 flex items-center justify-center p-4">
        <div className="bg-slate-800/50 backdrop-blur-sm border border-red-500/30 rounded-2xl p-8 max-w-md text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/20 flex items-center justify-center">
            <AlertIcon className="w-8 h-8 text-red-400" />
          </div>
          <h1 className="text-xl font-bold text-white mb-2">Failed to Load Courtroom</h1>
          <p className="text-slate-400 mb-6">{error}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => router.push('/')}
              className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
            >
              Go Home
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!sessionStatus?.initialized) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 flex items-center justify-center p-4">
        <div className="bg-slate-800/50 backdrop-blur-sm border border-amber-500/30 rounded-2xl p-8 max-w-md text-center">
          <div className="w-20 h-20 mx-auto mb-6 relative">
            <div className="absolute inset-0 border-4 border-amber-500/20 rounded-full" />
            <div className="absolute inset-0 border-4 border-transparent border-t-amber-500 rounded-full animate-spin" />
            <div className="absolute inset-2 border-4 border-transparent border-t-blue-400 rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
            <div className="absolute inset-0 flex items-center justify-center text-2xl">⚖️</div>
          </div>
          <h1 className="text-xl font-bold text-white mb-2">Preparing Courtroom</h1>
          <p className="text-slate-400 mb-4">Setting up agents and generating case strategy...</p>
          <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-amber-500 to-orange-500 rounded-full animate-pulse" style={{ width: '60%' }} />
          </div>
          <p className="text-xs text-slate-500 mt-3">This is faster on subsequent runs for the same case</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950">
      {/* Ambient background effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className={`absolute top-0 left-1/4 w-96 h-96 bg-gradient-to-br ${currentPhaseConfig.bgGradient} rounded-full blur-3xl opacity-20 transition-all duration-1000`} />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-purple-600/10 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative z-10 border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* Left: Home + Phase indicator */}
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push("/")}
                className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors"
                title="Home"
              >
                <HomeIcon className="w-5 h-5" />
                <span className="hidden sm:inline text-sm">Home</span>
              </button>
              <div className="h-8 w-px bg-slate-700" />
              <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${currentPhaseConfig.bgGradient} flex items-center justify-center shadow-lg`}>
                <span className="text-2xl">{currentPhaseConfig.icon}</span>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-bold text-white">{currentPhaseConfig.label}</h1>
                  <div className={`w-2 h-2 rounded-full ${currentPhaseConfig.color} animate-pulse`} />
                </div>
                <p className="text-sm text-slate-400">{currentPhaseConfig.description}</p>
              </div>
            </div>

            {/* Right: Role & Status */}
            <div className="flex items-center gap-4">
              {/* Judge interrupting alert */}
              {trialState.isJudgeInterrupting && (
                <div className="flex items-center gap-2 px-4 py-2 bg-purple-500/20 border border-purple-400/50 rounded-xl animate-pulse">
                  <GavelIcon className="w-5 h-5 text-purple-400" />
                  <span className="text-sm font-semibold text-purple-300">ORDER IN THE COURT!</span>
                </div>
              )}

              {/* Current speaker indicator */}
              {isAISpeaking && aiSpeakerName && (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/20 border border-blue-400/30 rounded-xl">
                  <VolumeIcon className="w-4 h-4 text-blue-400 animate-pulse" />
                  <span className="text-xs text-blue-300">{aiSpeakerName}</span>
                </div>
              )}

              {/* Next Phase Button - hidden during testimony phases (exam flow manages transitions) */}
              {(() => {
                const isTestimony = ["direct", "cross", "redirect", "recross"].includes(normalizedPhase);
                if (isTestimony) return null;
                if (normalizedPhase === "prep" || normalizedPhase === "scoring" || !getNextPhase()) return null;
                return (
                  <button
                    onClick={() => handleAdvancePhase(getNextPhase()!)}
                    disabled={isAdvancingPhase}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:from-slate-700 disabled:to-slate-600 text-white font-medium rounded-xl transition-all"
                  >
                    {isAdvancingPhase ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Advancing...</span>
                      </>
                    ) : (
                      <>
                        <span>Next: {phaseConfig[getNextPhase() as TrialPhase]?.label || getNextPhase()}</span>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                        </svg>
                      </>
                    )}
                  </button>
                );
              })()}

              {phaseError && (
                <div className="px-3 py-1.5 bg-red-500/20 border border-red-500/30 rounded-xl text-red-300 text-sm flex items-center gap-2">
                  <span>{phaseError}</span>
                  <button onClick={() => setPhaseError(null)} className="text-red-400 hover:text-red-200 font-bold">×</button>
                </div>
              )}

              {/* Human role badge */}
              {humanRoleConfig && (
                <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/80 border border-slate-600/50 rounded-xl">
                  <span className="text-lg">{humanRoleConfig.icon}</span>
                  <div>
                    <div className="text-xs text-slate-500">Your Role</div>
                    <div className={`text-sm font-medium ${humanRoleConfig.color}`}>
                      {humanRoleConfig.label}
                      {sessionStatus?.attorneySubRole && (
                        <span className="text-slate-400 font-normal">
                          {" "}({sessionStatus.attorneySubRole === "opening" ? "Opening" : sessionStatus.attorneySubRole === "direct_cross" ? "Direct/Cross" : "Closing"})
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="relative z-10 max-w-7xl mx-auto px-4 py-6 pb-24">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* Left column: Tips & Info Panel (collapsible) */}
          <div className="lg:col-span-3 space-y-4">
            {/* Tips Card */}
            <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-2xl overflow-hidden">
              <button 
                onClick={() => setShowTips(!showTips)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">💡</span>
                  <span className="font-medium text-white">Phase Tips</span>
                </div>
                <svg 
                  className={`w-5 h-5 text-slate-400 transition-transform ${showTips ? 'rotate-180' : ''}`} 
                  fill="none" 
                  viewBox="0 0 24 24" 
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showTips && (
                <div className="px-4 pb-4 space-y-2">
                  {currentPhaseConfig.tips.map((tip, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm">
                      <CheckIcon className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                      <span className="text-slate-300">{tip}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Case Info */}
            {sessionStatus.caseId && (
              <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <DocumentIcon className="w-5 h-5 text-amber-400" />
                  <span className="font-medium text-white">Case</span>
                </div>
                <p className="text-sm text-slate-300">{sessionStatus.caseName || sessionStatus.caseId}</p>
              </div>
            )}

            {/* Quick Actions */}
            <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-4 space-y-3">
              <div className="flex items-center gap-2 mb-2">
                <PlayIcon className="w-5 h-5 text-blue-400" />
                <span className="font-medium text-white">Quick Actions</span>
              </div>
              <button 
                onClick={() => {
                  setMaterialsModalTab("overview");
                  setIsMaterialsModalOpen(true);
                }}
                className="w-full px-3 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors text-left flex items-center gap-2"
              >
                <DocumentIcon className="w-4 h-4 text-amber-400" />
                View Case Materials
              </button>
              <button 
                onClick={() => {
                  setMaterialsModalTab("witnesses");
                  setIsMaterialsModalOpen(true);
                }}
                className="w-full px-3 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors text-left flex items-center gap-2"
              >
                <UserIcon className="w-4 h-4 text-blue-400" />
                Review Witnesses
              </button>
              <button 
                onClick={() => {
                  setMaterialsModalTab("exhibits");
                  setIsMaterialsModalOpen(true);
                }}
                className="w-full px-3 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors text-left flex items-center gap-2"
              >
                <FolderIcon className="w-4 h-4 text-emerald-400" />
                View Exhibits
              </button>
              <button 
                onClick={() => {
                  setMaterialsModalTab("files");
                  setIsMaterialsModalOpen(true);
                }}
                className="w-full px-3 py-2 bg-amber-600/30 hover:bg-amber-600/50 text-amber-300 text-sm rounded-lg transition-colors text-left flex items-center gap-2"
              >
                <DocumentIcon className="w-4 h-4 text-amber-400" />
                Open Case Files (PDFs)
              </button>
              <button 
                onClick={() => setIsPersonaModalOpen(true)}
                className="w-full px-3 py-2 bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 text-sm rounded-lg transition-colors text-left flex items-center gap-2"
              >
                <UserIcon className="w-4 h-4 text-purple-400" />
                Customize AI Team Personas
              </button>
            </div>
          </div>

          {/* Center column: Preparation (during PREP) or Transcript */}
          <div className="lg:col-span-6">
            {normalizedPhase === "prep" ? (
              <div className="flex flex-col h-full">
                <PreparationPanel
                  sessionId={sessionId}
                  humanRole={sessionStatus.humanRole}
                  className="flex-1"
                  style={{ maxHeight: 'calc(100vh - 290px)' }}
                  onOpeningsReady={(ready) => setOpeningsReady(ready)}
                  onPrepComplete={(complete) => setPrepComplete(complete)}
                />
                {/* Begin Trial Button */}
                <div className="mt-4">
                  <button
                    onClick={() => handleAdvancePhase("opening")}
                    disabled={isAdvancingPhase || openingsReady !== true}
                    className="w-full py-4 px-6 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:from-slate-700 disabled:to-slate-600 text-white font-bold text-lg rounded-xl shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 transition-all flex items-center justify-center gap-3 group"
                  >
                    {isAdvancingPhase ? (
                      <>
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Starting Trial...
                      </>
                    ) : prepComplete === null && openingsReady === null ? (
                      <>
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Checking trial readiness...
                      </>
                    ) : prepComplete !== true ? (
                      <>
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Preparing trial materials...
                      </>
                    ) : openingsReady !== true ? (
                      <>
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Generating opening statements...
                      </>
                    ) : (
                      <>
                        <span className="text-2xl group-hover:scale-110 transition-transform">⚖️</span>
                        Begin Trial - Opening Statements
                        <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                        </svg>
                      </>
                    )}
                  </button>
                  {openingsReady !== true && (
                    <p className="text-xs text-amber-400 text-center mt-2 animate-pulse">
                      {prepComplete !== true
                        ? "Trial materials are being prepared. Review tabs above for progress."
                        : "Opening statements are being prepared. Check the Openings tab for progress."}
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-2xl overflow-hidden h-full">
                <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <DocumentIcon className="w-5 h-5 text-slate-400" />
                    <span className="font-medium text-white">Court Transcript</span>
                  </div>
                  <span className="text-xs text-slate-500">{transcript.length} entries</span>
                </div>
                <div className="p-2" style={{ maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}>
                  {transcript.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                      <div className="w-16 h-16 rounded-full bg-slate-700/50 flex items-center justify-center mb-4">
                        <MicIcon className="w-8 h-8 text-slate-500" />
                      </div>
                      <h3 className="text-lg font-medium text-slate-400 mb-2">No Transcript Yet</h3>
                      <p className="text-sm text-slate-500 max-w-xs">
                        Begin speaking to start the transcript. All statements will be recorded here.
                      </p>
                    </div>
                  ) : (
                    <TranscriptPanel
                      entries={transcript}
                      currentPhase={normalizedPhase}
                      showPhaseSeparators={true}
                      showTimestamps={true}
                      highlightSpeaker={trialState.currentSpeaker}
                      maxHeight="calc(100vh - 260px)"
                      className="h-full"
                    />
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Right column: Controls */}
          <div className="lg:col-span-3 space-y-4">
            {/* Live Scores & Objection Counter Panel — collapsible */}
            <div className="bg-slate-800/50 backdrop-blur-sm border border-emerald-500/30 rounded-2xl overflow-hidden">
              <button
                onClick={() => setScoresCollapsed(!scoresCollapsed)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/20 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span className="font-medium text-white text-sm">Scores & Stats</span>
                  {scoresCollapsed && Object.keys(liveScores).length > 0 && (
                    <span className="text-[10px] text-slate-400 ml-1">({Object.keys(liveScores).length} scored)</span>
                  )}
                </div>
                <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${!scoresCollapsed ? "rotate-180" : ""}`} />
              </button>

              {!scoresCollapsed && (
                <div className="px-4 pb-4 space-y-3">
                  {/* Score bars grouped by side */}
                  <div className="space-y-2">
                    {Object.keys(liveScores).length > 0 ? (
                      (() => {
                        const entries = Object.entries(liveScores);
                        const prosEntries = entries.filter(([k, s]) => {
                          const v = s as any;
                          if (k.startsWith("attorney_")) return k.startsWith("attorney_plaintiff");
                          return v.side === "Prosecution" || v.side !== "Defense";
                        });
                        const defEntries = entries.filter(([k, s]) => {
                          const v = s as any;
                          if (k.startsWith("attorney_")) return k.startsWith("attorney_defense");
                          return v.side === "Defense";
                        });

                        const renderScoreEntry = ([key, score]: [string, any]) => {
                          const s = score as any;
                          const isAttorney = key.startsWith("attorney_");
                          const isWitness = key.startsWith("witness_");
                          let label: string;
                          let sideTag: string;
                          let roleLabel: string;
                          if (isAttorney) {
                            const isProsAtty = key.startsWith("attorney_plaintiff");
                            label = s.name || (isProsAtty ? "Prosecution Atty" : "Defense Atty");
                            sideTag = s.side || (isProsAtty ? "Prosecution" : "Defense");
                            roleLabel = s.attorney_sub_role
                              ? s.attorney_sub_role
                              : isProsAtty ? "Prosecution Attorney" : "Defense Attorney";
                          } else if (isWitness) {
                            label = s.name || "Witness";
                            sideTag = s.side || (() => {
                              const wCalledBy = witnesses.find((w) => key.includes(w.id))?.called_by;
                              return wCalledBy === "defense" ? "Defense" : "Prosecution";
                            })();
                            roleLabel = s.witness_role || "Witness";
                          } else {
                            label = s.name || key;
                            sideTag = "";
                            roleLabel = s.role || "";
                          }
                          const avg = s.average || 0;
                          const isPros = sideTag === "Prosecution";
                          const barColor = isAttorney
                            ? isPros ? "bg-blue-500" : "bg-red-500"
                            : "bg-amber-500";
                          const shortTag = isPros ? "PROS" : "DEF";
                          return (
                            <div key={key} className="space-y-0.5">
                              <div className="flex items-center gap-1.5">
                                <span className={`text-[9px] font-bold px-1 py-px rounded ${isPros ? "bg-blue-500/20 text-blue-400" : "bg-red-500/20 text-red-400"}`}>
                                  {shortTag}
                                </span>
                                <span className="text-xs text-white font-medium truncate" title={`${label} — ${roleLabel}`}>
                                  {label}
                                </span>
                                <span className="text-[10px] text-slate-500 ml-auto truncate max-w-[90px]" title={roleLabel}>{roleLabel}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full ${barColor} rounded-full transition-all duration-500`}
                                    style={{ width: `${(avg / 10) * 100}%` }}
                                  />
                                </div>
                                <span className="text-xs font-mono text-slate-200 w-8 text-right">{avg}/10</span>
                              </div>
                            </div>
                          );
                        };

                        return (
                          <>
                            {prosEntries.length > 0 && (
                              <div className="space-y-1.5">
                                <div className="text-[10px] font-semibold text-blue-400 uppercase tracking-wider">Prosecution</div>
                                {prosEntries.map(renderScoreEntry)}
                              </div>
                            )}
                            {defEntries.length > 0 && (
                              <div className="space-y-1.5">
                                <div className="text-[10px] font-semibold text-red-400 uppercase tracking-wider">Defense</div>
                                {defEntries.map(renderScoreEntry)}
                              </div>
                            )}
                          </>
                        );
                      })()
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">Scores update after witness examination</span>
                      </div>
                    )}
                  </div>

                  {/* Objection counter */}
                  <div className="border-t border-slate-700/50 pt-2">
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-slate-400 font-medium">Objections:</span>
                      <span className="text-blue-400">Pros {objectionCounts.prosecution}</span>
                      <span className="text-red-400">Def {objectionCounts.defense}</span>
                      <span className="text-emerald-400">Sustained {objectionCounts.sustained}</span>
                      <span className="text-amber-400">Overruled {objectionCounts.overruled}</span>
                    </div>
                  </div>

                  {/* View detailed scores link */}
                  {Object.keys(liveScores).length > 0 && (
                    <div className="border-t border-slate-700/50 pt-2">
                      <button
                        onClick={() => window.open(`/scores/${sessionId}`, "_blank")}
                        className="w-full py-2 text-xs text-amber-400 hover:text-amber-300 hover:bg-slate-700/30 rounded-lg transition-colors flex items-center justify-center gap-1"
                      >
                        View Detailed Scores
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Team Memory Viewer */}
            {normalizedPhase !== "prep" && (
              <div className="bg-slate-800/50 backdrop-blur-sm border border-purple-500/30 rounded-2xl overflow-hidden">
                <button
                  onClick={async () => {
                    if (!teamMemoryOpen) {
                      try {
                        const res = await fetch(`${API_BASE}/api/trial/${sessionId}/team-memory`);
                        if (res.ok) setTeamMemory(await res.json());
                      } catch { /* non-critical */ }
                    }
                    setTeamMemoryOpen((p) => !p);
                  }}
                  className="w-full flex items-center justify-between px-4 py-3 cursor-pointer hover:opacity-80 transition-opacity"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm">🧠</span>
                    <span className="font-medium text-white text-sm">Team Memory</span>
                  </div>
                  <span className={`text-xs text-slate-500 transition-transform ${teamMemoryOpen ? "rotate-180" : ""}`}>▲</span>
                </button>
                {teamMemoryOpen && (
                  <div className="px-4 pb-4 space-y-3">
                    {/* Side toggle */}
                    <div className="flex gap-1 bg-slate-900/50 rounded-lg p-0.5">
                      {(["plaintiff", "defense"] as const).map((s) => (
                        <button
                          key={s}
                          onClick={() => setTeamMemorySide(s)}
                          className={`flex-1 py-1 text-xs rounded-md transition-colors ${
                            teamMemorySide === s
                              ? s === "plaintiff" ? "bg-blue-600 text-white" : "bg-red-600 text-white"
                              : "text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          {s === "plaintiff" ? "Prosecution" : "Defense"}
                        </button>
                      ))}
                    </div>
                    {/* Refresh button */}
                    <button
                      onClick={async () => {
                        try {
                          const res = await fetch(`${API_BASE}/api/trial/${sessionId}/team-memory`);
                          if (res.ok) setTeamMemory(await res.json());
                        } catch { /* non-critical */ }
                      }}
                      className="w-full py-1 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
                    >
                      Refresh
                    </button>
                    {/* Memory content */}
                    {teamMemory && teamMemory[teamMemorySide] ? (() => {
                      const mem = teamMemory[teamMemorySide];
                      const isEmpty = !mem.facts?.length && !mem.weaknesses?.length && !mem.directives?.length && !mem.heard?.length;
                      if (isEmpty) return <p className="text-xs text-slate-500 italic">No shared memory yet for this side.</p>;
                      return (
                        <div className="space-y-2 text-xs">
                          {mem.directives?.length > 0 && (
                            <div>
                              <div className="text-purple-400 font-semibold uppercase tracking-wider text-[10px] mb-1">Case Theory / Directives</div>
                              {mem.directives.map((d: string, i: number) => (
                                <p key={i} className="text-slate-300 pl-2 border-l border-purple-500/30 mb-1">{d}</p>
                              ))}
                            </div>
                          )}
                          {mem.facts?.length > 0 && (
                            <div>
                              <div className="text-emerald-400 font-semibold uppercase tracking-wider text-[10px] mb-1">Facts Established</div>
                              {mem.facts.map((f: any, i: number) => (
                                <p key={i} className="text-slate-300 pl-2 border-l border-emerald-500/30 mb-1">
                                  <span className="text-slate-500">[{f.source}]</span> {f.fact}
                                </p>
                              ))}
                            </div>
                          )}
                          {mem.weaknesses?.length > 0 && (
                            <div>
                              <div className="text-amber-400 font-semibold uppercase tracking-wider text-[10px] mb-1">Opposing Weaknesses</div>
                              {mem.weaknesses.map((w: any, i: number) => (
                                <p key={i} className="text-slate-300 pl-2 border-l border-amber-500/30 mb-1">
                                  <span className="text-slate-500">[{w.source}]</span> {w.detail}
                                </p>
                              ))}
                            </div>
                          )}
                          {mem.heard?.length > 0 && (
                            <div>
                              <div className="text-sky-400 font-semibold uppercase tracking-wider text-[10px] mb-1">Courtroom Observations</div>
                              {mem.heard.slice(-8).map((h: any, i: number) => (
                                <p key={i} className="text-slate-300 pl-2 border-l border-sky-500/30 mb-1">
                                  <span className="text-slate-500">{h.speaker}:</span> {h.summary}
                                </p>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })() : <p className="text-xs text-slate-500 italic">Loading...</p>}
                  </div>
                )}
              </div>
            )}

            {/* Speech Playback Bar */}
            {isAISpeaking && (
              <div className="bg-slate-800/50 backdrop-blur-sm border border-blue-500/30 rounded-2xl p-4">
                <div className="flex items-center gap-3 mb-3">
                  <VolumeIcon className="w-5 h-5 text-blue-400 animate-pulse" />
                  <span className="font-medium text-white truncate flex-1">{aiSpeakerName || "Speaking..."}</span>
                  <button
                    onClick={stopAISpeech}
                    className="px-3 py-1 text-xs bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/30 transition-colors"
                  >
                    Stop
                  </button>
                </div>

                {/* Progress bar */}
                {speechDuration > 0 && (
                  <div className="mb-3">
                    <div
                      className="relative w-full h-2 bg-slate-700 rounded-full cursor-pointer group"
                      onClick={(e) => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        const pct = (e.clientX - rect.left) / rect.width;
                        handleSeek(pct * speechDuration);
                      }}
                    >
                      <div
                        className="absolute left-0 top-0 h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all"
                        style={{ width: `${Math.min((speechProgress / speechDuration) * 100, 100)}%` }}
                      />
                      <div
                        className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow opacity-0 group-hover:opacity-100 transition-opacity"
                        style={{ left: `${Math.min((speechProgress / speechDuration) * 100, 100)}%` }}
                      />
                    </div>
                    <div className="flex justify-between mt-1 text-xs text-slate-500">
                      <span>{formatTime(speechProgress)}</span>
                      <span>{formatTime(speechDuration)}</span>
                    </div>
                  </div>
                )}

                {/* Speed controls */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Speed:</span>
                  {[1, 1.25, 1.5, 2].map((s) => (
                    <button
                      key={s}
                      onClick={() => handleSpeedChange(s)}
                      className={`px-2 py-0.5 text-xs rounded-md transition-colors ${
                        speechSpeed === s
                          ? "bg-blue-600 text-white"
                          : "bg-slate-700 text-slate-400 hover:bg-slate-600"
                      }`}
                    >
                      {s}x
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Mic Input - only show when it's the human's turn to speak (not for spectators) */}
            {(() => {
              if (sessionStatus?.humanRole === "spectator") return null;
              const sub = sessionStatus?.attorneySubRole || "direct_cross";
              const showMic =
                (normalizedPhase === "opening" && sub === "opening") ||
                ((normalizedPhase === "direct" || normalizedPhase === "cross" ||
                  normalizedPhase === "redirect" || normalizedPhase === "recross") && sub === "direct_cross") ||
                (normalizedPhase === "closing" && sub === "closing");
              if (!showMic) return null;
              return (
                <div className="bg-slate-800/50 backdrop-blur-sm border border-emerald-500/30 rounded-2xl p-6">
                  <div className="flex items-center gap-2 mb-4 justify-center">
                    <MicIcon className="w-5 h-5 text-emerald-400" />
                    <span className="font-medium text-white">Your Turn — Speak</span>
                  </div>
                  <MicInput
                    sessionId={sessionId}
                    trialState={trialState}
                    permissions={permissions}
                    onTranscription={handleTranscription}
                    size="lg"
                    className="flex justify-center"
                  />
                  <p className="text-xs text-slate-500 text-center mt-3">
                    {permissions.canSpeak ? "Hold to speak" : permissions.reason}
                  </p>
                </div>
              );
            })()}

            {/* AI Turn Controls & Witness Stand */}
            {normalizedPhase !== "prep" && normalizedPhase !== "scoring" && (() => {
              const subRole = sessionStatus.attorneySubRole || "direct_cross";
              const humanIsOpening = subRole === "opening";
              const humanIsDirectCross = subRole === "direct_cross";
              const humanIsClosing = subRole === "closing";
              const humanIsPlaintiff = sessionStatus.humanRole?.includes("plaintiff");
              const opposingLabel = humanIsPlaintiff ? "Defense" : "Prosecution";
              const teammateLabel = humanIsPlaintiff ? "Prosecution" : "Defense";

              return (
                <div className="space-y-3">
                  {/* Witness Stand & Examination Flow */}
                  {(normalizedPhase === "direct" || normalizedPhase === "cross" ||
                    normalizedPhase === "redirect" || normalizedPhase === "recross") && (() => {
                    const prosWitnesses = witnesses.filter((w) => w.called_by === "plaintiff" || w.called_by === "prosecution");
                    const defWitnesses = witnesses.filter((w) => w.called_by === "defense");
                    const currentSideWitnesses = caseInChief === "defense" ? defWitnesses : prosWitnesses;
                    const examinedCount = currentSideWitnesses.filter((w) => w.is_examined).length;
                    const totalCount = currentSideWitnesses.length;
                    const remainingCount = currentSideWitnesses.filter((w) => w.is_pending).length;
                    const cicLabel = caseInChief === "defense" ? "Defense" : "Prosecution";

                    return (
                    <div className="bg-slate-800/50 backdrop-blur-sm border border-amber-500/30 rounded-2xl p-4">
                      {/* Case-in-chief header with witness counter — click to collapse */}
                      <button
                        onClick={() => setWitnessWindowCollapsed((p) => !p)}
                        className="w-full flex items-center justify-between text-left group cursor-pointer hover:opacity-80 transition-opacity"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-lg">⚖️</span>
                          <span className="font-medium text-white">
                            {cicLabel} Case-in-Chief
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-500/20 text-amber-400 rounded-full">
                            {examinedCount} / {totalCount} witnesses
                          </span>
                          {remainingCount > 0 && (
                            <span className="px-2 py-0.5 text-[10px] font-medium bg-slate-600/40 text-slate-300 rounded-full">
                              {remainingCount} remaining
                            </span>
                          )}
                          <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${!witnessWindowCollapsed ? "rotate-180" : ""}`} />
                        </div>
                      </button>

                      {!witnessWindowCollapsed && (<>
                      {/* Progress bar */}
                      <div className="w-full bg-slate-700/50 rounded-full h-1.5 mb-3 mt-3">
                        <div
                          className="bg-amber-500 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${totalCount > 0 ? (examinedCount / totalCount) * 100 : 0}%` }}
                        />
                      </div>

                      {/* Current witness on the stand */}
                      {currentWitnessId ? (
                        <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 mb-3">
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="text-xs text-amber-400/70 uppercase tracking-wider mb-1">On the Stand</div>
                              <div className="text-sm text-amber-300 font-semibold">
                                {currentWitnessName || witnesses.find((w) => w.id === currentWitnessId)?.name || "Witness"}
                              </div>
                            </div>
                            <span className="px-2 py-1 text-xs font-medium bg-amber-500/20 text-amber-300 rounded capitalize">
                              {normalizedPhase === "direct" ? "Direct Exam" :
                               normalizedPhase === "cross" ? "Cross Exam" :
                               normalizedPhase === "redirect" ? "Redirect" : "Recross"}
                            </span>
                          </div>
                          {isAITurnInProgress && aiTurnMessage && (
                            <div className="flex items-center gap-2 mt-2 text-xs text-slate-400">
                              <div className="w-3 h-3 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
                              {aiTurnMessage}
                            </div>
                          )}
                        </div>
                      ) : isAITurnInProgress ? (
                        <div className="bg-slate-700/30 border border-slate-600/30 rounded-lg p-3 mb-3">
                          <div className="flex items-center gap-2 text-sm text-slate-300">
                            <div className="w-4 h-4 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
                            {aiTurnMessage || "Processing examination..."}
                          </div>
                        </div>
                      ) : (
                        <div className="text-sm text-slate-400 mb-3">
                          {remainingCount > 0
                            ? "Examination will proceed automatically..."
                            : prosecutionRested && defenseRested
                              ? "All witnesses have been examined."
                              : `${cicLabel} has completed witness examination.`
                          }
                        </div>
                      )}

                      {/* Witness list showing status */}
                      <div className="space-y-1">
                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{cicLabel} Witnesses</div>
                        {currentSideWitnesses.map((w) => {
                          const side = w.called_by === "defense" ? "DEF" : "PROS";
                          const sideColor = w.called_by === "defense" ? "text-red-400" : "text-blue-400";
                          return (
                          <div
                            key={w.id}
                            className={`flex items-center justify-between py-1.5 px-2.5 rounded-lg text-sm ${
                              w.id === currentWitnessId
                                ? "bg-amber-500/15 text-amber-300 border border-amber-500/20"
                                : w.is_examined
                                  ? "text-slate-500 line-through"
                                  : "text-slate-400"
                            }`}
                          >
                            <span className="flex items-center gap-1.5">
                              <span className={`text-[9px] font-bold ${sideColor}`}>{side}</span>
                              {w.name}
                            </span>
                            <span className="text-[10px] uppercase">
                              {w.id === currentWitnessId
                                ? "testifying"
                                : w.is_examined
                                  ? "done"
                                  : "pending"
                              }
                            </span>
                          </div>
                          );
                        })}
                      </div>

                      {/* Side status */}
                      {prosecutionRested && (
                        <div className="mt-2 pt-2 border-t border-slate-700/50 text-xs text-emerald-400">
                          Prosecution has rested.
                        </div>
                      )}
                      {defenseRested && (
                        <div className="mt-1 text-xs text-emerald-400">
                          Defense has rested.
                        </div>
                      )}
                      </>)}
                    </div>
                    );
                  })()}

                  {/* Opposing side AI Controls (not for spectators - everything is auto) */}
                  {sessionStatus.humanRole !== "spectator" && <div className="bg-slate-800/50 backdrop-blur-sm border border-indigo-500/30 rounded-2xl p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <UserIcon className="w-5 h-5 text-indigo-400" />
                      <span className="font-medium text-white">{opposingLabel}</span>
                      {isAITurnInProgress && (
                        <div className="w-4 h-4 border-2 border-indigo-400/30 border-t-indigo-400 rounded-full animate-spin ml-auto" />
                      )}
                    </div>
                    <div className="space-y-2">
                      {normalizedPhase === "opening" && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleAITurn("opening")}
                            disabled={isAITurnInProgress}
                            className="flex-1 py-2 px-3 bg-indigo-600/30 hover:bg-indigo-600/50 disabled:bg-slate-700/30 text-indigo-300 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                          >
                            {isAITurnInProgress ? "Generating..." : "Opposing Opening Statement"}
                          </button>
                          <button
                            onClick={() => handleAITurn("opening", undefined, false, true)}
                            disabled={isAITurnInProgress}
                            title="Regenerate"
                            className="py-2 px-2.5 bg-amber-600/20 hover:bg-amber-600/40 disabled:bg-slate-700/30 text-amber-300 text-sm rounded-lg transition-colors"
                          >
                            &#8635;
                          </button>
                        </div>
                      )}
                      {(normalizedPhase === "cross" || normalizedPhase === "recross") && (
                        <button
                          onClick={() => handleAITurn("cross_question", currentWitnessId || undefined)}
                          disabled={isAITurnInProgress || !currentWitnessId}
                          className="w-full py-2 px-3 bg-indigo-600/30 hover:bg-indigo-600/50 disabled:bg-slate-700/30 text-indigo-300 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                        >
                          {isAITurnInProgress ? "Generating..." : !currentWitnessId ? "Call a witness first" : "Opposing Cross-Examination"}
                        </button>
                      )}
                      {(normalizedPhase === "direct" || normalizedPhase === "redirect") && (
                        <button
                          onClick={() => handleAITurn("direct_question", currentWitnessId || undefined)}
                          disabled={isAITurnInProgress || !currentWitnessId}
                          className="w-full py-2 px-3 bg-indigo-600/30 hover:bg-indigo-600/50 disabled:bg-slate-700/30 text-indigo-300 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                        >
                          {isAITurnInProgress ? "Generating..." : !currentWitnessId ? "Call a witness first" : "Opposing Direct Question"}
                        </button>
                      )}
                      {(normalizedPhase === "direct" || normalizedPhase === "cross" || normalizedPhase === "redirect" || normalizedPhase === "recross") && (
                        <button
                          onClick={() => handleAITurn("witness_answer", currentWitnessId || undefined)}
                          disabled={isAITurnInProgress || !currentWitnessId}
                          className="w-full py-2 px-3 bg-emerald-600/30 hover:bg-emerald-600/50 disabled:bg-slate-700/30 text-emerald-300 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                        >
                          {isAITurnInProgress ? "Generating..." : !currentWitnessId ? "Call a witness first" : "Witness Answer"}
                        </button>
                      )}
                      {normalizedPhase === "closing" && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleAITurn("closing")}
                            disabled={isAITurnInProgress}
                            className="flex-1 py-2 px-3 bg-indigo-600/30 hover:bg-indigo-600/50 disabled:bg-slate-700/30 text-indigo-300 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                          >
                            {isAITurnInProgress ? "Generating..." : "Opposing Closing Argument"}
                          </button>
                          <button
                            onClick={() => handleAITurn("closing", undefined, false, true)}
                            disabled={isAITurnInProgress}
                            title="Regenerate"
                            className="py-2 px-2.5 bg-amber-600/20 hover:bg-amber-600/40 disabled:bg-slate-700/30 text-amber-300 text-sm rounded-lg transition-colors"
                          >
                            &#8635;
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  }

                  {/* AI Teammate Controls - only shown for non-spectator, phases the human doesn't handle */}
                  {sessionStatus.humanRole !== "spectator" && ((normalizedPhase === "opening" && !humanIsOpening) ||
                    ((normalizedPhase === "direct" || normalizedPhase === "cross" || normalizedPhase === "redirect" || normalizedPhase === "recross") && !humanIsDirectCross) ||
                    (normalizedPhase === "closing" && !humanIsClosing)) && (
                    <div className="bg-slate-800/50 backdrop-blur-sm border border-teal-500/30 rounded-2xl p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <UserIcon className="w-5 h-5 text-teal-400" />
                        <span className="font-medium text-white">{teammateLabel}</span>
                        <span className="text-xs text-teal-400/70 ml-auto">AI Teammate</span>
                      </div>
                      <div className="space-y-2">
                        {normalizedPhase === "opening" && !humanIsOpening && (
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleAITurn("opening", undefined, true)}
                              disabled={isAITurnInProgress}
                              className="flex-1 py-2 px-3 bg-teal-600/30 hover:bg-teal-600/50 disabled:bg-slate-700/30 text-teal-300 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                            >
                              {isAITurnInProgress ? "Generating..." : "Teammate Opening Statement"}
                            </button>
                            <button
                              onClick={() => handleAITurn("opening", undefined, true, true)}
                              disabled={isAITurnInProgress}
                              title="Regenerate"
                              className="py-2 px-2.5 bg-amber-600/20 hover:bg-amber-600/40 disabled:bg-slate-700/30 text-amber-300 text-sm rounded-lg transition-colors"
                            >
                              &#8635;
                            </button>
                          </div>
                        )}
                        {(normalizedPhase === "direct" || normalizedPhase === "redirect") && !humanIsDirectCross && (
                          <button
                            onClick={() => handleAITurn("direct_question", currentWitnessId || undefined, true)}
                            disabled={isAITurnInProgress || !currentWitnessId}
                            className="w-full py-2 px-3 bg-teal-600/30 hover:bg-teal-600/50 disabled:bg-slate-700/30 text-teal-300 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                          >
                            {isAITurnInProgress ? "Generating..." : !currentWitnessId ? "Call a witness first" : "Teammate Direct Question"}
                          </button>
                        )}
                        {(normalizedPhase === "cross" || normalizedPhase === "recross") && !humanIsDirectCross && (
                          <button
                            onClick={() => handleAITurn("cross_question", currentWitnessId || undefined, true)}
                            disabled={isAITurnInProgress || !currentWitnessId}
                            className="w-full py-2 px-3 bg-teal-600/30 hover:bg-teal-600/50 disabled:bg-slate-700/30 text-teal-300 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                          >
                            {isAITurnInProgress ? "Generating..." : !currentWitnessId ? "Call a witness first" : "Teammate Cross-Examination"}
                          </button>
                        )}
                        {normalizedPhase === "closing" && !humanIsClosing && (
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleAITurn("closing", undefined, true)}
                              disabled={isAITurnInProgress}
                              className="flex-1 py-2 px-3 bg-teal-600/30 hover:bg-teal-600/50 disabled:bg-slate-700/30 text-teal-300 text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
                            >
                              {isAITurnInProgress ? "Generating..." : "Teammate Closing Argument"}
                            </button>
                            <button
                              onClick={() => handleAITurn("closing", undefined, true, true)}
                              disabled={isAITurnInProgress}
                              title="Regenerate"
                              className="py-2 px-2.5 bg-amber-600/20 hover:bg-amber-600/40 disabled:bg-slate-700/30 text-amber-300 text-sm rounded-lg transition-colors"
                            >
                              &#8635;
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {aiTurnMessage && (
                    witnessWindowCollapsed ||
                    !(normalizedPhase === "direct" || normalizedPhase === "cross" ||
                      normalizedPhase === "redirect" || normalizedPhase === "recross")
                  ) && (
                    <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30">
                      <p className="text-sm text-amber-300">{aiTurnMessage}</p>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Objection Panel */}
            {(normalizedPhase === "direct" || normalizedPhase === "cross" ||
              normalizedPhase === "redirect" || normalizedPhase === "recross") && (
              <div className="bg-slate-800/50 backdrop-blur-sm border border-red-500/30 rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-4">
                  <AlertIcon className="w-5 h-5 text-red-400" />
                  <span className="font-medium text-white">Objections</span>
                  {sessionStatus.humanRole === "spectator" && (
                    <span className="text-xs text-slate-500 ml-auto">AI attorneys will object automatically</span>
                  )}
                </div>
                <ObjectionPanel
                  sessionId={sessionId}
                  currentPhase={normalizedPhase}
                  humanRole={sessionStatus.humanRole}
                  isObjectionPending={trialState.isObjectionPending}
                  onObjectionRaised={handleObjectionRaised}
                  onObjectionResult={handleObjectionResult}
                  compact={true}
                />
              </div>
            )}

            {/* Advance Phase Button - hidden during testimony phases (managed by exam flow) */}
            {(() => {
              const isTestimonyPhase = ["direct", "cross", "redirect", "recross"].includes(normalizedPhase);
              const showClosingButton = isTestimonyPhase && prosecutionRested && defenseRested && !currentWitnessId;
              const showNormalAdvance = !isTestimonyPhase && normalizedPhase !== "prep" && normalizedPhase !== "scoring" && getNextPhase();

              if (showClosingButton) {
                return (
                  <button
                    onClick={() => handleAdvancePhase("closing")}
                    disabled={isAdvancingPhase}
                    className="w-full py-2.5 px-4 bg-gradient-to-r from-amber-700 to-amber-600 hover:from-amber-600 hover:to-amber-500 disabled:from-slate-800 disabled:to-slate-800 text-white text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2"
                  >
                    {isAdvancingPhase ? "Advancing..." : "Proceed to Closing Arguments"}
                  </button>
                );
              }
              if (showNormalAdvance) {
                return (
                  <button
                    onClick={() => {
                      const next = getNextPhase();
                      if (next) handleAdvancePhase(next);
                    }}
                    disabled={isAdvancingPhase}
                    className="w-full py-2.5 px-4 bg-gradient-to-r from-slate-700 to-slate-600 hover:from-slate-600 hover:to-slate-500 disabled:from-slate-800 disabled:to-slate-800 text-white text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2"
                  >
                    {isAdvancingPhase ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Advancing...
                      </>
                    ) : (
                      <>
                        Next: {phaseConfig[getNextPhase() as TrialPhase]?.label || getNextPhase()}
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                        </svg>
                      </>
                    )}
                  </button>
                );
              }
              return null;
            })()}
          </div>
        </div>
      </main>

      {/* Phase progress bar — collapsible */}
      <footer className="fixed bottom-0 left-0 right-0 z-20 bg-slate-900/95 backdrop-blur-sm border-t border-slate-700/50">
        <div className="max-w-7xl mx-auto px-4">
          <button
            onClick={() => setPhaseBarCollapsed(!phaseBarCollapsed)}
            className="w-full flex items-center justify-between py-2 text-xs text-slate-400 hover:text-slate-300 transition-colors"
          >
            <span className="font-medium">
              Trial Phase: {phaseConfig[normalizedPhase]?.label || normalizedPhase}
            </span>
            <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${!phaseBarCollapsed ? "rotate-180" : ""}`} />
          </button>
          {!phaseBarCollapsed && (
            <div className="pb-3">
              <div className="flex items-center gap-1">
                {(Object.keys(phaseConfig) as TrialPhase[]).map((phase, index) => {
                  const isActive = phase === normalizedPhase;
                  const isPast = Object.keys(phaseConfig).indexOf(phase) < Object.keys(phaseConfig).indexOf(normalizedPhase);
                  const config = phaseConfig[phase];

                  return (
                    <React.Fragment key={phase}>
                      <div
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          isActive
                            ? `bg-gradient-to-r ${config.bgGradient} text-white shadow-lg`
                            : isPast
                            ? "bg-slate-700/50 text-slate-400"
                            : "bg-slate-800/30 text-slate-600"
                        }`}
                      >
                        <span>{config.icon}</span>
                        <span className="hidden sm:inline">{config.label}</span>
                      </div>
                      {index < Object.keys(phaseConfig).length - 1 && (
                        <div className={`flex-1 h-0.5 rounded ${isPast ? "bg-slate-600" : "bg-slate-800"}`} />
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </footer>

      {/* Case Materials Modal */}
      <CaseMaterialsModal
        isOpen={isMaterialsModalOpen}
        onClose={() => setIsMaterialsModalOpen(false)}
        sessionId={sessionId}
        initialTab={materialsModalTab}
      />

      {/* Persona Customizer Modal */}
      {isPersonaModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <PersonaCustomizer
            sessionId={sessionId}
            onClose={() => setIsPersonaModalOpen(false)}
            humanRole={sessionStatus?.humanRole}
            attorneySubRole={sessionStatus?.attorneySubRole}
          />
        </div>
      )}
    </div>
  );
}
