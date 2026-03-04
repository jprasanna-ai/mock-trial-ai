/**
 * PreparationPanel - AI-Generated Trial Preparation Materials
 * 
 * Displays auto-generated preparation materials during the PREP phase:
 * - Case Brief
 * - Theory of the Case
 * - Witness Outlines
 * - Objection Playbook
 * - Cross-Exam Traps
 * - AMTA Rules
 * 
 * Also includes:
 * - Coach AI chat
 * - Drill mode for practice
 * - Editable notes
 */

"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { VoicePracticeInput, SpeechAnalysis } from "./VoicePracticeInput";
import { ChevronDownIcon } from "@/components/ui/icons";

// =============================================================================
// SPEECH RECOGNITION TYPE DECLARATIONS
// =============================================================================

interface WebSpeechRecognitionResult {
  readonly length: number;
  item(index: number): WebSpeechRecognitionAlternative;
  [index: number]: WebSpeechRecognitionAlternative;
  readonly isFinal: boolean;
}

interface WebSpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}

interface WebSpeechRecognitionResultList {
  readonly length: number;
  item(index: number): WebSpeechRecognitionResult;
  [index: number]: WebSpeechRecognitionResult;
}

interface WebSpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: WebSpeechRecognitionResultList;
}

interface WebSpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: ((this: WebSpeechRecognition, ev: Event) => void) | null;
  onresult: ((this: WebSpeechRecognition, ev: WebSpeechRecognitionEvent) => void) | null;
  onerror: ((this: WebSpeechRecognition, ev: Event & { error: string }) => void) | null;
  onend: ((this: WebSpeechRecognition, ev: Event) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

interface WebSpeechRecognitionConstructor {
  new (): WebSpeechRecognition;
}

// Helper to get SpeechRecognition constructor
function getSpeechRecognition(): WebSpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || null;
}

// =============================================================================
// TYPES
// =============================================================================

interface WitnessOutline {
  witness_id: string;
  witness_name: string;
  called_by: string;
  direct_exam_outline: string[];
  cross_exam_outline: string[];
  key_points: string[];
  potential_weaknesses: string[];
}

interface ObjectionPlaybook {
  common_objections: Array<{ type: string; example: string; response: string }>;
  when_to_object: string[];
  how_to_respond: string[];
}

interface CrossExamTrap {
  witness_name: string;
  trap_description: string;
  how_to_set: string;
  expected_response: string;
  follow_up: string;
}

interface PrepMaterials {
  case_brief: string;
  theory_plaintiff: string;
  theory_defense: string;
  opening_plaintiff: string;
  opening_defense: string;
  witness_outlines: WitnessOutline[];
  objection_playbook: ObjectionPlaybook | null;
  cross_exam_traps: CrossExamTrap[];
  amta_rules: string[];
  generation_status?: Record<string, string>;
}

interface OpeningStatementsResponse {
  opening_plaintiff: string | null;
  opening_defense: string | null;
  plaintiff_attorney_name: string | null;
  defense_attorney_name: string | null;
  status: { opening_plaintiff: string; opening_defense: string };
  ready: boolean;
  audio_plaintiff_ready?: boolean;
  audio_defense_ready?: boolean;
}

interface DrillResponse {
  scenario: string;
  prompts: string[];
  tips: string[];
  sample_responses: string[];
}

type PrepTab = "brief" | "theory" | "witnesses" | "objections" | "traps" | "openings" | "rules" | "coach" | "drill" | "practice" | "agents";

interface PreparationPanelProps {
  sessionId: string;
  humanRole: string | null;
  className?: string;
  style?: React.CSSProperties;
  onOpeningsReady?: (ready: boolean) => void;
  onPrepComplete?: (complete: boolean) => void;
}

// =============================================================================
// ICONS
// =============================================================================

const BookIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
);

const LightbulbIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 18h6" />
    <path d="M10 22h4" />
    <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14" />
  </svg>
);

const UsersIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const AlertIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <circle cx="12" cy="17" r="0.5" fill="currentColor" />
  </svg>
);

const TargetIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
  </svg>
);

const ScaleIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 3v18M5 8l7-5 7 5M5 8l-1 8h4M19 8l1 8h-4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const MessageIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const PlayIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

const SendIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const RefreshIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M23 4v6h-6" />
    <path d="M1 20v-6h6" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

const MicrophoneIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" y1="19" x2="12" y2="23" />
    <line x1="8" y1="23" x2="16" y2="23" />
  </svg>
);

const GavelIcon = ({ className = "" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14.5 2l6 6-1.4 1.4-6-6L14.5 2z" />
    <path d="M3 21l8-8" />
    <path d="M9.5 5.5L5 10l6 6 4.5-4.5" />
    <path d="M2 22h20" strokeLinecap="round" />
  </svg>
);

// =============================================================================
// API
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CaseWitness {
  id: string;
  name: string;
  called_by: string;
  role_description: string;
}

interface CaseExhibit {
  id: string;
  title: string;
  description: string;
  exhibit_type: string;
}

interface MaterialsResponse {
  materials: PrepMaterials;
  is_complete: boolean;
  case_witnesses?: CaseWitness[];
  case_exhibits?: CaseExhibit[];
}

async function fetchPrepMaterials(sessionId: string): Promise<MaterialsResponse> {
  const url = `${API_BASE}/api/prep/${sessionId}/materials`;
  const response = await fetch(url);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch materials: ${response.status}`);
  }
  return response.json();
}

async function triggerGeneration(sessionId: string, section?: string, force = false): Promise<void> {
  const params = new URLSearchParams();
  if (section) params.append("section", section);
  if (force) params.append("force", "true");
  
  // Generation can take 2-3 minutes for all materials
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout
  
  try {
    const response = await fetch(`${API_BASE}/api/prep/${sessionId}/generate?${params.toString()}`, {
      method: "POST",
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Generation failed: ${response.status}`);
    }
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Generation timed out. Please try again.');
    }
    throw err;
  }
}

async function updateMaterial(
  sessionId: string, 
  section: string, 
  content: string, 
  witnessId?: string
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/api/prep/${sessionId}/materials`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ 
      section, 
      content,
      witness_id: witnessId 
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Update failed: ${response.status}`);
  }
  return response.json();
}

async function sendCoachMessage(sessionId: string, message: string): Promise<{ response: string; suggestions: string[] }> {
  const response = await fetch(`${API_BASE}/api/prep/${sessionId}/coach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    throw new Error(`Coach chat failed: ${response.status}`);
  }
  return response.json();
}

async function fetchOpeningStatements(sessionId: string): Promise<OpeningStatementsResponse> {
  const response = await fetch(`${API_BASE}/api/prep/${sessionId}/opening-statements`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch opening statements: ${response.status}`);
  }
  return response.json();
}

async function regenerateOpenings(sessionId: string, side?: string, force = false): Promise<OpeningStatementsResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch(`${API_BASE}/api/prep/${sessionId}/generate-openings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ side: side || null, force }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Generation failed: ${response.status}`);
    }
    return response.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Opening statement generation timed out. Please try again.");
    }
    throw err;
  }
}

