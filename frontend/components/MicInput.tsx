/**
 * MicInput - Push-to-Talk Button Component
 * 
 * Per ARCHITECTURE.md Section 1:
 * - Frontend responsible for audio capture
 * - Frontend must NEVER control trial logic
 * 
 * Per AUDIO.md:
 * - Audio-first interaction
 * - Stream mic audio to Whisper
 */

"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";

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

export interface TrialState {
  sessionId: string;
  phase: TrialPhase;
  currentSpeaker: Role | null;
  humanRole: Role | null;
  canSpeak: boolean;
  isObjectionPending: boolean;
  isJudgeInterrupting: boolean;
}

export interface SpeakerPermissions {
  canSpeak: boolean;
  reason?: string;
}

export interface MicInputProps {
  /** Current session ID */
  sessionId: string;
  /** Current trial state from backend */
  trialState: TrialState;
  /** Speaker permissions from backend */
  permissions: SpeakerPermissions;
  /** Callback when transcription is received */
  onTranscription?: (text: string, isFinal: boolean) => void;
  /** Callback when recording starts */
  onRecordingStart?: () => void;
  /** Callback when recording stops */
  onRecordingStop?: () => void;
  /** Custom class name */
  className?: string;
  /** Size variant */
  size?: "sm" | "md" | "lg";
}

// =============================================================================
// AUDIO RECORDER HOOK
// =============================================================================

interface AudioRecorderState {
  isRecording: boolean;
  isPaused: boolean;
  duration: number;
  error: string | null;
}

interface AudioRecorderOptions {
  sessionId: string;
  wsUrl?: string;
  sampleRate?: number;
  onTranscription?: (text: string, isFinal: boolean) => void;
  onRecordingStart?: () => void;
  onRecordingStop?: () => void;
  onError?: (error: string) => void;
}

function useAudioRecorder(options: AudioRecorderOptions) {
  const {
    sessionId,
    wsUrl = `ws://localhost:8000/api/audio/${sessionId}/mic`,
    sampleRate = 16000,
    onTranscription,
    onRecordingStart,
    onRecordingStop,
    onError,
  } = options;

  const [state, setState] = useState<AudioRecorderState>({
    isRecording: false,
    isPaused: false,
    duration: 0,
    error: null,
  });

  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const durationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isSupported =
    typeof window !== "undefined" &&
    !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

  const cleanup = useCallback(() => {
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  const startRecording = useCallback(async () => {
    if (!isSupported) {
      const error = "Audio recording not supported in this browser";
      setState((prev) => ({ ...prev, error }));
      onError?.(error);
      return;
    }

    try {
      setState({
        isRecording: false,
        isPaused: false,
        duration: 0,
        error: null,
      });

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      mediaStreamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);

      // TODO: Migrate to AudioWorklet for better performance
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setState((prev) => ({ ...prev, isRecording: true }));
        onRecordingStart?.();

        durationIntervalRef.current = setInterval(() => {
          setState((prev) => ({ ...prev, duration: prev.duration + 100 }));
        }, 100);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "transcription") {
            onTranscription?.(data.text, data.is_final);
          } else if (data.type === "error") {
            setState((prev) => ({ ...prev, error: data.message }));
            onError?.(data.message);
          }
        } catch {
          // Non-JSON message, ignore
        }
      };

      ws.onerror = () => {
        const error = "WebSocket connection error";
        setState((prev) => ({ ...prev, error }));
        onError?.(error);
      };

      ws.onclose = () => {
        if (state.isRecording) {
          setState((prev) => ({ ...prev, isRecording: false }));
          onRecordingStop?.();
        }
      };

      processor.onaudioprocess = (event) => {
        if (ws.readyState === WebSocket.OPEN) {
          const inputData = event.inputBuffer.getChannelData(0);
          
          // Convert Float32 to Int16 for Whisper
          const int16Data = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]));
            int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }
          
          ws.send(int16Data.buffer);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

    } catch (err) {
      const error =
        err instanceof Error ? err.message : "Failed to start recording";
      setState((prev) => ({ ...prev, error }));
      onError?.(error);
      cleanup();
    }
  }, [
    isSupported,
    wsUrl,
    sampleRate,
    onTranscription,
    onRecordingStart,
    onRecordingStop,
    onError,
    cleanup,
    state.isRecording,
  ]);

  const stopRecording = useCallback(() => {
    cleanup();
    setState((prev) => ({ ...prev, isRecording: false }));
    onRecordingStop?.();
  }, [cleanup, onRecordingStop]);

  return {
    state,
    startRecording,
    stopRecording,
    isSupported,
  };
}

// =============================================================================
// STYLES
// =============================================================================

const sizeClasses = {
  sm: "w-16 h-16",
  md: "w-24 h-24",
  lg: "w-32 h-32",
};

const iconSizes = {
  sm: 24,
  md: 36,
  lg: 48,
};

// =============================================================================
// COMPONENT
// =============================================================================

