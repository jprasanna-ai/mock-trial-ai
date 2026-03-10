/**
 * ObjectionPanel - Objection Buttons Component
 * 
 * Per SPEC.md:
 * - Objections only valid during testimony states (DIRECT, CROSS, REDIRECT, RECROSS)
 * 
 * Per ARCHITECTURE.md:
 * - Frontend must NEVER control trial logic
 * - All trial logic flows through LangGraph
 * 
 * Sends objection intent to backend for validation.
 */

"use client";

import React, { useState, useCallback } from "react";
import { apiFetch, API_BASE } from "@/lib/api";

// =============================================================================
// TYPES
// =============================================================================

export type TrialPhase =
  | "prep"
  | "opening"
  | "direct"
  | "cross"
  | "redirect"
  | "recross"
  | "closing"
  | "scoring";

export type Role =
  | "attorney_plaintiff"
  | "attorney_defense"
  | "witness"
  | "judge"
  | "coach"
  | "spectator";

export type ObjectionType =
  | "hearsay"
  | "leading"
  | "relevance"
  | "speculation"
  | "asked_and_answered"
  | "compound"
  | "argumentative"
  | "foundation"
  | "narrative"
  | "non_responsive";

export interface ObjectionPanelProps {
  sessionId: string;
  currentPhase: TrialPhase;
  humanRole: Role | null;
  isObjectionPending: boolean;
  apiBaseUrl?: string;
  onObjectionRaised?: (type: ObjectionType) => void;
  onObjectionResult?: (sustained: boolean, explanation: string) => void;
  onError?: (error: string) => void;
  className?: string;
  compact?: boolean;
}

// =============================================================================
// OBJECTION CONFIG
// =============================================================================

const TESTIMONY_PHASES: TrialPhase[] = ["direct", "cross", "redirect", "recross"];

interface ObjectionConfig {
  label: string;
  description: string;
  shortcut: string;
  icon: React.ReactNode;
  color: string;
}

const objectionConfig: Record<ObjectionType, ObjectionConfig> = {
  hearsay: {
    label: "Hearsay",
    description: "Out-of-court statement offered for truth",
    shortcut: "H",
    color: "from-red-500 to-rose-600",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        <line x1="9" y1="10" x2="15" y2="10" />
      </svg>
    ),
  },
  leading: {
    label: "Leading",
    description: "Question suggests the answer",
    shortcut: "L",
    color: "from-orange-500 to-amber-600",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <path d="M8 12l2 2 4-4" />
      </svg>
    ),
  },
  relevance: {
    label: "Relevance",
    description: "Not relevant to the case",
    shortcut: "R",
    color: "from-yellow-500 to-orange-500",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="8" />
        <path d="M21 21l-4.35-4.35" />
        <line x1="11" y1="8" x2="11" y2="14" />
      </svg>
    ),
  },
  speculation: {
    label: "Speculation",
    description: "Witness lacks personal knowledge",
    shortcut: "S",
    color: "from-purple-500 to-violet-600",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <circle cx="12" cy="17" r="0.5" fill="currentColor" />
      </svg>
    ),
  },
  asked_and_answered: {
    label: "Asked & Answered",
    description: "Question already answered",
    shortcut: "A",
    color: "from-blue-500 to-indigo-600",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M17 2.1l4 4-4 4" />
        <path d="M3 12.2v-2a4 4 0 0 1 4-4h12.8" />
        <path d="M7 21.9l-4-4 4-4" />
        <path d="M21 11.8v2a4 4 0 0 1-4 4H4.2" />
      </svg>
    ),
  },
  compound: {
    label: "Compound",
    description: "Multiple questions at once",
    shortcut: "C",
    color: "from-teal-500 to-cyan-600",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
      </svg>
    ),
  },
  argumentative: {
    label: "Argumentative",
    description: "Arguing with the witness",
    shortcut: "G",
    color: "from-pink-500 to-rose-600",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
        <line x1="4" y1="22" x2="4" y2="15" />
      </svg>
    ),
  },
  foundation: {
    label: "Foundation",
    description: "Lacks proper foundation",
    shortcut: "F",
    color: "from-emerald-500 to-green-600",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M2 20h20" />
        <path d="M5 20V8l7-5 7 5v12" />
        <path d="M10 20v-6h4v6" />
      </svg>
    ),
  },
  narrative: {
    label: "Narrative",
    description: "Witness giving a narrative response",
    shortcut: "N",
    color: "from-sky-500 to-blue-600",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="M16 13H8" />
        <path d="M16 17H8" />
        <path d="M10 9H8" />
      </svg>
    ),
  },
  non_responsive: {
    label: "Non-Responsive",
    description: "Answer doesn't address the question",
    shortcut: "X",
    color: "from-slate-500 to-slate-600",
    icon: (
      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
      </svg>
    ),
  },
};

