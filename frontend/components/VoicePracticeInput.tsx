/**
 * VoicePracticeInput - Inline Voice Recording for Practice Sessions
 * 
 * Used in preparation phase for:
 * - Coach AI conversations (voice questions)
 * - Drill mode practice (speaking responses)
 * - Witness interview practice
 * 
 * Features:
 * - Toggle recording with browser's Web Speech API
 * - Real-time transcription display
 * - Speech pattern analysis feedback
 * 
 * Uses Web Speech API for simplicity in practice mode (no backend WebSocket needed)
 */

"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import { apiFetch, API_BASE } from "@/lib/api";

// =============================================================================
// TYPES
// =============================================================================

export interface SpeechAnalysis {
  transcript: string;
  duration_seconds: number;
  word_count: number;
  words_per_minute: number;
  filler_words: { word: string; count: number }[];
  filler_word_percentage: number;
  average_sentence_length: number;
  pauses: { count: number; total_seconds: number };
  clarity_score: number; // 0-100
  pacing_feedback: string;
  delivery_tips: string[];
  strengths: string[];
  areas_to_improve: string[];
}

export interface VoicePracticeInputProps {
  sessionId: string;
  mode?: "push-to-talk" | "toggle";
  placeholder?: string;
  onTranscription?: (text: string) => void;
  onAnalysis?: (analysis: SpeechAnalysis) => void;
  onComplete?: (transcript: string) => void; // Called when speech ends with final transcript
  showAnalysis?: boolean;
  autoSubmit?: boolean; // If true, auto-submits when user stops speaking
  silenceTimeout?: number; // ms to wait after silence before auto-completing (default: 1500)
  compact?: boolean;
  className?: string;
  disabled?: boolean;
  context?: string; // e.g., "opening_statement", "cross_examination", "coach_question"
}

// =============================================================================
// WEB SPEECH API HOOK
// =============================================================================

// Extend Window interface for SpeechRecognition
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionResultList {
  length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
  isFinal: boolean;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: Event & { error: string }) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition;
    webkitSpeechRecognition: new () => SpeechRecognition;
  }
}

interface RecorderState {
  isRecording: boolean;
  isListening: boolean; // True when actively hearing speech
  duration: number;
  transcript: string;
  interimTranscript: string;
  error: string | null;
}

interface SpeechRecognitionOptions {
  onTranscription?: (text: string) => void;
  onSpeechEnd?: (finalTranscript: string, durationMs: number) => void;
  silenceTimeout?: number; // ms to wait after speech stops before auto-completing
}

