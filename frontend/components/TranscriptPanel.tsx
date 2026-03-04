/**
 * TranscriptPanel - Live Transcript Display Component
 * 
 * Per ARCHITECTURE.md:
 * - Frontend responsible for UI rendering
 * - All trial logic flows through backend
 * 
 * Displays live transcript with:
 * - Speaker labels
 * - Timestamps
 * - Read-only view
 */

"use client";

import React, { useEffect, useRef, useState } from "react";

// =============================================================================
// TYPES
// =============================================================================

export type Role =
  | "attorney_plaintiff"
  | "attorney_defense"
  | "witness"
  | "judge"
  | "coach"
  | "spectator";

export type TrialPhase =
  | "prep"
  | "opening"
  | "direct"
  | "cross"
  | "redirect"
  | "recross"
  | "closing"
  | "scoring";

export interface TranscriptEntry {
  id: string;
  timestamp: number;
  role: Role;
  speakerName: string;
  text: string;
  phase: TrialPhase;
  isHuman: boolean;
  isFinal: boolean;
}

export interface TranscriptPanelProps {
  /** Transcript entries to display */
  entries: TranscriptEntry[];
  /** Current trial phase */
  currentPhase?: TrialPhase;
  /** Auto-scroll to bottom on new entries */
  autoScroll?: boolean;
  /** Show phase separators */
  showPhaseSeparators?: boolean;
  /** Show timestamps */
  showTimestamps?: boolean;
  /** Highlight current speaker */
  highlightSpeaker?: Role | null;
  /** Custom class name */
  className?: string;
  /** Max height (CSS value) */
  maxHeight?: string;
}

// =============================================================================
// ROLE DISPLAY CONFIG
// =============================================================================

const roleConfig: Record<Role, { label: string; color: string; bgColor: string }> = {
  attorney_plaintiff: {
    label: "Plaintiff Attorney",
    color: "text-blue-700",
    bgColor: "bg-blue-50",
  },
  attorney_defense: {
    label: "Defense Attorney",
    color: "text-indigo-700",
    bgColor: "bg-indigo-50",
  },
  witness: {
    label: "Witness",
    color: "text-green-700",
    bgColor: "bg-green-50",
  },
  judge: {
    label: "Judge",
    color: "text-purple-700",
    bgColor: "bg-purple-50",
  },
  coach: {
    label: "Coach",
    color: "text-amber-700",
    bgColor: "bg-amber-50",
  },
  spectator: {
    label: "Spectator",
    color: "text-slate-700",
    bgColor: "bg-slate-50",
  },
};

const phaseLabels: Record<TrialPhase, string> = {
  prep: "Preparation",
  opening: "Opening Statements",
  direct: "Direct Examination",
  cross: "Cross Examination",
  redirect: "Redirect Examination",
  recross: "Recross Examination",
  closing: "Closing Arguments",
  scoring: "Scoring",
};

// =============================================================================
// COMPONENT
// =============================================================================

