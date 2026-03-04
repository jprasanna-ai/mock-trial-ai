/**
 * AudioPlayer - AI Agent Audio Playback Component
 * 
 * Per ARCHITECTURE.md Section 4:
 * AI: Text → GPT-4.1 → Persona Conditioning → TTS → WebRTC → Speaker
 * 
 * Per AUDIO.md:
 * - All audio must be streamed (no blocking)
 * - Judge voice priority for interruptions
 */

"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";

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

export interface Speaker {
  role: Role;
  name: string;
  isAI: boolean;
}

export interface AudioPlayerState {
  isPlaying: boolean;
  currentSpeaker: Speaker | null;
  isInterrupted: boolean;
  volume: number;
  isMuted: boolean;
}

export interface AudioPlayerProps {
  sessionId: string;
  wsUrl?: string;
  onPlaybackStart?: (speaker: Speaker) => void;
  onPlaybackEnd?: () => void;
  onInterrupt?: (interruptingSpeaker: Speaker) => void;
  onTextReceived?: (text: string, speaker: Speaker) => void;
  className?: string;
  showVolumeControls?: boolean;
  showAvatar?: boolean;
}

// =============================================================================
// ROLE DISPLAY CONFIG
// =============================================================================

const roleConfig: Record<Role, { 
  label: string; 
  gradient: string; 
  iconBg: string;
  textColor: string;
  borderColor: string;
  icon: React.ReactNode;
}> = {
  attorney_plaintiff: {
    label: "Plaintiff Attorney",
    gradient: "from-blue-500 to-blue-600",
    iconBg: "bg-blue-500/20",
    textColor: "text-blue-400",
    borderColor: "border-blue-500/30",
    icon: (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    ),
  },
  attorney_defense: {
    label: "Defense Attorney",
    gradient: "from-emerald-500 to-emerald-600",
    iconBg: "bg-emerald-500/20",
    textColor: "text-emerald-400",
    borderColor: "border-emerald-500/30",
    icon: (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    ),
  },
  witness: {
    label: "Witness",
    gradient: "from-amber-500 to-orange-500",
    iconBg: "bg-amber-500/20",
    textColor: "text-amber-400",
    borderColor: "border-amber-500/30",
    icon: (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
  judge: {
    label: "Judge",
    gradient: "from-purple-500 to-purple-600",
    iconBg: "bg-purple-500/20",
    textColor: "text-purple-400",
    borderColor: "border-purple-500/30",
    icon: (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 10l-1 1-5-5 1-1 5 5z" />
        <path d="M19 15l-5-5" />
        <path d="M4 20l5-5" />
        <circle cx="19" cy="5" r="3" />
      </svg>
    ),
  },
  coach: {
    label: "Coach",
    gradient: "from-cyan-500 to-cyan-600",
    iconBg: "bg-cyan-500/20",
    textColor: "text-cyan-400",
    borderColor: "border-cyan-500/30",
    icon: (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    ),
  },
  spectator: {
    label: "Spectator",
    gradient: "from-amber-500 to-amber-600",
    iconBg: "bg-amber-500/20",
    textColor: "text-amber-400",
    borderColor: "border-amber-500/30",
    icon: (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
};

// =============================================================================
// COMPONENT
// =============================================================================

export function AudioPlayer({
  sessionId,
  wsUrl,
  onPlaybackStart,
  onPlaybackEnd,
  onInterrupt,
  onTextReceived,
  className = "",
  showVolumeControls = true,
  showAvatar = true,
}: AudioPlayerProps) {
  const [state, setState] = useState<AudioPlayerState>({
    isPlaying: false,
    currentSpeaker: null,
    isInterrupted: false,
    volume: 1.0,
    isMuted: false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<AudioBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null);

  const effectiveWsUrl = wsUrl || `ws://localhost:8000/api/audio/${sessionId}/speaker`;

  const initAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
      gainNodeRef.current = audioContextRef.current.createGain();
      gainNodeRef.current.connect(audioContextRef.current.destination);
    }
    return audioContextRef.current;
  }, []);

  const playNextInQueue = useCallback(() => {
    if (audioQueueRef.current.length === 0 || !audioContextRef.current || !gainNodeRef.current) {
      isPlayingRef.current = false;
      setState((prev) => ({ ...prev, isPlaying: false }));
      onPlaybackEnd?.();
      return;
    }

    isPlayingRef.current = true;
    const buffer = audioQueueRef.current.shift()!;
    
    const source = audioContextRef.current.createBufferSource();
    source.buffer = buffer;
    source.connect(gainNodeRef.current);
    currentSourceRef.current = source;

    source.onended = () => {
      currentSourceRef.current = null;
      playNextInQueue();
    };

    source.start();
  }, [onPlaybackEnd]);

  const handleAudioData = useCallback(
    async (data: ArrayBuffer) => {
      const audioContext = initAudioContext();
      
      try {
        const audioBuffer = await audioContext.decodeAudioData(data.slice(0));
        audioQueueRef.current.push(audioBuffer);

        if (!isPlayingRef.current) {
          setState((prev) => ({ ...prev, isPlaying: true }));
          playNextInQueue();
        }
      } catch (err) {
        console.error("Failed to decode audio data:", err);
      }
    },
    [initAudioContext, playNextInQueue]
  );

  const handleMessage = useCallback(
    async (event: MessageEvent) => {
      if (event.data instanceof Blob) {
        const arrayBuffer = await event.data.arrayBuffer();
        handleAudioData(arrayBuffer);
        return;
      }

      if (event.data instanceof ArrayBuffer) {
        handleAudioData(event.data);
        return;
      }

      try {
        const message = JSON.parse(event.data);

        switch (message.type) {
          case "speaker_start": {
            const speaker: Speaker = {
              role: message.role,
              name: message.name,
              isAI: true,
            };
            setState((prev) => ({
              ...prev,
              currentSpeaker: speaker,
              isInterrupted: false,
            }));
            onPlaybackStart?.(speaker);
            break;
          }

          case "speaker_end": {
            setState((prev) => ({
              ...prev,
              currentSpeaker: null,
            }));
            break;
          }

          case "interrupt": {
            const interruptingSpeaker: Speaker = {
              role: message.role || "judge",
              name: message.name || "Judge",
              isAI: true,
            };

            if (currentSourceRef.current) {
              currentSourceRef.current.stop();
              currentSourceRef.current = null;
            }
            audioQueueRef.current = [];
            isPlayingRef.current = false;

            setState((prev) => ({
              ...prev,
              isPlaying: false,
              isInterrupted: true,
              currentSpeaker: interruptingSpeaker,
            }));

            onInterrupt?.(interruptingSpeaker);
            break;
          }

          case "text": {
            if (state.currentSpeaker) {
              onTextReceived?.(message.text, state.currentSpeaker);
            }
            break;
          }

          case "error": {
            console.error("Audio player error:", message.message);
            break;
          }
        }
      } catch {
        // Non-JSON message, ignore
      }
    },
    [handleAudioData, onPlaybackStart, onInterrupt, onTextReceived, state.currentSpeaker]
  );

  useEffect(() => {
    const ws = new WebSocket(effectiveWsUrl);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onmessage = handleMessage;

    ws.onerror = (error) => {
      console.error("AudioPlayer WebSocket error:", error);
    };

    ws.onclose = () => {
      setState((prev) => ({
        ...prev,
        isPlaying: false,
        currentSpeaker: null,
      }));
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
      if (currentSourceRef.current) {
        currentSourceRef.current.stop();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [effectiveWsUrl, handleMessage]);

  useEffect(() => {
    if (gainNodeRef.current) {
      gainNodeRef.current.gain.value = state.isMuted ? 0 : state.volume;
    }
  }, [state.volume, state.isMuted]);

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const volume = parseFloat(e.target.value);
    setState((prev) => ({ ...prev, volume }));
  };

  const toggleMute = () => {
    setState((prev) => ({ ...prev, isMuted: !prev.isMuted }));
  };

  const stopPlayback = useCallback(() => {
    if (currentSourceRef.current) {
      currentSourceRef.current.stop();
      currentSourceRef.current = null;
    }
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    setState((prev) => ({
      ...prev,
      isPlaying: false,
    }));
  }, []);

  const { isPlaying, currentSpeaker, isInterrupted, volume, isMuted } = state;
  const config = currentSpeaker ? roleConfig[currentSpeaker.role] : null;

  // Sound wave animation component
  const SoundWave = () => (
    <div className="flex items-center justify-center gap-[3px] h-8">
      {[...Array(5)].map((_, i) => (
        <div
          key={i}
          className={`w-1 rounded-full ${config?.textColor || "bg-amber-400"} ${
            isPlaying ? "animate-sound-wave" : ""
          }`}
          style={{
            height: isPlaying ? "100%" : "4px",
            backgroundColor: "currentColor",
            animationDelay: `${i * 0.1}s`,
          }}
        />
      ))}
      <style jsx>{`
        @keyframes sound-wave {
          0%, 100% { height: 4px; }
          50% { height: 100%; }
        }
        .animate-sound-wave {
          animation: sound-wave 0.5s ease-in-out infinite;
        }
      `}</style>
    </div>
  );

  return (
    <div
      className={`bg-slate-900/80 backdrop-blur-sm rounded-2xl border overflow-hidden transition-all duration-300 ${
        isPlaying 
          ? `${config?.borderColor || "border-amber-500/50"} shadow-lg shadow-amber-500/10` 
          : "border-slate-700/50"
      } ${className}`}
    >
      {/* Header with gradient accent */}
      <div className={`h-1 ${isPlaying && config ? `bg-gradient-to-r ${config.gradient}` : "bg-slate-700"}`} />
      
      {/* Main content */}
      <div className="p-4">
        <div className="flex items-center gap-4">
          {/* Avatar */}
          {showAvatar && (
            <div className={`relative w-14 h-14 rounded-xl flex items-center justify-center transition-all duration-300 ${
              currentSpeaker && config
                ? `${config.iconBg} ${config.textColor}`
                : "bg-slate-800 text-slate-500"
            }`}>
              {currentSpeaker && config ? (
                <>
                  {config.icon}
                  {isPlaying && (
                    <div className={`absolute inset-0 rounded-xl animate-pulse ${config.iconBg}`} />
                  )}
                </>
              ) : (
                <svg viewBox="0 0 24 24" className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                </svg>
              )}
            </div>
          )}

          {/* Speaker info */}
          <div className="flex-1 min-w-0">
            {currentSpeaker ? (
              <>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-white truncate">
                    {currentSpeaker.name}
                  </h3>
                  {isPlaying && (
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${config?.iconBg} ${config?.textColor}`}>
                      LIVE
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`text-sm ${config?.textColor || "text-slate-400"}`}>
                    {config?.label}
                  </span>
                  {isInterrupted && (
                    <span className="text-xs px-2 py-0.5 bg-red-500/20 text-red-400 rounded-full font-medium">
                      Interrupting
                    </span>
                  )}
                </div>
              </>
            ) : (
              <div>
                <h3 className="font-medium text-slate-400">AI Speaker</h3>
                <p className="text-sm text-slate-500">Waiting for audio...</p>
              </div>
            )}
          </div>

          {/* Sound wave indicator */}
          <div className={`w-12 ${config?.textColor || "text-slate-500"}`}>
            <SoundWave />
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4 mt-4 pt-4 border-t border-slate-700/50">
          {/* Play/Stop button */}
          <button
            onClick={isPlaying ? stopPlayback : undefined}
            disabled={!isPlaying}
            className={`flex items-center justify-center w-10 h-10 rounded-xl transition-all ${
              isPlaying
                ? "bg-red-500/20 text-red-400 hover:bg-red-500/30 cursor-pointer"
                : "bg-slate-800 text-slate-500 cursor-not-allowed"
            }`}
            aria-label={isPlaying ? "Stop playback" : "No audio playing"}
          >
            {isPlaying ? (
              <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            )}
          </button>

          {/* Status text */}
          <div className="flex-1">
            <p className={`text-sm ${isPlaying ? "text-slate-300" : "text-slate-500"}`}>
              {isPlaying ? "AI is speaking..." : "Waiting for AI response"}
            </p>
          </div>

          {/* Volume controls */}
          {showVolumeControls && (
            <div className="flex items-center gap-3">
              <button
                onClick={toggleMute}
                className={`p-2 rounded-lg transition-colors ${
                  isMuted
                    ? "bg-red-500/20 text-red-400"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                }`}
                aria-label={isMuted ? "Unmute" : "Mute"}
              >
                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2">
                  {isMuted ? (
                    <>
                      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                      <line x1="23" y1="9" x2="17" y2="15" />
                      <line x1="17" y1="9" x2="23" y2="15" />
                    </>
                  ) : (
                    <>
                      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                    </>
                  )}
                </svg>
              </button>
              
              <div className="relative w-24 h-2">
                <div className="absolute inset-0 bg-slate-700 rounded-full" />
                <div 
                  className="absolute left-0 top-0 h-full bg-gradient-to-r from-amber-500 to-orange-500 rounded-full"
                  style={{ width: `${volume * 100}%` }}
                />
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={volume}
                  onChange={handleVolumeChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  aria-label="Volume"
                />
              </div>
              <span className="text-xs text-slate-500 w-8">
                {Math.round(volume * 100)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Judge interrupt banner */}
      {isInterrupted && currentSpeaker?.role === "judge" && (
        <div className="px-4 pb-4">
          <div className="flex items-center gap-3 p-4 bg-gradient-to-r from-purple-500/20 to-purple-600/10 border border-purple-500/30 rounded-xl">
            <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 10l-1 1-5-5 1-1 5 5z" />
                <path d="M19 15l-5-5" />
                <path d="M4 20l5-5" />
                <circle cx="19" cy="5" r="3" />
              </svg>
            </div>
            <div>
              <div className="font-semibold text-purple-300">
                Order in the Court!
              </div>
              <div className="text-sm text-purple-400/80">
                The Honorable Judge is speaking. Please wait.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AudioPlayer;