function useSpeechRecognition(options: SpeechRecognitionOptions = {}) {
  const { 
    onTranscription, 
    onSpeechEnd,
    silenceTimeout = 1500 // Auto-stop 1.5 seconds after silence
  } = options;
  
  const [state, setState] = useState<RecorderState>({
    isRecording: false,
    isListening: false,
    duration: 0,
    transcript: "",
    interimTranscript: "",
    error: null,
  });

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const durationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startTimeRef = useRef<number>(0);
  const finalTranscriptRef = useRef<string>("");
  const hasSpokenRef = useRef<boolean>(false);

  const isSupported =
    typeof window !== "undefined" &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  const cleanup = useCallback(() => {
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore errors on cleanup
      }
      recognitionRef.current = null;
    }
  }, []);

  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  const stopRecording = useCallback((triggerCallback = true) => {
    const finalDuration = Date.now() - startTimeRef.current;
    const finalText = finalTranscriptRef.current;
    
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore
      }
    }
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    
    setState((prev) => ({
      ...prev,
      isRecording: false,
      isListening: false,
      interimTranscript: "",
    }));
    
    // Trigger callback with final transcript if speech was detected
    if (triggerCallback && finalText.trim() && hasSpokenRef.current) {
      onSpeechEnd?.(finalText.trim(), finalDuration);
    }
    
    hasSpokenRef.current = false;
  }, [onSpeechEnd]);

  const resetSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
    }
    silenceTimerRef.current = setTimeout(() => {
      // Only auto-stop if user has actually spoken
      if (hasSpokenRef.current && finalTranscriptRef.current.trim()) {
        stopRecording(true);
      }
    }, silenceTimeout);
  }, [silenceTimeout, stopRecording]);

  const startRecording = useCallback(async () => {
    if (!isSupported) {
      setState((prev) => ({
        ...prev,
        error: "Speech recognition not supported. Try Chrome or Edge.",
      }));
      return;
    }

    cleanup();
    finalTranscriptRef.current = "";
    hasSpokenRef.current = false;

    try {
      const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognitionClass();
      recognitionRef.current = recognition;

      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        startTimeRef.current = Date.now();
        durationIntervalRef.current = setInterval(() => {
          setState((prev) => ({
            ...prev,
            duration: Date.now() - startTimeRef.current,
          }));
        }, 100);

        setState({
          isRecording: true,
          isListening: false,
          duration: 0,
          transcript: "",
          interimTranscript: "",
          error: null,
        });
      };

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let interim = "";
        hasSpokenRef.current = true;

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            const text = result[0].transcript;
            finalTranscriptRef.current += text + " ";
            onTranscription?.(text);
          } else {
            interim += result[0].transcript;
          }
        }

        setState((prev) => ({
          ...prev,
          isListening: true,
          transcript: finalTranscriptRef.current.trim(),
          interimTranscript: interim,
        }));
        
        // Reset silence timer on each result
        resetSilenceTimer();
      };

      recognition.onerror = (event) => {
        // "no-speech" is common and not really an error for auto-detection
        if (event.error === "no-speech") {
          // Just restart if no speech detected yet
          if (!hasSpokenRef.current) {
            try {
              recognition.stop();
              setTimeout(() => {
                if (recognitionRef.current === recognition) {
                  recognition.start();
                }
              }, 100);
            } catch {
              // Ignore
            }
            return;
          }
        }
        
        const errorMessages: Record<string, string> = {
          "audio-capture": "Microphone not available.",
          "not-allowed": "Microphone permission denied.",
          "network": "Network error occurred.",
        };
        const message = errorMessages[event.error];
        if (message) {
          setState((prev) => ({ ...prev, error: message, isRecording: false }));
          cleanup();
        }
      };

      recognition.onend = () => {
        // Auto-restart if still recording and haven't manually stopped
        setState((prev) => {
          if (prev.isRecording && !hasSpokenRef.current) {
            // Try to restart if no speech detected yet
            try {
              setTimeout(() => {
                if (recognitionRef.current) {
                  recognitionRef.current.start();
                }
              }, 100);
            } catch {
              // Ignore
            }
            return prev;
          }
          return { ...prev, isRecording: false, isListening: false };
        });
      };

      recognition.start();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start recording";
      setState((prev) => ({ ...prev, error: message }));
    }
  }, [isSupported, cleanup, onTranscription, resetSilenceTimer]);

  const clearTranscript = useCallback(() => {
    finalTranscriptRef.current = "";
    setState((prev) => ({ ...prev, transcript: "", interimTranscript: "" }));
  }, []);

  return {
    state,
    startRecording,
    stopRecording: () => stopRecording(true),
    clearTranscript,
    isSupported,
  };
}

// =============================================================================
// ICONS
// =============================================================================

const MicIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" y1="19" x2="12" y2="23" />
    <line x1="8" y1="23" x2="16" y2="23" />
  </svg>
);

const StopIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </svg>
);

const WaveformIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 12h2M6 8v8M10 4v16M14 6v12M18 8v8M22 12h-2" />
  </svg>
);

// =============================================================================
// COMPONENT
// =============================================================================