async function startDrill(sessionId: string, drillType: string, witnessId?: string): Promise<DrillResponse> {
  const response = await fetch(`${API_BASE}/api/prep/${sessionId}/drill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ drill_type: drillType, witness_id: witnessId }),
  });
  if (!response.ok) {
    throw new Error(`Drill failed: ${response.status}`);
  }
  return response.json();
}

// =============================================================================
// CHAT INPUT WITH VOICE COMPONENT
// =============================================================================

interface ChatInputWithVoiceProps {
  placeholder?: string;
  isLoading?: boolean;
  onSend: (message: string) => void;
}

function ChatInputWithVoice({ placeholder = "Type or tap mic to speak...", isLoading = false, onSend }: ChatInputWithVoiceProps) {
  const [inputValue, setInputValue] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [interimText, setInterimText] = useState("");
  const recognitionRef = useRef<WebSpeechRecognition | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // Check browser support
  const isSupported = typeof window !== "undefined" && getSpeechRecognition() !== null;

  const cleanup = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore
      }
      recognitionRef.current = null;
    }
  }, []);

  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  const handleSend = useCallback(() => {
    const message = inputValue.trim();
    if (message && !isLoading) {
      onSend(message);
      setInputValue("");
    }
  }, [inputValue, isLoading, onSend]);

  const startVoiceInput = useCallback(() => {
    if (!isSupported || isLoading) return;

    cleanup();
    setInputValue("");
    setInterimText("");

    try {
      const SpeechRecognitionClass = getSpeechRecognition();
      if (!SpeechRecognitionClass) return;
      const recognition = new SpeechRecognitionClass();
      recognitionRef.current = recognition;

      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      let finalText = "";
      let hasSpoken = false;

      const resetSilenceTimer = () => {
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
        }
        silenceTimerRef.current = setTimeout(() => {
          if (hasSpoken && finalText.trim()) {
            recognition.stop();
            // Auto-send after stopping
            setTimeout(() => {
              if (finalText.trim()) {
                onSend(finalText.trim());
                setInputValue("");
                setInterimText("");
              }
            }, 100);
          }
        }, 1500);
      };

      recognition.onstart = () => {
        setIsRecording(true);
        setIsListening(false);
      };

      recognition.onresult = (event: WebSpeechRecognitionEvent) => {
        hasSpoken = true;
        setIsListening(true);
        let interim = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            finalText += result[0].transcript + " ";
            setInputValue(finalText.trim());
          } else {
            interim += result[0].transcript;
          }
        }
        setInterimText(interim);
        resetSilenceTimer();
      };

      recognition.onerror = (event: Event & { error: string }) => {
        if (event.error === "no-speech") {
          // Restart if no speech detected yet
          if (!hasSpoken) {
            try {
              recognition.stop();
              setTimeout(() => recognition.start(), 100);
            } catch {
              // Ignore
            }
            return;
          }
        }
        setIsRecording(false);
        setIsListening(false);
        cleanup();
      };

      recognition.onend = () => {
        setIsRecording(false);
        setIsListening(false);
        setInterimText("");
      };

      recognition.start();
    } catch {
      setIsRecording(false);
    }
  }, [isSupported, isLoading, cleanup, onSend]);

  const stopVoiceInput = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore
      }
    }
    cleanup();
    setIsRecording(false);
    setIsListening(false);
    setInterimText("");
  }, [cleanup]);

  const displayValue = inputValue + (interimText ? (inputValue ? " " : "") + interimText : "");

  return (
    <div className="space-y-2">
      {/* Input Row */}
      <div className="flex gap-2">
        {/* Text Input */}
        <div className="flex-1 relative">
          <input
            type="text"
            value={displayValue}
            onChange={(e) => {
              if (!isRecording) {
                setInputValue(e.target.value);
              }
            }}
            onKeyDown={(e) => e.key === "Enter" && !isRecording && handleSend()}
            placeholder={isRecording ? (isListening ? "Listening..." : "Start speaking...") : placeholder}
            disabled={isRecording}
            className={`w-full px-4 py-3 pr-12 bg-slate-800 border rounded-xl text-white placeholder-slate-500 focus:outline-none transition-colors ${
              isRecording 
                ? isListening 
                  ? "border-emerald-500 bg-emerald-500/10" 
                  : "border-amber-500 bg-amber-500/10"
                : "border-slate-700 focus:border-indigo-500"
            }`}
          />
          {interimText && (
            <span className="absolute right-14 top-1/2 -translate-y-1/2 text-slate-500 text-xs">
              ...
            </span>
          )}
        </div>

        {/* Mic Button */}
        {isSupported && (
          <button
            onClick={isRecording ? stopVoiceInput : startVoiceInput}
            disabled={isLoading}
            className={`px-4 py-3 rounded-xl transition-all ${
              isRecording
                ? isListening
                  ? "bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/30 animate-pulse"
                  : "bg-amber-500 hover:bg-amber-600 text-white shadow-lg shadow-amber-500/30"
                : "bg-slate-700 hover:bg-slate-600 text-slate-300"
            } ${isLoading ? "opacity-50 cursor-not-allowed" : ""}`}
            title={isRecording ? "Stop recording" : "Tap to speak"}
          >
            {isRecording ? (
              <div className="flex items-center gap-1">
                <span className="flex gap-0.5">
                  <span className="w-0.5 h-3 bg-white rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
                  <span className="w-0.5 h-4 bg-white rounded-full animate-pulse" style={{ animationDelay: "100ms" }} />
                  <span className="w-0.5 h-2 bg-white rounded-full animate-pulse" style={{ animationDelay: "200ms" }} />
                  <span className="w-0.5 h-5 bg-white rounded-full animate-pulse" style={{ animationDelay: "300ms" }} />
                  <span className="w-0.5 h-3 bg-white rounded-full animate-pulse" style={{ animationDelay: "400ms" }} />
                </span>
              </div>
            ) : (
              <MicrophoneIcon className="w-5 h-5" />
            )}
          </button>
        )}

        {/* Send Button */}
        <button
          onClick={handleSend}
          disabled={!inputValue.trim() || isLoading || isRecording}
          className="px-4 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-xl transition-colors"
        >
          {isLoading ? (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <SendIcon className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Recording Status */}
      {isRecording && (
        <p className="text-xs text-center text-slate-400">
          {isListening ? "Listening... will auto-send when you pause" : "Start speaking..."}
        </p>
      )}
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function PreparationPanel({ sessionId, humanRole, className = "", style, onOpeningsReady, onPrepComplete }: PreparationPanelProps) {
  const [activeTab, setActiveTab] = useState<PrepTab>("brief");
  const [materials, setMaterials] = useState<PrepMaterials | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedWitness, setExpandedWitness] = useState<string | null>(null);
  const [expandedTrap, setExpandedTrap] = useState<number | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  
  // Coach chat state
  const [chatMessages, setChatMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  
  // Drill state
  const [activeDrill, setActiveDrill] = useState<DrillResponse | null>(null);
  const [selectedDrillType, setSelectedDrillType] = useState<string>("direct");
  const [selectedWitness, setSelectedWitness] = useState<string>("");
  const [isDrillLoading, setIsDrillLoading] = useState(false);
  
  // Edit state
  const [editingSection, setEditingSection] = useState<string | null>(null);
  const [editContent, setEditContent] = useState<string>("");
  const [editWitnessId, setEditWitnessId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  
  // Voice input state
  const [lastSpeechAnalysis, setLastSpeechAnalysis] = useState<SpeechAnalysis | null>(null);
  
  // Agent prep state
  const [agentPreps, setAgentPreps] = useState<Record<string, { role_type: string; prep_content: Record<string, unknown>; is_generated: boolean; agent_name?: string; side?: string }>>({});
  const [agentPrepLoading, setAgentPrepLoading] = useState(false);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [regeneratingAgent, setRegeneratingAgent] = useState<string | null>(null);

  // Practice mode state
  const [practiceType, setPracticeType] = useState<string>("opening");
  const [practiceWitness, setPracticeWitness] = useState<string>("");
  const [practiceHistory, setPracticeHistory] = useState<Array<{ type: string; transcript: string; analysis: SpeechAnalysis }>>([]);
  
  // Opening statements state
  const [openings, setOpenings] = useState<OpeningStatementsResponse | null>(null);
  const [isGeneratingOpenings, setIsGeneratingOpenings] = useState(false);
  const [openingsError, setOpeningsError] = useState<string | null>(null);

  const [caseWitnesses, setCaseWitnesses] = useState<CaseWitness[]>([]);
  const [caseExhibits, setCaseExhibits] = useState<CaseExhibit[]>([]);

  // Load materials on mount and start generation
  useEffect(() => {
    loadAndGenerate();
    
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [sessionId]);

  // Notify parent when openings readiness changes
  useEffect(() => {
    if (openings && onOpeningsReady) {
      onOpeningsReady(openings.ready);
    }
  }, [openings, onOpeningsReady]);

  // Notify parent when prep materials completion changes
  useEffect(() => {
    if (onPrepComplete) {
      onPrepComplete(isComplete);
    }
  }, [isComplete, onPrepComplete]);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const loadMaterials = async () => {
    try {
      const response = await fetchPrepMaterials(sessionId);
      setMaterials(response.materials);
      setIsComplete(response.is_complete);
      if (response.case_witnesses) setCaseWitnesses(response.case_witnesses);
      if (response.case_exhibits) setCaseExhibits(response.case_exhibits);
      return response;
    } catch (err) {
      console.error("Failed to load materials:", err);
      throw err;
    }
  };

  const loadOpenings = async () => {
    try {
      const data = await fetchOpeningStatements(sessionId);
      setOpenings(data);
      return data;
    } catch (err) {
      console.error("Failed to load opening statements:", err);
      return null;
    }
  };

  const ensureOpeningsGenerated = async () => {
    const openingsData = await loadOpenings();
    const textReady = openingsData?.ready;
    const audioReady = openingsData?.audio_plaintiff_ready && openingsData?.audio_defense_ready;

    if (textReady && audioReady) return;

    setIsGeneratingOpenings(true);
    try {
      if (!textReady) {
        const result = await regenerateOpenings(sessionId);
        setOpenings(result);
      } else if (!audioReady) {
        await fetch(`${API_BASE}/api/prep/${sessionId}/generate-opening-audio`, {
          method: "POST",
        });
        const refreshed = await loadOpenings();
        if (refreshed) setOpenings(refreshed);
      }
    } catch (err) {
      console.error("Failed to generate opening statements:", err);
      setOpeningsError(err instanceof Error ? err.message : "Failed to generate openings");
    } finally {
      setIsGeneratingOpenings(false);
    }
  };

  const loadAndGenerate = async (forceRegenerate = false) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await loadMaterials();
      setIsLoading(false);

      const hasMainContent = !!(
        response.materials.case_brief &&
        response.materials.theory_plaintiff &&
        response.materials.theory_defense &&
        response.materials.witness_outlines?.length > 0
      );
      if ((response.is_complete || hasMainContent) && !forceRegenerate) {
        setIsGenerating(false);
        await ensureOpeningsGenerated();
        return;
      }
      
      if (forceRegenerate || !hasMainContent) {
        setIsGenerating(true);
      }
      
      try {
        await triggerGeneration(sessionId, undefined, forceRegenerate);
        const updated = await loadMaterials();
        setMaterials(updated.materials);
        setIsComplete(updated.is_complete);
        setIsGenerating(false);
        await ensureOpeningsGenerated();
      } catch (genErr) {
        console.error("Generation error:", genErr);
        setIsGenerating(false);
        setError("Failed to generate materials. Click Regenerate to try again.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load materials");
      setIsLoading(false);
      setIsGenerating(false);
    }
  };

  const handleRegenerate = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    loadAndGenerate(true);
  };

  const handleRegenerateSection = async (section: string) => {
    setIsGenerating(true);
    setError(null);
    try {
      await triggerGeneration(sessionId, section, true);
      const updated = await loadMaterials();
      setMaterials(updated.materials);
      setIsComplete(updated.is_complete);
    } catch (err) {
      console.error(`Failed to regenerate ${section}:`, err);
      setError(`Failed to regenerate ${section}. Please try again.`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRegenerateOpening = async (side?: string) => {
    setIsGeneratingOpenings(true);
    setOpeningsError(null);
    try {
      const result = await regenerateOpenings(sessionId, side, true);
      setOpenings(result);
      // Also refresh materials to keep in sync
      await loadMaterials();
    } catch (err) {
      console.error("Failed to regenerate opening:", err);
      setOpeningsError(err instanceof Error ? err.message : "Failed to regenerate opening statement");
    } finally {
      setIsGeneratingOpenings(false);
    }
  };

  const handleSendCoachMessage = async (message: string) => {
    if (!message.trim() || isChatLoading) return;
    setChatMessages(prev => [...prev, { role: "user", content: message }]);
    setIsChatLoading(true);
    try {
      const response = await sendCoachMessage(sessionId, message);
      setChatMessages(prev => [...prev, { role: "assistant", content: response.response }]);
    } catch {
      setChatMessages(prev => [...prev, { role: "assistant", content: "Sorry, I couldn't process that. Please try again." }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const fetchAgentPreps = useCallback(async () => {
    setAgentPrepLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/prep/${sessionId}/agent-prep`);
      if (res.ok) {
        const data = await res.json();
        setAgentPreps(data.agents || {});
      }
    } catch (err) {
      console.error("Failed to fetch agent preps:", err);
    } finally {
      setAgentPrepLoading(false);
    }
  }, [sessionId]);

  const handleGenerateAgentPreps = useCallback(async () => {
    setAgentPrepLoading(true);
    try {
      await fetch(`${API_BASE}/api/prep/${sessionId}/generate-agent-prep`, { method: "POST" });
      await fetchAgentPreps();
    } catch (err) {
      console.error("Failed to generate agent preps:", err);
    } finally {
      setAgentPrepLoading(false);
    }
  }, [sessionId, fetchAgentPreps]);

  const handleRegenerateAgentPrep = useCallback(async (agentKey: string) => {
    setRegeneratingAgent(agentKey);
    try {
      await fetch(`${API_BASE}/api/prep/${sessionId}/regenerate-agent-prep/${agentKey}`, { method: "POST" });
      await fetchAgentPreps();
    } catch (err) {
      console.error(`Failed to regenerate agent prep for ${agentKey}:`, err);
    } finally {
      setRegeneratingAgent(null);
    }
  }, [sessionId, fetchAgentPreps]);

  useEffect(() => {
    if (activeTab === "agents") {
      fetchAgentPreps();
    }
  }, [activeTab, fetchAgentPreps]);

  const handleStartDrill = async () => {
    if (isDrillLoading) return;
    setIsDrillLoading(true);
    
    try {
      const drill = await startDrill(sessionId, selectedDrillType, selectedWitness || undefined);
      setActiveDrill(drill);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start drill");
    } finally {
      setIsDrillLoading(false);
    }
  };

  // Edit handlers
  const handleStartEdit = (section: string, content: string, witnessId?: string) => {
    setEditingSection(section);
    setEditContent(content);
    setEditWitnessId(witnessId || null);
    setSaveMessage(null);
  };

  const handleCancelEdit = () => {
    setEditingSection(null);
    setEditContent("");
    setEditWitnessId(null);
    setSaveMessage(null);
  };

  const handleSaveEdit = async () => {
    if (!editingSection || isSaving) return;
    
    setIsSaving(true);
    setSaveMessage(null);
    
    try {
      await updateMaterial(sessionId, editingSection, editContent, editWitnessId || undefined);
      
      // Refresh materials to get updated content
      await loadMaterials();
      
      setSaveMessage({ type: "success", text: "Changes saved successfully!" });
      
      // Clear edit state after a short delay
      setTimeout(() => {
        setEditingSection(null);
        setEditContent("");
        setEditWitnessId(null);
        setSaveMessage(null);
      }, 1500);
    } catch (err) {
      setSaveMessage({ 
        type: "error", 
        text: err instanceof Error ? err.message : "Failed to save changes" 
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Edit button component
  const EditButton = ({ section, content, witnessId, label = "Edit" }: { 
    section: string; 
    content: string; 
    witnessId?: string;
    label?: string;
  }) => (
    <button
      onClick={() => handleStartEdit(section, content, witnessId)}
      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-400 hover:text-blue-300 bg-blue-500/10 hover:bg-blue-500/20 rounded-lg transition-colors"
    >
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
      {label}
    </button>
  );

  const tabs: { id: PrepTab; label: string; icon: React.ReactNode }[] = [
    { id: "brief", label: "Case Brief", icon: <BookIcon className="w-4 h-4" /> },
    { id: "theory", label: "Theory", icon: <LightbulbIcon className="w-4 h-4" /> },
    { id: "witnesses", label: "Witnesses", icon: <UsersIcon className="w-4 h-4" /> },
    { id: "objections", label: "Objections", icon: <AlertIcon className="w-4 h-4" /> },
    { id: "traps", label: "Cross Traps", icon: <TargetIcon className="w-4 h-4" /> },
    { id: "openings", label: "Openings", icon: <GavelIcon className="w-4 h-4" /> },
    { id: "rules", label: "AMTA Rules", icon: <ScaleIcon className="w-4 h-4" /> },
    { id: "coach", label: "Coach", icon: <MessageIcon className="w-4 h-4" /> },
    { id: "drill", label: "Drill", icon: <PlayIcon className="w-4 h-4" /> },
    { id: "practice", label: "Voice Practice", icon: <MicrophoneIcon className="w-4 h-4" /> },
    { id: "agents", label: "Agent Prep", icon: <UsersIcon className="w-4 h-4" /> },
  ];

  const isPlaintiffSide = humanRole?.includes("plaintiff");

  return (
    <div className={`bg-slate-900/80 backdrop-blur-sm rounded-2xl border border-slate-700/50 overflow-hidden flex flex-col ${className}`} style={style}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <BookIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="font-bold text-white">Trial Preparation</h2>
            <p className="text-xs text-slate-400">AI-generated study materials</p>
          </div>
        </div>
        <button
          onClick={handleRegenerate}
          disabled={isLoading || isGenerating}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-50"
          title="Regenerate all materials"
        >
          <RefreshIcon className={`w-4 h-4 ${isGenerating ? "animate-spin" : ""}`} />
          {isGenerating ? "Generating..." : "Regenerate"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-700/50 px-2 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors border-b-2 -mb-px whitespace-nowrap ${
              activeTab === tab.id
                ? "text-indigo-400 border-indigo-400"
                : "text-slate-400 border-transparent hover:text-white"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Generation Status Banner */}
      {isGenerating && (
        <div className="mx-4 mt-2 p-4 bg-gradient-to-r from-indigo-900/40 to-purple-900/40 border border-indigo-500/30 rounded-xl flex items-center gap-4">
          <div className="relative">
            <div className="w-10 h-10 border-3 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-lg">✨</span>
            </div>
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-indigo-300">AI is preparing your study materials...</p>
            <p className="text-xs text-slate-400 mt-1">Generating case brief, theories, witness outlines, and more. This typically takes 30-60 seconds.</p>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading && activeTab !== "coach" && activeTab !== "drill" ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-4" />
            <p className="text-slate-400">Loading preparation materials...</p>
            <p className="text-xs text-slate-500 mt-2">This may take a minute</p>
          </div>
        ) : error && activeTab !== "coach" && activeTab !== "drill" ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mb-4">
              <AlertIcon className="w-8 h-8 text-red-400" />
            </div>
            <p className="text-red-400 mb-2">Failed to load materials</p>
            <p className="text-slate-500 text-sm mb-4 max-w-md">{error}</p>
            <button
              onClick={() => loadAndGenerate(true)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            {/* Case Brief */}
            {activeTab === "brief" && materials && (
              <div className="prose prose-invert prose-sm max-w-none">
                <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                      <BookIcon className="w-5 h-5 text-indigo-400" />
                      Case Brief
                      {!materials.case_brief && isGenerating && (
                        <span className="ml-2 px-2 py-0.5 text-xs bg-indigo-500/20 text-indigo-400 rounded-full flex items-center gap-1">
                          <div className="w-3 h-3 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                          Generating...
                        </span>
                      )}
                    </h3>
                    {materials.case_brief && editingSection !== "case_brief" && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleRegenerateSection("case_brief")}
                          disabled={isGenerating}
                          className="p-1.5 text-slate-400 hover:text-indigo-400 rounded-lg transition-colors disabled:opacity-50"
                          title="Regenerate case brief"
                        >
                          <RefreshIcon className={`w-4 h-4 ${isGenerating ? "animate-spin" : ""}`} />
                        </button>
                        <EditButton section="case_brief" content={materials.case_brief} />
                      </div>
                    )}
                  </div>
                  
                  {editingSection === "case_brief" ? (
                    <div className="space-y-3">
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="w-full h-96 bg-slate-900/50 border border-slate-600 rounded-lg p-4 text-slate-300 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        placeholder="Edit the case brief..."
                      />
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {saveMessage && (
                            <span className={`text-sm ${saveMessage.type === "success" ? "text-green-400" : "text-red-400"}`}>
                              {saveMessage.text}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={handleCancelEdit}
                            className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={handleSaveEdit}
                            disabled={isSaving}
                            className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-2"
                          >
                            {isSaving ? (
                              <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Saving...
                              </>
                            ) : (
                              <>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                </svg>
                                Save Changes
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : materials.case_brief ? (
                    <div className="text-slate-300 whitespace-pre-wrap leading-relaxed">
                      {materials.case_brief}
                    </div>
                  ) : (
                    <div className="text-slate-500 italic">
                      {isGenerating ? "AI is generating the case brief..." : "No case brief available. Click Regenerate to generate."}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Theory of the Case */}
            {activeTab === "theory" && materials && (
              <div className="space-y-4">
                {/* Your side's theory (highlighted) */}
                <div className={`rounded-xl p-6 border-2 ${
                  isPlaintiffSide 
                    ? "bg-blue-500/10 border-blue-500/30" 
                    : "bg-emerald-500/10 border-emerald-500/30"
                }`}>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-1 text-xs font-bold rounded ${
                        isPlaintiffSide ? "bg-blue-500/20 text-blue-400" : "bg-emerald-500/20 text-emerald-400"
                      }`}>
                        YOUR SIDE
                      </span>
                      <h3 className="font-semibold text-white">
                        {isPlaintiffSide ? "Plaintiff Theory" : "Defense Theory"}
                      </h3>
                      {!(isPlaintiffSide ? materials.theory_plaintiff : materials.theory_defense) && isGenerating && (
                        <span className="ml-2 px-2 py-0.5 text-xs bg-indigo-500/20 text-indigo-400 rounded-full flex items-center gap-1">
                          <div className="w-3 h-3 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                          Generating...
                        </span>
                      )}
                    </div>
                    {(isPlaintiffSide ? materials.theory_plaintiff : materials.theory_defense) && 
                     editingSection !== (isPlaintiffSide ? "theory_plaintiff" : "theory_defense") && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleRegenerateSection("theory")}
                          disabled={isGenerating}
                          className="p-1.5 text-slate-400 hover:text-indigo-400 rounded-lg transition-colors disabled:opacity-50"
                          title="Regenerate theory"
                        >
                          <RefreshIcon className={`w-4 h-4 ${isGenerating ? "animate-spin" : ""}`} />
                        </button>
                        <EditButton 
                          section={isPlaintiffSide ? "theory_plaintiff" : "theory_defense"} 
                          content={isPlaintiffSide ? materials.theory_plaintiff : materials.theory_defense} 
                        />
                      </div>
                    )}
                  </div>
                  
                  {editingSection === (isPlaintiffSide ? "theory_plaintiff" : "theory_defense") ? (
                    <div className="space-y-3">
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="w-full h-72 bg-slate-900/50 border border-slate-600 rounded-lg p-4 text-slate-300 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <div className="flex items-center justify-between">
                        {saveMessage && (
                          <span className={`text-sm ${saveMessage.type === "success" ? "text-green-400" : "text-red-400"}`}>
                            {saveMessage.text}
                          </span>
                        )}
                        <div className="flex items-center gap-2 ml-auto">
                          <button onClick={handleCancelEdit} className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
                            Cancel
                          </button>
                          <button
                            onClick={handleSaveEdit}
                            disabled={isSaving}
                            className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-2"
                          >
                            {isSaving ? "Saving..." : "Save Changes"}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (isPlaintiffSide ? materials.theory_plaintiff : materials.theory_defense) ? (
                    <div className={`whitespace-pre-wrap leading-relaxed ${
                      isPlaintiffSide ? "text-blue-200" : "text-emerald-200"
                    }`}>
                      {isPlaintiffSide ? materials.theory_plaintiff : materials.theory_defense}
                    </div>
                  ) : (
                    <div className="text-slate-500 italic">
                      {isGenerating ? "AI is generating your theory..." : "No theory available. Click Regenerate to generate."}
                    </div>
                  )}
                </div>

                {/* Opposing side's theory */}
                <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-1 text-xs font-medium bg-slate-700 text-slate-400 rounded">
                        OPPOSING
                      </span>
                      <h3 className="font-semibold text-slate-400">
                        {isPlaintiffSide ? "Defense Theory" : "Plaintiff Theory"}
                      </h3>
                      {!(isPlaintiffSide ? materials.theory_defense : materials.theory_plaintiff) && isGenerating && (
                        <span className="ml-2 px-2 py-0.5 text-xs bg-slate-700 text-slate-400 rounded-full flex items-center gap-1">
                          <div className="w-3 h-3 border-2 border-slate-600 border-t-slate-400 rounded-full animate-spin" />
                          Generating...
                        </span>
                      )}
                    </div>
                    {(isPlaintiffSide ? materials.theory_defense : materials.theory_plaintiff) && 
                     editingSection !== (isPlaintiffSide ? "theory_defense" : "theory_plaintiff") && (
                      <EditButton 
                        section={isPlaintiffSide ? "theory_defense" : "theory_plaintiff"} 
                        content={isPlaintiffSide ? materials.theory_defense : materials.theory_plaintiff} 
                      />
                    )}
                  </div>
                  
                  {editingSection === (isPlaintiffSide ? "theory_defense" : "theory_plaintiff") ? (
                    <div className="space-y-3">
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="w-full h-72 bg-slate-900/50 border border-slate-600 rounded-lg p-4 text-slate-300 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <div className="flex items-center justify-between">
                        {saveMessage && (
                          <span className={`text-sm ${saveMessage.type === "success" ? "text-green-400" : "text-red-400"}`}>
                            {saveMessage.text}
                          </span>
                        )}
                        <div className="flex items-center gap-2 ml-auto">
                          <button onClick={handleCancelEdit} className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
                            Cancel
                          </button>
                          <button
                            onClick={handleSaveEdit}
                            disabled={isSaving}
                            className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-2"
                          >
                            {isSaving ? "Saving..." : "Save Changes"}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (isPlaintiffSide ? materials.theory_defense : materials.theory_plaintiff) ? (
                    <div className="text-slate-400 whitespace-pre-wrap leading-relaxed">
                      {isPlaintiffSide ? materials.theory_defense : materials.theory_plaintiff}
                    </div>
                  ) : (
                    <div className="text-slate-500 italic">
                      {isGenerating ? "AI is generating opposing theory..." : "Not available"}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Witness Outlines */}
            {activeTab === "witnesses" && materials && (
              <div className="space-y-3">
                {materials.witness_outlines.length > 0 && (
                  <div className="flex items-center justify-end mb-2">
                    <button
                      onClick={() => handleRegenerateSection("witnesses")}
                      disabled={isGenerating}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 hover:text-indigo-400 hover:bg-slate-800/50 rounded-lg transition-colors disabled:opacity-50"
                      title="Regenerate all witness outlines"
                    >
                      <RefreshIcon className={`w-3.5 h-3.5 ${isGenerating ? "animate-spin" : ""}`} />
                      Regenerate All
                    </button>
                  </div>
                )}
                {(() => {
                  const outlineMap = new Map(
                    materials.witness_outlines.map((o) => [o.witness_id, o])
                  );
                  const witnessList = caseWitnesses.length > 0
                    ? caseWitnesses.map((cw) => ({
                        id: cw.id,
                        name: cw.name,
                        called_by: cw.called_by,
                        role_description: cw.role_description,
                        outline: outlineMap.get(cw.id) || null,
                      }))
                    : materials.witness_outlines.map((o) => ({
                        id: o.witness_id,
                        name: o.witness_name,
                        called_by: o.called_by,
                        role_description: "",
                        outline: o,
                      }));

                  if (witnessList.length === 0) {
                    return (
                      <div className="flex flex-col items-center justify-center py-12 text-center">
                        {isGenerating ? (
                          <>
                            <div className="w-10 h-10 border-3 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-4" />
                            <p className="text-slate-400">Generating witness outlines...</p>
                            <p className="text-xs text-slate-500 mt-1">This may take a moment</p>
                          </>
                        ) : (
                          <>
                            <UsersIcon className="w-10 h-10 text-slate-600 mb-4" />
                            <p className="text-slate-400">Witness outlines not yet generated</p>
                            <button
                              onClick={() => handleRegenerateSection("witnesses")}
                              className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors"
                            >
                              Generate Now
                            </button>
                          </>
                        )}
                      </div>
                    );
                  }

                  const prosWitnesses = witnessList.filter((w) => w.called_by !== "defense");
                  const defWitnesses = witnessList.filter((w) => w.called_by === "defense");

                  const renderWitnessGroup = (witnesses: typeof witnessList, label: string, textColor: string, dotColor: string) => (
                    witnesses.length > 0 ? (
                      <div className="mb-4">
                        <h4 className={`text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-2 ${textColor}`}>
                          <span className={`w-2 h-2 rounded-full ${dotColor}`} />
                          {label} ({witnesses.length})
                        </h4>
                        <div className="space-y-2">
                          {witnesses.map((w) => {
                            const outline = w.outline;
                            const isDef = w.called_by === "defense";
                            return (
                              <div
                                key={w.id}
                                className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden"
                              >
                                <button
                                  onClick={() => setExpandedWitness(expandedWitness === w.id ? null : w.id)}
                                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
                                >
                                  <div className="flex items-center gap-3">
                                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                                      !isDef ? "bg-blue-500/20" : "bg-emerald-500/20"
                                    }`}>
                                      <UsersIcon className={`w-5 h-5 ${!isDef ? "text-blue-400" : "text-emerald-400"}`} />
                                    </div>
                                    <div className="text-left">
                                      <h4 className="font-medium text-white">{w.name}</h4>
                                      <div className="flex items-center gap-1.5">
                                        <span className={`text-[10px] font-bold px-1 py-px rounded ${
                                          isDef ? "bg-red-500/20 text-red-400" : "bg-blue-500/20 text-blue-400"
                                        }`}>
                                          {isDef ? "DEF" : "PROS"}
                                        </span>
                                        <p className="text-xs text-slate-400">
                                          {isDef ? "Defense" : "Prosecution"} Witness
                                        </p>
                                        {!outline && (
                                          <span className="text-[10px] text-slate-500 italic ml-1">outline pending</span>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                  <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${
                                    expandedWitness === w.id ? "rotate-180" : ""
                                  }`} />
                                </button>

                                {expandedWitness === w.id && outline && (
                                  <div className="px-4 pb-4 space-y-4">
                                    <div className="bg-amber-500/10 rounded-lg p-4 border border-amber-500/20">
                                      <h5 className="text-sm font-semibold text-amber-400 mb-2">Key Points to Establish</h5>
                                      <ul className="space-y-1">
                                        {outline.key_points.map((point, i) => (
                                          <li key={i} className="text-sm text-amber-200/80 flex items-start gap-2">
                                            <span className="text-amber-400">•</span>
                                            {point}
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                    <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/20">
                                      <h5 className="text-sm font-semibold text-blue-400 mb-2">Direct Examination Outline</h5>
                                      <ol className="space-y-1">
                                        {outline.direct_exam_outline.map((q, i) => (
                                          <li key={i} className="text-sm text-blue-200/80 flex items-start gap-2">
                                            <span className="text-blue-400 font-medium">{i + 1}.</span>
                                            {q}
                                          </li>
                                        ))}
                                      </ol>
                                    </div>
                                    <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
                                      <h5 className="text-sm font-semibold text-red-400 mb-2">Cross-Examination Outline</h5>
                                      <ol className="space-y-1">
                                        {outline.cross_exam_outline.map((q, i) => (
                                          <li key={i} className="text-sm text-red-200/80 flex items-start gap-2">
                                            <span className="text-red-400 font-medium">{i + 1}.</span>
                                            {q}
                                          </li>
                                        ))}
                                      </ol>
                                    </div>
                                    <div className="bg-slate-700/30 rounded-lg p-4 border border-slate-600/30">
                                      <h5 className="text-sm font-semibold text-slate-400 mb-2">Potential Weaknesses</h5>
                                      <ul className="space-y-1">
                                        {outline.potential_weaknesses.map((pw, i) => (
                                          <li key={i} className="text-sm text-slate-400 flex items-start gap-2">
                                            <span className="text-red-400">⚠</span>
                                            {pw}
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  </div>
                                )}

                                {expandedWitness === w.id && !outline && (
                                  <div className="px-4 pb-4">
                                    <div className="bg-slate-700/30 rounded-lg p-4 border border-slate-600/30 text-center">
                                      <p className="text-sm text-slate-400 mb-1">
                                        {w.role_description || "No outline generated yet."}
                                      </p>
                                      <p className="text-xs text-slate-500">
                                        Click &ldquo;Regenerate All&rdquo; above to generate outlines for all witnesses.
                                      </p>
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : null
                  );

                  return (
                    <>
                      {renderWitnessGroup(prosWitnesses, "Prosecution Witnesses", "text-blue-400", "bg-blue-400")}
                      {renderWitnessGroup(defWitnesses, "Defense Witnesses", "text-emerald-400", "bg-emerald-400")}
                    </>
                  );
                })()}
              </div>
            )}

            {/* Objection Playbook */}
            {activeTab === "objections" && materials && (
              <div className="space-y-6">
                {materials.objection_playbook && (
                  <div className="flex items-center justify-end mb-2">
                    <button
                      onClick={() => handleRegenerateSection("objections")}
                      disabled={isGenerating}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 hover:text-indigo-400 hover:bg-slate-800/50 rounded-lg transition-colors disabled:opacity-50"
                      title="Regenerate objection playbook"
                    >
                      <RefreshIcon className={`w-3.5 h-3.5 ${isGenerating ? "animate-spin" : ""}`} />
                      Regenerate
                    </button>
                  </div>
                )}
                {!materials.objection_playbook ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    {isGenerating ? (
                      <>
                        <div className="w-10 h-10 border-3 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-4" />
                        <p className="text-slate-400">Generating objection playbook...</p>
                        <p className="text-xs text-slate-500 mt-1">This may take a moment</p>
                      </>
                    ) : (
                      <>
                        <AlertIcon className="w-10 h-10 text-slate-600 mb-4" />
                        <p className="text-slate-400">Objection playbook not yet generated</p>
                        <button 
                          onClick={() => handleRegenerateSection("objections")}
                          className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors"
                        >
                          Generate Now
                        </button>
                      </>
                    )}
                  </div>
                ) : (
                  <>
                    {/* Common Objections */}
                    <div>
                      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
                        Common Objections
                      </h3>
                      <div className="space-y-2">
                        {materials.objection_playbook.common_objections?.map((obj, i) => (
                          <div key={i} className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="px-2 py-1 text-xs font-bold bg-red-500/20 text-red-400 rounded">
                                {obj.type}
                              </span>
                            </div>
                            <p className="text-sm text-slate-400 mb-2">
                              <span className="text-slate-500">Example:</span> {obj.example}
                            </p>
                            <p className="text-sm text-emerald-400">
                              <span className="text-emerald-500">Response:</span> {obj.response}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* When to Object */}
                    {materials.objection_playbook.when_to_object?.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
                          When to Object
                        </h3>
                        <div className="bg-amber-500/10 rounded-xl p-4 border border-amber-500/20">
                          <ul className="space-y-2">
                            {materials.objection_playbook.when_to_object.map((tip, i) => (
                              <li key={i} className="text-sm text-amber-200/80 flex items-start gap-2">
                                <span className="text-amber-400 mt-0.5">→</span>
                                {tip}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}

                    {/* How to Respond */}
                    {materials.objection_playbook.how_to_respond?.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
                          How to Respond to Objections
                        </h3>
                        <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/20">
                          <ul className="space-y-2">
                            {materials.objection_playbook.how_to_respond.map((tip, i) => (
                              <li key={i} className="text-sm text-blue-200/80 flex items-start gap-2">
                                <span className="text-blue-400 mt-0.5">→</span>
                                {tip}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Cross-Exam Traps */}
            {activeTab === "traps" && materials && (
              <div className="space-y-3">
                {materials.cross_exam_traps.length > 0 && (
                  <div className="flex items-center justify-end mb-2">
                    <button
                      onClick={() => handleRegenerateSection("traps")}
                      disabled={isGenerating}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 hover:text-indigo-400 hover:bg-slate-800/50 rounded-lg transition-colors disabled:opacity-50"
                      title="Regenerate cross-exam traps"
                    >
                      <RefreshIcon className={`w-3.5 h-3.5 ${isGenerating ? "animate-spin" : ""}`} />
                      Regenerate
                    </button>
                  </div>
                )}
                {materials.cross_exam_traps.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    {isGenerating ? (
                      <>
                        <div className="w-10 h-10 border-3 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-4" />
                        <p className="text-slate-400">Generating cross-exam traps...</p>
                        <p className="text-xs text-slate-500 mt-1">This may take a moment</p>
                      </>
                    ) : (
                      <>
                        <TargetIcon className="w-10 h-10 text-slate-600 mb-4" />
                        <p className="text-slate-400">Cross-exam traps not yet generated</p>
                        <button 
                          onClick={() => handleRegenerateSection("traps")}
                          className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors"
                        >
                          Generate Now
                        </button>
                      </>
                    )}
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-slate-400 mb-4">
                      These are cross-examination techniques that opposing counsel might use. 
                      Be prepared to defend against them!
                    </p>
                    {materials.cross_exam_traps.map((trap, i) => (
                  <div
                    key={i}
                    className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden"
                  >
                    <button
                      onClick={() => setExpandedTrap(expandedTrap === i ? null : i)}
                      className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center">
                          <TargetIcon className="w-5 h-5 text-red-400" />
                        </div>
                        <div className="text-left">
                          <h4 className="font-medium text-white">{trap.witness_name}</h4>
                          <p className="text-xs text-red-400">{trap.trap_description}</p>
                        </div>
                      </div>
                      <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${
                        expandedTrap === i ? "rotate-180" : ""
                      }`} />
                    </button>

                    {expandedTrap === i && (
                      <div className="px-4 pb-4 space-y-3">
                        <div className="bg-slate-700/30 rounded-lg p-3">
                          <p className="text-xs text-slate-500 uppercase mb-1">How to Set the Trap</p>
                          <p className="text-sm text-slate-300">{trap.how_to_set}</p>
                        </div>
                        <div className="bg-slate-700/30 rounded-lg p-3">
                          <p className="text-xs text-slate-500 uppercase mb-1">Expected Response</p>
                          <p className="text-sm text-slate-300">{trap.expected_response}</p>
                        </div>
                        <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
                          <p className="text-xs text-red-400 uppercase mb-1">Follow-Up (Spring the Trap)</p>
                          <p className="text-sm text-red-200">{trap.follow_up}</p>
                        </div>
                      </div>
                    )}
                  </div>
                    ))}
                  </>
                )}
              </div>
            )}

            {/* Opening Statements */}
            {activeTab === "openings" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <GavelIcon className="w-5 h-5 text-amber-400" />
                    <h3 className="text-sm font-semibold text-white">Opening Statements</h3>
                    {openings?.ready && openings?.audio_plaintiff_ready && openings?.audio_defense_ready ? (
                      <span className="px-2 py-0.5 text-[10px] font-medium bg-emerald-500/20 text-emerald-400 rounded-full">
                        Ready
                      </span>
                    ) : openings?.ready && !(openings?.audio_plaintiff_ready && openings?.audio_defense_ready) ? (
                      <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-500/20 text-amber-400 rounded-full animate-pulse">
                        Generating audio...
                      </span>
                    ) : isGeneratingOpenings || isGenerating ? (
                      <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-500/20 text-amber-400 rounded-full animate-pulse">
                        Generating...
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-[10px] font-medium bg-slate-500/20 text-slate-400 rounded-full">
                        Not Ready
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => handleRegenerateOpening()}
                    disabled={isGeneratingOpenings}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 hover:text-indigo-400 hover:bg-slate-800/50 rounded-lg transition-colors disabled:opacity-50"
                    title="Regenerate both opening statements"
                  >
                    <RefreshIcon className={`w-3.5 h-3.5 ${isGeneratingOpenings ? "animate-spin" : ""}`} />
                    Regenerate All
                  </button>
                </div>

                {openingsError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400">
                    {openingsError}
                  </div>
                )}

                {/* Prosecution Opening */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-medium text-blue-400">Prosecution Opening</h4>
                      {openings?.plaintiff_attorney_name && (
                        <p className="text-xs text-slate-500 mt-0.5">{openings.plaintiff_attorney_name}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {openings?.status?.opening_plaintiff === "generating" && (
                        <span className="text-[10px] text-amber-400 animate-pulse">Generating...</span>
                      )}
                      {openings?.status?.opening_plaintiff === "complete" && (
                        <span className="text-[10px] text-emerald-400">Ready</span>
                      )}
                      {openings?.status?.opening_plaintiff?.startsWith("error") && (
                        <span className="text-[10px] text-red-400">Error</span>
                      )}
                      <button
                        onClick={() => handleRegenerateOpening("plaintiff")}
                        disabled={isGeneratingOpenings}
                        className="p-1 text-slate-400 hover:text-indigo-400 rounded transition-colors disabled:opacity-50"
                        title="Regenerate prosecution opening"
                      >
                        <RefreshIcon className={`w-3.5 h-3.5 ${isGeneratingOpenings ? "animate-spin" : ""}`} />
                      </button>
                    </div>
                  </div>
                  <div className="p-4">
                    {openings?.opening_plaintiff ? (
                      <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                        {openings.opening_plaintiff}
                      </div>
                    ) : isGeneratingOpenings || isGenerating ? (
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        <div className="w-4 h-4 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                        Generating prosecution opening statement...
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500 italic">
                        Not yet generated. Click Regenerate to create.
                      </p>
                    )}
                  </div>
                </div>

                {/* Defense Opening */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-medium text-red-400">Defense Opening</h4>
                      {openings?.defense_attorney_name && (
                        <p className="text-xs text-slate-500 mt-0.5">{openings.defense_attorney_name}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {openings?.status?.opening_defense === "generating" && (
                        <span className="text-[10px] text-amber-400 animate-pulse">Generating...</span>
                      )}
                      {openings?.status?.opening_defense === "complete" && (
                        <span className="text-[10px] text-emerald-400">Ready</span>
                      )}
                      {openings?.status?.opening_defense?.startsWith("error") && (
                        <span className="text-[10px] text-red-400">Error</span>
                      )}
                      <button
                        onClick={() => handleRegenerateOpening("defense")}
                        disabled={isGeneratingOpenings}
                        className="p-1 text-slate-400 hover:text-indigo-400 rounded transition-colors disabled:opacity-50"
                        title="Regenerate defense opening"
                      >
                        <RefreshIcon className={`w-3.5 h-3.5 ${isGeneratingOpenings ? "animate-spin" : ""}`} />
                      </button>
                    </div>
                  </div>
                  <div className="p-4">
                    {openings?.opening_defense ? (
                      <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                        {openings.opening_defense}
                      </div>
                    ) : isGeneratingOpenings || isGenerating ? (
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        <div className="w-4 h-4 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                        Generating defense opening statement...
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500 italic">
                        Not yet generated. Click Regenerate to create.
                      </p>
                    )}
                  </div>
                </div>

                {!openings?.ready && !isGeneratingOpenings && !isGenerating && (
                  <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-xs text-amber-400">
                    Opening statements must be generated before starting the trial. Click &quot;Regenerate All&quot; above to generate them.
                  </div>
                )}
              </div>
            )}

            {/* AMTA Rules */}
            {activeTab === "rules" && materials && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 mb-4">
                  <ScaleIcon className="w-5 h-5 text-indigo-400" />
                  <h3 className="font-semibold text-white">AMTA Competition Rules</h3>
                </div>
                {materials.amta_rules.map((rule, i) => (
                  <div
                    key={i}
                    className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 flex items-start gap-3"
                  >
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center flex-shrink-0">
                      <span className="text-sm font-bold text-indigo-400">{i + 1}</span>
                    </div>
                    <p className="text-sm text-slate-300">{rule}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Coach Chat */}
            {activeTab === "coach" && (
              <div className="flex flex-col h-full">
                <div className="flex-1 overflow-y-auto space-y-4 mb-4">
                  {chatMessages.length === 0 && (
                    <div className="text-center py-8">
                      <div className="w-16 h-16 rounded-full bg-indigo-500/20 flex items-center justify-center mx-auto mb-4">
                        <MessageIcon className="w-8 h-8 text-indigo-400" />
                      </div>
                      <h3 className="font-semibold text-white mb-2">AI Coach</h3>
                      <p className="text-sm text-slate-400 max-w-md mx-auto">
                        Ask me anything about trial strategy, objections, witness examination, 
                        or AMTA rules. I&apos;m here to help you prepare!
                      </p>
                      <div className="flex flex-wrap justify-center gap-2 mt-4">
                        {["How do I handle a hostile witness?", "What objections should I watch for?", "Quiz me on the case"].map((q) => (
                          <button
                            key={q}
                            onClick={() => handleSendCoachMessage(q)}
                            className="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {chatMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                          msg.role === "user"
                            ? "bg-indigo-600 text-white"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
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

                {/* Unified Chat Input with Mic */}
                <ChatInputWithVoice
                  placeholder="Ask the coach anything..."
                  isLoading={isChatLoading}
                  onSend={handleSendCoachMessage}
                />
              </div>
            )}

            {/* Drill Mode */}
            {activeTab === "drill" && (
              <div className="space-y-6">
                {!activeDrill ? (
                  <>
                    <div className="text-center mb-6">
                      <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
                        <PlayIcon className="w-8 h-8 text-emerald-400" />
                      </div>
                      <h3 className="font-semibold text-white mb-2">Practice Drills</h3>
                      <p className="text-sm text-slate-400">
                        Select a skill to practice with AI-generated scenarios
                      </p>
                    </div>

                    <div className="space-y-4">
                      {/* Drill Type */}
                      <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">
                          Drill Type
                        </label>
                        <select
                          value={selectedDrillType}
                          onChange={(e) => setSelectedDrillType(e.target.value)}
                          className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-indigo-500"
                        >
                          <option value="direct">Direct Examination</option>
                          <option value="cross">Cross-Examination</option>
                          <option value="opening">Opening Statement</option>
                          <option value="closing">Closing Argument</option>
                          <option value="objections">Objection Recognition</option>
                        </select>
                      </div>

                      {/* Witness Selection (for direct/cross) */}
                      {(selectedDrillType === "direct" || selectedDrillType === "cross") && materials && (
                        <div>
                          <label className="block text-sm font-medium text-slate-400 mb-2">
                            Select Witness
                          </label>
                          <select
                            value={selectedWitness}
                            onChange={(e) => setSelectedWitness(e.target.value)}
                            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-indigo-500"
                          >
                            <option value="">Select a witness...</option>
                            {materials.witness_outlines.map((w) => (
                              <option key={w.witness_id} value={w.witness_id}>
                                {w.witness_name} ({w.called_by})
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      <button
                        onClick={handleStartDrill}
                        disabled={isDrillLoading || ((selectedDrillType === "direct" || selectedDrillType === "cross") && !selectedWitness)}
                        className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-xl transition-colors flex items-center justify-center gap-2"
                      >
                        {isDrillLoading ? (
                          <>
                            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            Starting...
                          </>
                        ) : (
                          <>
                            <PlayIcon className="w-5 h-5" />
                            Start Drill
                          </>
                        )}
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold text-white">{activeDrill.scenario}</h3>
                      <button
                        onClick={() => setActiveDrill(null)}
                        className="text-sm text-slate-400 hover:text-white"
                      >
                        ← Back
                      </button>
                    </div>

                    {/* Prompts */}
                    <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-500/20">
                      <h4 className="text-sm font-semibold text-emerald-400 mb-3">Practice These</h4>
                      <ol className="space-y-2">
                        {activeDrill.prompts.map((prompt, i) => (
                          <li key={i} className="text-sm text-emerald-200/80 flex items-start gap-2">
                            <span className="text-emerald-400 font-medium">{i + 1}.</span>
                            {prompt}
                          </li>
                        ))}
                      </ol>
                    </div>

                    {/* Tips */}
                    <div className="bg-amber-500/10 rounded-xl p-4 border border-amber-500/20">
                      <h4 className="text-sm font-semibold text-amber-400 mb-3">Tips</h4>
                      <ul className="space-y-2">
                        {activeDrill.tips.map((tip, i) => (
                          <li key={i} className="text-sm text-amber-200/80 flex items-start gap-2">
                            <span className="text-amber-400">→</span>
                            {tip}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Sample Responses */}
                    <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                      <h4 className="text-sm font-semibold text-slate-400 mb-3">Sample Approaches</h4>
                      <ul className="space-y-2">
                        {activeDrill.sample_responses.map((sample, i) => (
                          <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                            <span className="text-slate-500">•</span>
                            {sample}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Voice Practice for Drill */}
                    <div className="bg-indigo-500/10 rounded-xl p-4 border border-indigo-500/20">
                      <h4 className="text-sm font-semibold text-indigo-400 mb-3 flex items-center gap-2">
                        <MicrophoneIcon className="w-4 h-4" />
                        Practice Your Response
                      </h4>
                      <p className="text-xs text-slate-400 mb-3">
                        Speak your response out loud and get instant feedback on your delivery.
                      </p>
                      <VoicePracticeInput
                        sessionId={sessionId}
                        placeholder="Click Speak and practice your response..."
                        context={selectedDrillType === "direct" ? "direct_examination" : 
                                selectedDrillType === "cross" ? "cross_examination" :
                                selectedDrillType === "opening" ? "opening_statement" :
                                selectedDrillType === "closing" ? "closing_argument" : "general"}
                        showAnalysis={true}
                        onAnalysis={(analysis) => {
                          setLastSpeechAnalysis(analysis);
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Voice Practice Mode */}
            {activeTab === "practice" && (
              <div className="space-y-6">
                <div className="text-center mb-6">
                  <div className="w-16 h-16 rounded-full bg-indigo-500/20 flex items-center justify-center mx-auto mb-4">
                    <MicrophoneIcon className="w-8 h-8 text-indigo-400" />
                  </div>
                  <h3 className="font-semibold text-white mb-2">Voice Practice</h3>
                  <p className="text-sm text-slate-400 max-w-md mx-auto">
                    Practice speaking and get AI feedback on your delivery, pacing, and filler words.
                    This helps you prepare for actual trial performance.
                  </p>
                </div>

                {/* Practice Type Selection */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">
                      What do you want to practice?
                    </label>
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
                      <option value="witness">Witness Testimony (Practice as Witness)</option>
                    </select>
                  </div>

                  {/* Witness Selection for relevant practice types */}
                  {(practiceType === "direct" || practiceType === "cross" || practiceType === "witness") && materials && (
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-2">
                        Select Witness
                      </label>
                      <select
                        value={practiceWitness}
                        onChange={(e) => setPracticeWitness(e.target.value)}
                        className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-indigo-500"
                      >
                        <option value="">Choose a witness...</option>
                        {materials.witness_outlines.map((w) => (
                          <option key={w.witness_id} value={w.witness_id}>
                            {w.witness_name} ({w.called_by})
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                {/* Practice Instructions */}
                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                  <h4 className="text-sm font-semibold text-slate-300 mb-3">Practice Tips</h4>
                  {practiceType === "opening" && (
                    <ul className="space-y-2 text-sm text-slate-400">
                      <li>• Introduce yourself and state who you represent</li>
                      <li>• Present your theory of the case clearly</li>
                      <li>• Preview the evidence you will present</li>
                      <li>• Speak at 130-150 WPM for clarity</li>
                      <li>• Make eye contact with the jury (look at camera)</li>
                    </ul>
                  )}
                  {practiceType === "closing" && (
                    <ul className="space-y-2 text-sm text-slate-400">
                      <li>• Summarize the key evidence presented</li>
                      <li>• Remind the jury of your theme</li>
                      <li>• Address weaknesses in your case</li>
                      <li>• End with a clear call to action</li>
                      <li>• Vary your pace for emphasis</li>
                    </ul>
                  )}
                  {practiceType === "direct" && (
                    <ul className="space-y-2 text-sm text-slate-400">
                      <li>• Use open-ended questions (who, what, when, where, why)</li>
                      <li>• Let the witness tell the story</li>
                      <li>• Avoid leading questions</li>
                      <li>• Establish foundation before key testimony</li>
                      <li>• Listen actively and follow up</li>
                    </ul>
                  )}
                  {practiceType === "cross" && (
                    <ul className="space-y-2 text-sm text-slate-400">
                      <li>• Use leading questions that suggest the answer</li>
                      <li>• One fact per question</li>
                      <li>• Control the witness - don&apos;t let them explain</li>
                      <li>• Know the answer before you ask</li>
                      <li>• Build to your strongest points</li>
                    </ul>
                  )}
                  {practiceType === "objection" && (
                    <ul className="space-y-2 text-sm text-slate-400">
                      <li>• Stand immediately when objecting</li>
                      <li>• State &quot;Objection&quot; clearly and firmly</li>
                      <li>• Give the specific ground (hearsay, leading, etc.)</li>
                      <li>• Be ready to explain if the judge asks</li>
                      <li>• Accept rulings gracefully</li>
                    </ul>
                  )}
                  {practiceType === "witness" && (
                    <ul className="space-y-2 text-sm text-slate-400">
                      <li>• Answer only the question asked</li>
                      <li>• Pause before answering to allow objections</li>
                      <li>• Speak clearly and at a measured pace</li>
                      <li>• Stay in character throughout</li>
                      <li>• Don&apos;t volunteer extra information</li>
                    </ul>
                  )}
                </div>

                {/* Voice Practice Input */}
                <div className="bg-gradient-to-br from-indigo-500/10 to-purple-500/10 rounded-xl p-5 border border-indigo-500/30">
                  <h4 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                    <MicrophoneIcon className="w-5 h-5 text-indigo-400" />
                    Practice Your Delivery
                  </h4>
                  <p className="text-xs text-slate-400 mb-4">
                    Tap the mic and speak. Recording will auto-stop when you pause, then analyze your delivery.
                  </p>
                  <VoicePracticeInput
                    sessionId={sessionId}
                    placeholder="Tap the mic and start speaking..."
                    context={practiceType === "opening" ? "opening_statement" :
                            practiceType === "closing" ? "closing_argument" :
                            practiceType === "direct" ? "direct_examination" :
                            practiceType === "cross" ? "cross_examination" :
                            practiceType === "objection" ? "objection" :
                            practiceType === "witness" ? "witness_interview" : "general"}
                    showAnalysis={true}
                    autoSubmit={false}
                    silenceTimeout={2000}
                    onAnalysis={(analysis) => {
                      setLastSpeechAnalysis(analysis);
                      setPracticeHistory(prev => [...prev, {
                        type: practiceType,
                        transcript: analysis.transcript,
                        analysis
                      }]);
                    }}
                  />
                </div>

                {/* Practice History */}
                {practiceHistory.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-slate-300">Practice History</h4>
                      <button
                        onClick={() => setPracticeHistory([])}
                        className="text-xs text-slate-500 hover:text-slate-300"
                      >
                        Clear History
                      </button>
                    </div>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {practiceHistory.slice().reverse().map((entry, i) => (
                        <div key={i} className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-indigo-400 capitalize">{entry.type.replace("_", " ")}</span>
                            <span className="text-xs text-slate-500">
                              Score: {entry.analysis.clarity_score}/100 | WPM: {entry.analysis.words_per_minute}
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 line-clamp-2">{entry.transcript}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === "agents" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <h3 className="font-semibold text-white">Per-Agent Preparation</h3>
                    <p className="text-xs text-slate-400 mt-0.5">Role-specific prep materials for each AI participant</p>
                  </div>
                  <button
                    onClick={handleGenerateAgentPreps}
                    disabled={agentPrepLoading}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors disabled:opacity-50"
                  >
                    <RefreshIcon className={`w-4 h-4 ${agentPrepLoading ? "animate-spin" : ""}`} />
                    {agentPrepLoading ? "Loading..." : Object.keys(agentPreps).length > 0 ? "Refresh" : "Generate All"}
                  </button>
                </div>

                {Object.keys(agentPreps).length === 0 && !agentPrepLoading && (
                  <div className="text-center py-10">
                    <UsersIcon className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                    <p className="text-slate-400 text-sm">No agent prep materials generated yet.</p>
                    <p className="text-slate-500 text-xs mt-1">Click &quot;Generate All&quot; to create role-specific prep for every AI agent.</p>
                  </div>
                )}

                {agentPrepLoading && Object.keys(agentPreps).length === 0 && (
                  <div className="flex items-center justify-center py-10">
                    <RefreshIcon className="w-6 h-6 text-indigo-400 animate-spin" />
                    <span className="ml-3 text-slate-400 text-sm">Generating agent prep materials...</span>
                  </div>
                )}

                {Object.entries(agentPreps).sort(([a], [b]) => a.localeCompare(b)).map(([agentKey, agentData]) => {
                  const isExpanded = expandedAgent === agentKey;
                  const isRegen = regeneratingAgent === agentKey;
                  const roleType = agentData.role_type;
                  const content = agentData.prep_content as Record<string, unknown>;

                  const agentName = agentData.agent_name;
                  const agentSide = agentData.side;
                  let displayName = agentName || agentKey.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
                  let roleColor = "text-slate-400";
                  let roleBg = "bg-slate-700/50";
                  let sideLabel = agentSide || "";
                  if (roleType === "attorney") {
                    const isPros = agentKey.startsWith("plaintiff");
                    roleColor = isPros ? "text-blue-400" : "text-red-400";
                    roleBg = isPros ? "bg-blue-500/10" : "bg-red-500/10";
                    sideLabel = sideLabel || (isPros ? "Prosecution" : "Defense");
                    const subRole = agentKey.includes("opening") ? "Opening" : agentKey.includes("closing") ? "Closing" : "Direct/Cross";
                    displayName = agentName
                      ? `${agentName}`
                      : `${sideLabel} Attorney (${subRole})`;
                  } else if (roleType === "witness") {
                    roleColor = "text-amber-400";
                    roleBg = "bg-amber-500/10";
                    if (!agentName) {
                      displayName = agentKey.replace("witness_", "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
                    }
                  } else if (roleType === "judge") {
                    roleColor = "text-purple-400";
                    roleBg = "bg-purple-500/10";
                  }

                  return (
                    <div key={agentKey} className="rounded-xl border border-slate-700/50 overflow-hidden">
                      <button
                        onClick={() => setExpandedAgent(isExpanded ? null : agentKey)}
                        className={`w-full flex items-center justify-between p-3 text-left transition-colors hover:bg-slate-800/50 ${roleBg}`}
                      >
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${roleBg} ${roleColor}`}>{roleType}</span>
                          {sideLabel && <span className={`text-[10px] font-bold ${roleColor}`}>({sideLabel})</span>}
                          <span className="text-sm font-medium text-white">{displayName}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => { e.stopPropagation(); handleRegenerateAgentPrep(agentKey); }}
                            disabled={isRegen}
                            className="text-xs text-slate-500 hover:text-indigo-400 transition-colors px-2 py-1 rounded"
                          >
                            {isRegen ? <RefreshIcon className="w-3 h-3 animate-spin" /> : "Regen"}
                          </button>
                          <ChevronDownIcon className={`w-5 h-5 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                        </div>
                      </button>

                      {isExpanded && (
                        <div className="p-4 space-y-3 bg-slate-800/30 border-t border-slate-700/50">
                          {Object.entries(content).map(([key, value]) => {
                            const label = key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
                            if (Array.isArray(value)) {
                              return (
                                <div key={key}>
                                  <h5 className="text-xs font-semibold text-slate-300 mb-1">{label}</h5>
                                  <ul className="space-y-1">
                                    {(value as unknown[]).slice(0, 10).map((item, i) => (
                                      <li key={i} className="text-xs text-slate-400 pl-3 border-l-2 border-slate-700">
                                        {typeof item === "string" ? item : typeof item === "object" && item !== null ? (
                                          <div className="space-y-0.5">
                                            {Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                                              <div key={k}><span className="text-slate-500">{k}:</span> {String(v)}</div>
                                            ))}
                                          </div>
                                        ) : String(item)}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              );
                            }
                            if (typeof value === "string" && value) {
                              return (
                                <div key={key}>
                                  <h5 className="text-xs font-semibold text-slate-300 mb-1">{label}</h5>
                                  <p className="text-xs text-slate-400 whitespace-pre-wrap">{value}</p>
                                </div>
                              );
                            }
                            if (typeof value === "object" && value !== null) {
                              return (
                                <div key={key}>
                                  <h5 className="text-xs font-semibold text-slate-300 mb-1">{label}</h5>
                                  <pre className="text-xs text-slate-400 bg-slate-900/50 rounded p-2 overflow-x-auto">{JSON.stringify(value, null, 2)}</pre>
                                </div>
                              );
                            }
                            return null;
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default PreparationPanel;