export function TranscriptPanel({
  entries,
  currentPhase,
  autoScroll = true,
  showPhaseSeparators = true,
  showTimestamps = true,
  highlightSpeaker = null,
  className = "",
  maxHeight = "500px",
}: TranscriptPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [userScrolled, setUserScrolled] = useState(false);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (autoScroll && !userScrolled && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries, autoScroll, userScrolled]);

  // Detect user scroll
  const handleScroll = () => {
    if (!scrollRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    
    setUserScrolled(!isAtBottom);
  };

  // Scroll to bottom button
  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      setUserScrolled(false);
    }
  };

  // Format timestamp
  const formatTimestamp = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, "0")}:${seconds
        .toString()
        .padStart(2, "0")}`;
    }
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  // Group entries by phase for separators
  const getPhaseForEntry = (index: number): TrialPhase | null => {
    if (index === 0) return entries[0]?.phase || null;
    
    const currentEntry = entries[index];
    const prevEntry = entries[index - 1];
    
    if (currentEntry.phase !== prevEntry.phase) {
      return currentEntry.phase;
    }
    return null;
  };

  // Render phase separator
  const PhaseSeparator = ({ phase }: { phase: TrialPhase }) => (
    <div className="flex items-center gap-3 py-3">
      <div className="flex-1 h-px bg-gray-300" />
      <span className="px-3 py-1 text-xs font-semibold text-gray-500 bg-gray-100 rounded-full uppercase tracking-wide">
        {phaseLabels[phase]}
      </span>
      <div className="flex-1 h-px bg-gray-300" />
    </div>
  );

  // Render single entry
  const TranscriptEntryRow = ({
    entry,
    isHighlighted,
  }: {
    entry: TranscriptEntry;
    isHighlighted: boolean;
  }) => {
    const isSystemMessage = entry.speakerName === "Court Clerk" || entry.speakerName === "SYSTEM";

    // System/clerk announcements get a distinct style
    if (isSystemMessage) {
      return (
        <div className="py-2 px-4 my-1 rounded-lg bg-amber-50 border border-amber-200 text-center">
          <div className="text-xs font-semibold text-amber-700 mb-0.5">Court Clerk</div>
          <div className="text-sm text-amber-900 italic leading-relaxed">{entry.text}</div>
        </div>
      );
    }

    // Get config with fallback for unknown roles
    const config = roleConfig[entry.role] || {
      label: entry.role,
      color: "text-gray-700",
      bgColor: "bg-gray-50",
    };

    return (
      <div
        className={`py-3 px-4 rounded-lg transition-colors ${
          isHighlighted ? "ring-2 ring-blue-400 bg-blue-50" : ""
        } ${!entry.isFinal ? "opacity-70" : ""}`}
      >
        {/* Header row: speaker + timestamp */}
        <div className="flex items-center gap-2 mb-1">
          {/* Speaker badge */}
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${config.color} ${config.bgColor}`}
          >
            {entry.speakerName}
            {entry.isHuman && (
              <span className="text-gray-500">(You)</span>
            )}
          </span>

          {/* Role label */}
          <span className="text-xs text-gray-400">
            {config.label}
          </span>

          {/* Timestamp */}
          {showTimestamps && (
            <span className="ml-auto text-xs text-gray-400 font-mono">
              {formatTimestamp(entry.timestamp)}
            </span>
          )}
        </div>

        {/* Text content */}
        <div className={`text-gray-800 leading-relaxed ${!entry.isFinal ? "italic" : ""}`}>
          {entry.text}
          {!entry.isFinal && (
            <span className="ml-1 inline-block w-2 h-4 bg-gray-400 animate-pulse" />
          )}
        </div>
      </div>
    );
  };

  return (
    <div className={`flex flex-col bg-white rounded-lg border shadow-sm ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50 rounded-t-lg">
        <div className="flex items-center gap-2">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-gray-500"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          <h3 className="font-medium text-gray-700">Transcript</h3>
          {currentPhase && (
            <span className="px-2 py-0.5 text-xs font-medium text-gray-500 bg-gray-200 rounded">
              {phaseLabels[currentPhase]}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-400">
          {entries.length} {entries.length === 1 ? "entry" : "entries"}
        </span>
      </div>

      {/* Transcript content */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-2"
        style={{ maxHeight }}
      >
        {entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="mb-3 opacity-50"
            >
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <p>No transcript entries yet</p>
            <p className="text-sm">Entries will appear as participants speak</p>
          </div>
        ) : (
          entries.map((entry, index) => (
            <React.Fragment key={entry.id}>
              {/* Phase separator */}
              {showPhaseSeparators && getPhaseForEntry(index) && (
                <PhaseSeparator phase={getPhaseForEntry(index)!} />
              )}
              
              {/* Entry */}
              <TranscriptEntryRow
                entry={entry}
                isHighlighted={highlightSpeaker === entry.role}
              />
            </React.Fragment>
          ))
        )}
      </div>

      {/* Scroll to bottom button */}
      {userScrolled && entries.length > 0 && (
        <div className="absolute bottom-4 right-4">
          <button
            onClick={scrollToBottom}
            className="flex items-center gap-1 px-3 py-2 bg-blue-500 text-white text-sm font-medium rounded-full shadow-lg hover:bg-blue-600 transition-colors"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
            New messages
          </button>
        </div>
      )}

      {/* Footer with legend */}
      <div className="px-4 py-2 border-t bg-gray-50 rounded-b-lg">
        <div className="flex flex-wrap gap-3 text-xs">
          {Object.entries(roleConfig).map(([role, config]) => (
            <div key={role} className="flex items-center gap-1">
              <span className={`w-2 h-2 rounded-full ${config.bgColor} border ${config.color.replace("text-", "border-")}`} />
              <span className="text-gray-500">{config.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default TranscriptPanel;