export function VoicePracticeInput({
  sessionId,
  mode = "toggle",
  placeholder = "Click the mic and start speaking...",
  onTranscription,
  onAnalysis,
  onComplete,
  showAnalysis = true,
  autoSubmit = true,
  silenceTimeout = 1500,
  compact = false,
  className = "",
  disabled = false,
  context = "general",
}: VoicePracticeInputProps) {
  void mode; // Mode kept for future push-to-talk implementation
  
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<SpeechAnalysis | null>(null);
  const [showFullAnalysis, setShowFullAnalysis] = useState(false);

  // Handle speech completion (auto-triggered when user stops speaking)
  const handleSpeechEnd = useCallback(async (finalTranscript: string, durationMs: number) => {
    // Call onComplete callback with transcript
    if (autoSubmit && finalTranscript.trim()) {
      onComplete?.(finalTranscript.trim());
    }
    
    // Run speech analysis
    if (showAnalysis && finalTranscript.trim()) {
      await analyzeSpeechAsync(finalTranscript, durationMs);
    }
  }, [autoSubmit, onComplete, showAnalysis]);

  const { state, startRecording, stopRecording, clearTranscript, isSupported } =
    useSpeechRecognition({
      onTranscription,
      onSpeechEnd: handleSpeechEnd,
      silenceTimeout,
    });

  const { isRecording, isListening, duration, transcript, interimTranscript, error } = state;
  
  // Combined display text (final + interim)
  const displayText = transcript + (interimTranscript ? (transcript ? " " : "") + interimTranscript : "");

  const handleToggle = useCallback(async () => {
    if (disabled || !isSupported) return;

    if (isRecording) {
      stopRecording();
    } else {
      clearTranscript();
      setAnalysis(null);
      await startRecording();
    }
  }, [disabled, isSupported, isRecording, stopRecording, startRecording, clearTranscript]);

  const analyzeSpeechAsync = async (text: string, durationMs: number) => {
    if (!text.trim()) return;

    setIsAnalyzing(true);
    try {
      const response = await apiFetch(`${API_BASE}/api/prep/${sessionId}/analyze-speech`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: text,
          duration_seconds: durationMs / 1000,
          context,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setAnalysis(data);
        onAnalysis?.(data);
      } else {
        console.error("Speech analysis failed:", response.status);
      }
    } catch (err) {
      console.error("Speech analysis failed:", err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const formatDuration = (ms: number): string => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  if (!isSupported) {
    return (
      <div className={`text-sm text-amber-400 bg-amber-500/10 px-3 py-2 rounded-lg ${className}`}>
        Speech recognition requires Chrome, Edge, or Safari. Please use a supported browser.
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Recording Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={handleToggle}
          disabled={disabled || isAnalyzing}
          className={`
            flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all
            ${isRecording
              ? isListening 
                ? "bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/30 animate-pulse"
                : "bg-amber-500 hover:bg-amber-600 text-white shadow-lg shadow-amber-500/30"
              : "bg-indigo-600 hover:bg-indigo-500 text-white"
            }
            ${disabled || isAnalyzing ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
          `}
        >
          {isRecording ? (
            <>
              <MicIcon className={`w-5 h-5 ${isListening ? "animate-bounce" : ""}`} />
              <span>{isListening ? "Listening..." : "Waiting..."}</span>
              <span className="text-sm opacity-80">{formatDuration(duration)}</span>
            </>
          ) : (
            <>
              <MicIcon className="w-5 h-5" />
              <span>Tap to Speak</span>
            </>
          )}
        </button>

        {isRecording && (
          <div className="flex items-center gap-2">
            {isListening ? (
              <span className="text-xs text-emerald-400 flex items-center gap-1.5">
                <span className="flex gap-0.5">
                  <span className="w-1 h-3 bg-emerald-400 rounded-full animate-pulse" style={{ animationDelay: "0ms" }} />
                  <span className="w-1 h-4 bg-emerald-400 rounded-full animate-pulse" style={{ animationDelay: "150ms" }} />
                  <span className="w-1 h-2 bg-emerald-400 rounded-full animate-pulse" style={{ animationDelay: "300ms" }} />
                  <span className="w-1 h-5 bg-emerald-400 rounded-full animate-pulse" style={{ animationDelay: "450ms" }} />
                  <span className="w-1 h-3 bg-emerald-400 rounded-full animate-pulse" style={{ animationDelay: "600ms" }} />
                </span>
                Hearing you...
              </span>
            ) : (
              <span className="text-xs text-amber-400">Start speaking...</span>
            )}
          </div>
        )}

        {isRecording && (
          <button
            onClick={() => stopRecording()}
            className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg transition-colors"
          >
            Cancel
          </button>
        )}

        {isAnalyzing && (
          <div className="flex items-center gap-2 text-indigo-400">
            <div className="w-4 h-4 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
            <span className="text-sm">Analyzing your speech...</span>
          </div>
        )}
      </div>

      {/* Live Transcript */}
      {(displayText || isRecording) && (
        <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50">
          <div className="flex items-center gap-2 mb-2">
            <WaveformIcon className="w-4 h-4 text-slate-400" />
            <span className="text-xs text-slate-400 uppercase tracking-wider">
              {isRecording ? "Live Transcript" : "Transcript"}
            </span>
            {isRecording && (
              <span className="text-xs text-emerald-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
                Listening...
              </span>
            )}
          </div>
          <p className={`text-sm ${displayText ? "text-slate-300" : "text-slate-500 italic"}`}>
            {transcript && <span>{transcript}</span>}
            {interimTranscript && (
              <span className="text-slate-400 italic">
                {transcript ? " " : ""}{interimTranscript}
              </span>
            )}
            {!displayText && placeholder}
            {isRecording && !displayText && <span className="animate-pulse ml-1">|</span>}
          </p>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="text-sm text-red-400 bg-red-500/10 px-3 py-2 rounded-lg">
          {error}
        </div>
      )}

      {/* Speech Analysis Results */}
      {showAnalysis && analysis && !compact && (
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 rounded-xl border border-slate-700/50 overflow-hidden">
          {/* Summary Header */}
          <div className="p-4 border-b border-slate-700/50">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-white flex items-center gap-2">
                <svg className="w-5 h-5 text-indigo-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Speech Analysis
              </h4>
              <button
                onClick={() => setShowFullAnalysis(!showFullAnalysis)}
                className="text-sm text-indigo-400 hover:text-indigo-300"
              >
                {showFullAnalysis ? "Show Less" : "Show More"}
              </button>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-4 gap-3 mt-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-white">{analysis.clarity_score}</div>
                <div className="text-xs text-slate-400">Clarity Score</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-white">{analysis.words_per_minute}</div>
                <div className="text-xs text-slate-400">WPM</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-white">{analysis.word_count}</div>
                <div className="text-xs text-slate-400">Words</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-white">{analysis.filler_word_percentage.toFixed(1)}%</div>
                <div className="text-xs text-slate-400">Fillers</div>
              </div>
            </div>
          </div>

          {/* Pacing Feedback */}
          <div className="p-4 border-b border-slate-700/50">
            <p className="text-sm text-slate-300">{analysis.pacing_feedback}</p>
          </div>

          {/* Detailed Analysis (expandable) */}
          {showFullAnalysis && (
            <div className="p-4 space-y-4">
              {/* Filler Words */}
              {analysis.filler_words.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-amber-400 mb-2">Filler Words Detected</h5>
                  <div className="flex flex-wrap gap-2">
                    {analysis.filler_words.map((fw, i) => (
                      <span key={i} className="px-2 py-1 bg-amber-500/20 text-amber-300 text-xs rounded-full">
                        &quot;{fw.word}&quot; × {fw.count}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Strengths */}
              {analysis.strengths.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-emerald-400 mb-2">Strengths</h5>
                  <ul className="space-y-1">
                    {analysis.strengths.map((s, i) => (
                      <li key={i} className="text-sm text-emerald-300/80 flex items-start gap-2">
                        <span className="text-emerald-400 mt-0.5">✓</span>
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Areas to Improve */}
              {analysis.areas_to_improve.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-orange-400 mb-2">Areas to Improve</h5>
                  <ul className="space-y-1">
                    {analysis.areas_to_improve.map((a, i) => (
                      <li key={i} className="text-sm text-orange-300/80 flex items-start gap-2">
                        <span className="text-orange-400 mt-0.5">→</span>
                        {a}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Tips */}
              {analysis.delivery_tips.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-indigo-400 mb-2">Tips</h5>
                  <ul className="space-y-1">
                    {analysis.delivery_tips.map((t, i) => (
                      <li key={i} className="text-sm text-indigo-300/80 flex items-start gap-2">
                        <span className="text-indigo-400 mt-0.5">💡</span>
                        {t}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Compact Analysis */}
      {showAnalysis && analysis && compact && (
        <div className="flex items-center gap-4 text-sm">
          <span className="text-slate-400">
            Score: <span className="text-white font-medium">{analysis.clarity_score}/100</span>
          </span>
          <span className="text-slate-400">
            WPM: <span className="text-white font-medium">{analysis.words_per_minute}</span>
          </span>
          {analysis.filler_words.length > 0 && (
            <span className="text-amber-400">
              {analysis.filler_word_percentage.toFixed(1)}% fillers
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export default VoicePracticeInput;