export function MicInput({
  sessionId,
  trialState,
  permissions,
  onTranscription,
  onRecordingStart,
  onRecordingStop,
  className = "",
  size = "md",
}: MicInputProps) {
  const [isPressed, setIsPressed] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  // Determine if user can speak
  const canSpeak = permissions.canSpeak && !trialState.isJudgeInterrupting;
  const isDisabled = !canSpeak;

  // Audio recorder hook
  const { state, startRecording, stopRecording, isSupported } =
    useAudioRecorder({
      sessionId,
      onTranscription,
      onRecordingStart: () => {
        onRecordingStart?.();
      },
      onRecordingStop: () => {
        onRecordingStop?.();
      },
      onError: (error) => {
        console.error("Recording error:", error);
      },
    });

  const { isRecording, duration, error } = state;

  // Handle press start
  const handlePressStart = useCallback(
    async (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault();
      if (isDisabled || !isSupported) return;

      setIsPressed(true);
      await startRecording();
    },
    [isDisabled, isSupported, startRecording]
  );

  // Handle press end
  const handlePressEnd = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault();
      if (!isRecording) return;

      setIsPressed(false);
      stopRecording();
    },
    [isRecording, stopRecording]
  );

  // Handle keyboard (space bar)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat && !isDisabled && !isRecording) {
        e.preventDefault();
        setIsPressed(true);
        startRecording();
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space" && isRecording) {
        e.preventDefault();
        setIsPressed(false);
        stopRecording();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [isDisabled, isRecording, startRecording, stopRecording]);

  // Stop recording if judge interrupts
  useEffect(() => {
    if (trialState.isJudgeInterrupting && isRecording) {
      stopRecording();
      setIsPressed(false);
    }
  }, [trialState.isJudgeInterrupting, isRecording, stopRecording]);

  // Format duration
  const formatDuration = (ms: number): string => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  // Get button state classes
  const getButtonClasses = (): string => {
    const base = `
      relative rounded-full transition-all duration-200 
      flex items-center justify-center
      focus:outline-none focus:ring-4 focus:ring-offset-2
      select-none touch-none
    `;

    if (isDisabled) {
      return `${base} bg-gray-300 cursor-not-allowed opacity-50`;
    }

    if (isRecording) {
      return `${base} bg-red-500 hover:bg-red-600 cursor-pointer shadow-lg shadow-red-500/50 animate-pulse`;
    }

    if (isPressed) {
      return `${base} bg-red-400 cursor-pointer scale-95`;
    }

    return `${base} bg-blue-500 hover:bg-blue-600 cursor-pointer shadow-lg hover:shadow-xl`;
  };

  // Microphone icon
  const MicIcon = () => (
    <svg
      width={iconSizes[size]}
      height={iconSizes[size]}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-white"
    >
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );

  // Recording indicator
  const RecordingIndicator = () => (
    <div className="absolute -top-1 -right-1 w-4 h-4">
      <span className="absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 animate-ping" />
      <span className="relative inline-flex rounded-full h-4 w-4 bg-red-500" />
    </div>
  );

  return (
    <div className={`flex flex-col items-center gap-3 ${className}`}>
      {/* Main button */}
      <div className="relative">
        <button
          type="button"
          className={`${getButtonClasses()} ${sizeClasses[size]}`}
          onMouseDown={handlePressStart}
          onMouseUp={handlePressEnd}
          onMouseLeave={handlePressEnd}
          onTouchStart={handlePressStart}
          onTouchEnd={handlePressEnd}
          onMouseEnter={() => setShowTooltip(true)}
          onFocus={() => setShowTooltip(true)}
          onBlur={() => setShowTooltip(false)}
          disabled={isDisabled}
          aria-label={isRecording ? "Release to stop recording" : "Hold to speak"}
          aria-pressed={isRecording}
        >
          <MicIcon />
          {isRecording && <RecordingIndicator />}
        </button>

        {/* Tooltip */}
        {showTooltip && isDisabled && permissions.reason && (
          <div className="absolute -top-12 left-1/2 -translate-x-1/2 px-3 py-1 bg-gray-900 text-white text-sm rounded whitespace-nowrap z-10">
            {permissions.reason}
            <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
          </div>
        )}
      </div>

      {/* Status text */}
      <div className="text-center">
        {isRecording ? (
          <div className="flex items-center gap-2 text-red-500 font-medium">
            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            Recording {formatDuration(duration)}
          </div>
        ) : isDisabled ? (
          <span className="text-gray-400 text-sm">
            {trialState.isJudgeInterrupting
              ? "Judge is speaking"
              : permissions.reason || "Cannot speak now"}
          </span>
        ) : (
          <span className="text-gray-500 text-sm">
            Hold to speak (or press Space)
          </span>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="text-red-500 text-sm bg-red-50 px-3 py-1 rounded">
          {error}
        </div>
      )}

      {/* Browser support warning */}
      {!isSupported && (
        <div className="text-amber-600 text-sm bg-amber-50 px-3 py-2 rounded">
          Audio recording is not supported in this browser.
          Please use Chrome, Firefox, or Safari.
        </div>
      )}
    </div>
  );
}

export default MicInput;