const PRIMARY_OBJECTIONS: ObjectionType[] = [
  "hearsay",
  "leading",
  "relevance",
  "speculation",
  "foundation",
];

const SECONDARY_OBJECTIONS: ObjectionType[] = [
  "asked_and_answered",
  "compound",
  "argumentative",
  "narrative",
  "non_responsive",
];

// =============================================================================
// COMPONENT
// =============================================================================

export function ObjectionPanel({
  sessionId,
  currentPhase,
  humanRole,
  isObjectionPending,
  apiBaseUrl = "http://localhost:8000",
  onObjectionRaised,
  onObjectionResult,
  onError,
  className = "",
  compact = false,
}: ObjectionPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<{
    sustained: boolean;
    explanation: string;
  } | null>(null);
  const [hoveredObjection, setHoveredObjection] = useState<ObjectionType | null>(null);

  const isTestimonyPhase = TESTIMONY_PHASES.includes(currentPhase);
  const canObject = 
    isTestimonyPhase &&
    !isObjectionPending &&
    !isSubmitting &&
    (humanRole === "attorney_plaintiff" || humanRole === "attorney_defense");

  const raiseObjection = useCallback(
    async (type: ObjectionType) => {
      if (!canObject) return;

      setIsSubmitting(true);
      setLastResult(null);
      onObjectionRaised?.(type);

      try {
        const response = await apiFetch(
          `${apiBaseUrl}/api/trial/${sessionId}/objection`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              objection_type: type,
              role: humanRole,
            }),
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || "Failed to raise objection");
        }

        const result = await response.json();
        
        setLastResult({
          sustained: result.sustained,
          explanation: result.explanation,
        });
        
        onObjectionResult?.(result.sustained, result.explanation);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to raise objection";
        onError?.(errorMessage);
      } finally {
        setIsSubmitting(false);
      }
    },
    [canObject, sessionId, humanRole, apiBaseUrl, onObjectionRaised, onObjectionResult, onError]
  );

  React.useEffect(() => {
    if (!canObject) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      const allObjections = [...PRIMARY_OBJECTIONS, ...SECONDARY_OBJECTIONS];
      for (const type of allObjections) {
        const config = objectionConfig[type];
        if (config.shortcut && e.key.toUpperCase() === config.shortcut) {
          e.preventDefault();
          raiseObjection(type);
          return;
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [canObject, raiseObjection]);

  const getDisableReason = (): string | null => {
    if (!isTestimonyPhase) {
      return `Objections allowed during testimony phases only`;
    }
    if (humanRole !== "attorney_plaintiff" && humanRole !== "attorney_defense") {
      return "Only attorneys can raise objections";
    }
    if (isObjectionPending) {
      return "Waiting for ruling on current objection";
    }
    if (isSubmitting) {
      return "Submitting objection...";
    }
    return null;
  };

  const disableReason = getDisableReason();

  const ObjectionButton = ({ type }: { type: ObjectionType }) => {
    const config = objectionConfig[type];
    const isHovered = hoveredObjection === type;
    
    return (
      <button
        onClick={() => raiseObjection(type)}
        onMouseEnter={() => setHoveredObjection(type)}
        onMouseLeave={() => setHoveredObjection(null)}
        disabled={!canObject}
        className={`
          relative group flex flex-col items-center justify-center
          px-3 py-3 rounded-xl transition-all duration-200
          ${canObject
            ? `bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700/50 hover:border-red-500/50
               hover:shadow-lg hover:shadow-red-500/10 cursor-pointer`
            : "bg-slate-800/30 border border-slate-700/30 cursor-not-allowed opacity-40"
          }
        `}
        title={config.description}
      >
        {/* Gradient accent on hover */}
        {canObject && (
          <div className={`absolute inset-0 rounded-xl bg-gradient-to-br ${config.color} opacity-0 group-hover:opacity-10 transition-opacity`} />
        )}
        
        {/* Icon */}
        <div className={`mb-1.5 ${canObject ? "text-slate-400 group-hover:text-white" : "text-slate-600"} transition-colors`}>
          {config.icon}
        </div>
        
        {/* Label */}
        <span className={`font-medium text-xs ${canObject ? "text-slate-300 group-hover:text-white" : "text-slate-600"} transition-colors`}>
          {config.label}
        </span>
        
        {/* Shortcut */}
        <span className={`text-[10px] mt-1 px-1.5 py-0.5 rounded ${
          canObject 
            ? "bg-slate-700/50 text-slate-500 group-hover:bg-red-500/20 group-hover:text-red-400" 
            : "bg-slate-800/50 text-slate-700"
        } transition-colors`}>
          {config.shortcut}
        </span>

        {/* Tooltip on hover */}
        {isHovered && canObject && (
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-10 whitespace-nowrap">
            <p className="text-xs text-slate-300">{config.description}</p>
            <div className="absolute left-1/2 -translate-x-1/2 top-full w-2 h-2 bg-slate-900 border-r border-b border-slate-700 transform rotate-45 -mt-1" />
          </div>
        )}
      </button>
    );
  };

  return (
    <div className={`bg-slate-900/80 backdrop-blur-sm rounded-2xl border border-slate-700/50 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
            isTestimonyPhase ? "bg-red-500/20" : "bg-slate-800"
          }`}>
            <svg viewBox="0 0 24 24" className={`w-5 h-5 ${isTestimonyPhase ? "text-red-400" : "text-slate-500"}`} fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <circle cx="12" cy="17" r="0.5" fill="currentColor" />
            </svg>
          </div>
          <div>
            <h3 className="font-semibold text-white">Objections</h3>
            <p className="text-xs text-slate-500">
              {isTestimonyPhase ? "Available during testimony" : "Not available in current phase"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isTestimonyPhase && (
            <span className="px-2.5 py-1 text-xs font-medium text-emerald-400 bg-emerald-500/20 rounded-full flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Active
            </span>
          )}
          {!compact && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="px-3 py-1.5 text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
            >
              {isExpanded ? "Less" : "More"}
            </button>
          )}
        </div>
      </div>

      {/* Disable reason banner */}
      {disableReason && (
        <div className="px-4 py-2 bg-amber-500/10 border-b border-amber-500/20">
          <p className="text-xs text-amber-400 flex items-center gap-2">
            <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <circle cx="12" cy="16" r="0.5" fill="currentColor" />
            </svg>
            {disableReason}
          </p>
        </div>
      )}

      {/* Objection buttons */}
      <div className="p-4">
        {/* Primary objections */}
        <div className="grid grid-cols-5 gap-2">
          {PRIMARY_OBJECTIONS.map((type) => (
            <ObjectionButton key={type} type={type} />
          ))}
        </div>

        {/* Secondary objections (expanded) */}
        {(isExpanded || !compact) && (
          <div className="mt-3 pt-3 border-t border-slate-700/50">
            <div className="grid grid-cols-5 gap-2">
              {SECONDARY_OBJECTIONS.map((type) => (
                <ObjectionButton key={type} type={type} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Pending indicator */}
      {(isObjectionPending || isSubmitting) && (
        <div className="px-4 pb-4">
          <div className="flex items-center gap-4 p-4 bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/30 rounded-xl">
            <div className="relative">
              <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center">
                <svg viewBox="0 0 24 24" className="w-6 h-6 text-amber-400" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 10l-1 1-5-5 1-1 5 5z" />
                  <path d="M19 15l-5-5" />
                  <path d="M4 20l5-5" />
                  <circle cx="19" cy="5" r="3" />
                </svg>
              </div>
              <div className="absolute inset-0 rounded-xl border-2 border-amber-400/50 animate-ping" />
            </div>
            <div>
              <div className="font-semibold text-amber-300">
                Objection Raised!
              </div>
              <div className="text-sm text-amber-400/70">
                Awaiting the judge&apos;s ruling...
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Last result */}
      {lastResult && !isObjectionPending && !isSubmitting && (
        <div className="px-4 pb-4">
          <div
            className={`p-4 rounded-xl border ${
              lastResult.sustained
                ? "bg-gradient-to-r from-emerald-500/10 to-green-500/10 border-emerald-500/30"
                : "bg-gradient-to-r from-red-500/10 to-rose-500/10 border-red-500/30"
            }`}
          >
            <div className="flex items-center gap-3 mb-2">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                lastResult.sustained ? "bg-emerald-500/20" : "bg-red-500/20"
              }`}>
                {lastResult.sustained ? (
                  <svg viewBox="0 0 24 24" className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                )}
              </div>
              <div>
                <span className={`font-bold text-lg ${
                  lastResult.sustained ? "text-emerald-400" : "text-red-400"
                }`}>
                  {lastResult.sustained ? "SUSTAINED" : "OVERRULED"}
                </span>
              </div>
            </div>
            <p className={`text-sm ${
              lastResult.sustained ? "text-emerald-300/80" : "text-red-300/80"
            }`}>
              {lastResult.explanation}
            </p>
          </div>
        </div>
      )}

      {/* Keyboard shortcuts help */}
      {canObject && !compact && (
        <div className="px-4 pb-4 pt-1 border-t border-slate-700/50">
          <p className="text-xs text-slate-500 flex items-center gap-2 flex-wrap">
            <span className="text-slate-400 font-medium">Shortcuts:</span>
            {PRIMARY_OBJECTIONS.slice(0, 3).map((type) => (
              <span key={type} className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400 text-[10px]">
                  {objectionConfig[type].shortcut}
                </kbd>
                <span className="text-slate-600">{objectionConfig[type].label}</span>
              </span>
            ))}
            <span className="text-slate-600">...</span>
          </p>
        </div>
      )}
    </div>
  );
}

export default ObjectionPanel;
