"""
Whisper Streaming Service

Per AUDIO.md Section 2:
- Streaming transcription only
- Verbatim capture
- Preserve filler words and pauses
- No semantic cleanup

Per AUDIO.md - Audio Processing Pipeline:
- Whisper (STT) calls are handled by backend services
- Frontend streams mic audio → backend → Whisper → text → agent
- No keys are exposed in frontend or agent code

Per ARCHITECTURE.md:
- User: Mic → WebRTC → Whisper → Text
- All audio must be streamed (no blocking)
- API keys (OpenAI, Whisper) are stored only in backend environment variables
"""

import asyncio
import logging
import time
from typing import Optional, AsyncGenerator, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import os
import wave
import tempfile
import struct

from openai import OpenAI

logger = logging.getLogger(__name__)

from ..graph.trial_graph import TrialState, Role


# =============================================================================
# TRANSCRIPTION TYPES
# =============================================================================

class TranscriptionStatus(str, Enum):
    """Status of a transcription segment."""
    PARTIAL = "partial"      # In-progress, may change
    FINAL = "final"          # Complete, will not change
    SILENCE = "silence"      # Detected silence/pause
    ERROR = "error"          # Transcription error


@dataclass
class TranscriptionSegment:
    """
    A segment of transcribed speech.
    
    Per AUDIO.md Section 5: Transcript synced with audio timestamps.
    """
    text: str
    status: TranscriptionStatus
    start_time: float          # Seconds from session start
    end_time: float            # Seconds from session start
    confidence: float = 1.0    # 0.0-1.0 confidence score
    
    # Metadata
    segment_id: str = ""
    speaker_role: Optional[Role] = None  # Who is speaking
    contains_filler: bool = False  # True if contains um, uh, etc.
    contains_pause: bool = False   # True if contains [pause] marker
    
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence,
            "segment_id": self.segment_id,
            "speaker_role": self.speaker_role.value if self.speaker_role else None,
            "contains_filler": self.contains_filler,
            "contains_pause": self.contains_pause,
        }


@dataclass
class TranscriptionSession:
    """
    Active transcription session state.
    """
    session_id: str
    started_at: float = field(default_factory=time.time)
    
    # All segments in order
    segments: List[TranscriptionSegment] = field(default_factory=list)
    
    # Current partial segment (not yet finalized)
    partial_segment: Optional[TranscriptionSegment] = None
    
    # Audio buffer for chunking
    audio_buffer: bytes = b""
    
    # Timing
    last_audio_time: float = 0.0
    total_audio_duration: float = 0.0
    
    # State
    is_active: bool = True
    current_speaker: Optional[Role] = None
    
    def get_full_transcript(self) -> str:
        """Get complete transcript text."""
        texts = [seg.text for seg in self.segments if seg.status == TranscriptionStatus.FINAL]
        if self.partial_segment:
            texts.append(f"[{self.partial_segment.text}]")  # Mark partial
        return " ".join(texts)
    
    def get_recent_transcript(self, seconds: float = 30.0) -> str:
        """Get transcript from the last N seconds."""
        cutoff = time.time() - self.started_at - seconds
        recent = [
            seg.text for seg in self.segments
            if seg.start_time >= cutoff and seg.status == TranscriptionStatus.FINAL
        ]
        return " ".join(recent)
    
    def get_transcript_for_trial_state(self) -> List[Dict[str, Any]]:
        """
        Get transcript formatted for TrialState integration.
        
        Returns list of dicts compatible with TrialState.transcript.
        """
        return [
            {
                "role": seg.speaker_role.value if seg.speaker_role else "unknown",
                "text": seg.text,
                "audio_timestamp": seg.start_time,
                "phase": "",  # Filled in by caller
            }
            for seg in self.segments
            if seg.status == TranscriptionStatus.FINAL and seg.text
        ]


# =============================================================================
# FILLER WORD DETECTION
# =============================================================================

# Common filler words to preserve (per AUDIO.md: preserve filler words)
FILLER_WORDS = frozenset({
    "um", "uh", "er", "ah", "eh",
    "umm", "uhh", "hmm", "hm",
    "like", "you know", "i mean",
    "so", "well", "basically",
    "actually", "literally", "right",
})

# Pause indicators
PAUSE_MARKERS = frozenset({
    "...", "[pause]", "[silence]", "[inaudible]",
})


def contains_filler_words(text: str) -> bool:
    """Check if text contains filler words."""
    text_lower = text.lower()
    return any(filler in text_lower for filler in FILLER_WORDS)


def contains_pause_markers(text: str) -> bool:
    """Check if text contains pause markers."""
    return any(marker in text for marker in PAUSE_MARKERS)


# =============================================================================
# SILENCE DETECTION
# =============================================================================

class SilenceDetector:
    """
    Detects silence in audio stream.
    
    Per AUDIO.md: Silence, pauses, interruptions matter.
    """
    
    # Default thresholds
    SILENCE_THRESHOLD = 500      # RMS amplitude below this is silence
    MIN_SILENCE_DURATION_MS = 500  # Minimum silence to report
    
    def __init__(
        self,
        threshold: int = SILENCE_THRESHOLD,
        min_duration_ms: int = MIN_SILENCE_DURATION_MS
    ):
        self.threshold = threshold
        self.min_duration_ms = min_duration_ms
        
        # State
        self._silence_start: Optional[float] = None
        self._in_silence: bool = False
    
    def process_chunk(
        self,
        audio_data: bytes,
        timestamp: float,
        sample_width: int = 2
    ) -> Optional[Dict[str, Any]]:
        """
        Process audio chunk for silence detection.
        
        Args:
            audio_data: Raw PCM audio
            timestamp: Current timestamp
            sample_width: Bytes per sample
            
        Returns:
            Dict with silence info if silence detected, None otherwise
        """
        rms = self._calculate_rms(audio_data, sample_width)
        
        if rms < self.threshold:
            # Silence detected
            if not self._in_silence:
                self._silence_start = timestamp
                self._in_silence = True
        else:
            # Speech detected
            if self._in_silence:
                # End of silence
                silence_duration = timestamp - self._silence_start
                self._in_silence = False
                
                if silence_duration * 1000 >= self.min_duration_ms:
                    return {
                        "type": "silence",
                        "start": self._silence_start,
                        "end": timestamp,
                        "duration_ms": int(silence_duration * 1000)
                    }
        
        return None
    
    def _calculate_rms(self, audio_data: bytes, sample_width: int) -> float:
        """Calculate RMS amplitude of audio data."""
        if not audio_data:
            return 0.0
        
        if sample_width == 2:
            fmt = f"<{len(audio_data) // 2}h"  # Little-endian 16-bit
        else:
            return 0.0
        
        try:
            samples = struct.unpack(fmt, audio_data)
            
            # Calculate RMS
            sum_squares = sum(s * s for s in samples)
            rms = (sum_squares / len(samples)) ** 0.5
            
            return rms
        except struct.error:
            return 0.0
    
    def reset(self) -> None:
        """Reset silence detection state."""
        self._silence_start = None
        self._in_silence = False


# =============================================================================
# WHISPER STREAMING SERVICE
# =============================================================================

class WhisperService:
    """
    Streaming speech-to-text service using OpenAI Whisper.
    
    Per AUDIO.md Section 2:
    - Streaming transcription only
    - Verbatim capture
    - Preserve filler words and pauses
    - No semantic cleanup
    
    Implementation uses chunked audio processing for streaming effect
    since Whisper API doesn't support true real-time streaming.
    """
    
    # Audio configuration
    SAMPLE_RATE = 16000          # 16kHz for Whisper
    CHANNELS = 1                  # Mono
    SAMPLE_WIDTH = 2              # 16-bit
    
    # Chunking configuration
    CHUNK_DURATION_MS = 3000      # 3 second chunks for processing
    MIN_CHUNK_DURATION_MS = 500   # Minimum audio to process
    SILENCE_THRESHOLD_MS = 1500   # Silence duration to force segment
    
    def __init__(self, client: Optional[OpenAI] = None):
        """
        Initialize Whisper service.
        
        Args:
            client: Optional OpenAI client for dependency injection
        """
        self.client = client or OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Active sessions
        self._sessions: Dict[str, TranscriptionSession] = {}
        
        # Callbacks for real-time updates
        self._segment_callbacks: Dict[str, List[Callable]] = {}
        
        # Silence detector per session
        self._silence_detectors: Dict[str, SilenceDetector] = {}
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    def create_session(
        self,
        session_id: str,
        current_speaker: Optional[Role] = None
    ) -> TranscriptionSession:
        """
        Create a new transcription session.
        
        Args:
            session_id: Unique session identifier
            current_speaker: Optional role of current speaker
            
        Returns:
            New TranscriptionSession
        """
        session = TranscriptionSession(
            session_id=session_id,
            current_speaker=current_speaker
        )
        self._sessions[session_id] = session
        self._segment_callbacks[session_id] = []
        self._silence_detectors[session_id] = SilenceDetector()
        return session
    
    def get_session(self, session_id: str) -> Optional[TranscriptionSession]:
        """Get an active session."""
        return self._sessions.get(session_id)
    
    def set_speaker(self, session_id: str, speaker: Role) -> None:
        """Update current speaker for a session."""
        session = self._sessions.get(session_id)
        if session:
            session.current_speaker = speaker
    
    def end_session(self, session_id: str) -> Optional[TranscriptionSession]:
        """
        End a transcription session.
        
        Processes any remaining audio buffer before closing.
        
        Returns:
            The completed session, or None if not found
        """
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        session.is_active = False
        
        # Finalize any partial segment
        if session.partial_segment:
            session.partial_segment.status = TranscriptionStatus.FINAL
            session.segments.append(session.partial_segment)
            session.partial_segment = None
        
        # Cleanup
        del self._sessions[session_id]
        if session_id in self._segment_callbacks:
            del self._segment_callbacks[session_id]
        if session_id in self._silence_detectors:
            del self._silence_detectors[session_id]
        
        return session
    
    def register_callback(
        self,
        session_id: str,
        callback: Callable[[TranscriptionSegment], None]
    ) -> None:
        """
        Register callback for real-time transcription updates.
        
        Args:
            session_id: Session to subscribe to
            callback: Function called with each new segment
        """
        if session_id in self._segment_callbacks:
            self._segment_callbacks[session_id].append(callback)
    
    def unregister_callback(
        self,
        session_id: str,
        callback: Callable[[TranscriptionSegment], None]
    ) -> None:
        """Unregister a callback."""
        if session_id in self._segment_callbacks:
            try:
                self._segment_callbacks[session_id].remove(callback)
            except ValueError:
                pass
    
    def _notify_callbacks(
        self,
        session_id: str,
        segment: TranscriptionSegment
    ) -> None:
        """Notify all registered callbacks of new segment."""
        callbacks = self._segment_callbacks.get(session_id, [])
        for callback in callbacks:
            try:
                callback(segment)
            except Exception as e:
                logger.error(
                    f"Whisper callback error for session {session_id}: {e}",
                    exc_info=True
                )
    
    # =========================================================================
    # AUDIO PROCESSING
    # =========================================================================
    
    async def process_audio_chunk(
        self,
        session_id: str,
        audio_data: bytes,
        timestamp: float
    ) -> Optional[TranscriptionSegment]:
        """
        Process incoming audio chunk.
        
        Per ARCHITECTURE.md: Mic → WebRTC → Whisper → Text
        
        Args:
            session_id: Active session ID
            audio_data: Raw PCM audio bytes
            timestamp: Timestamp of this chunk
            
        Returns:
            TranscriptionSegment if transcription produced, None otherwise
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return None
        
        # Check for silence
        silence_detector = self._silence_detectors.get(session_id)
        if silence_detector:
            silence_event = silence_detector.process_chunk(audio_data, timestamp)
            if silence_event and session.audio_buffer:
                # Force process on significant silence
                return await self._process_buffer(session)
        
        # Add to buffer
        session.audio_buffer += audio_data
        session.last_audio_time = timestamp
        
        # Calculate buffer duration
        buffer_duration_ms = self._calculate_duration_ms(session.audio_buffer)
        
        # Check if we have enough audio to process
        if buffer_duration_ms < self.MIN_CHUNK_DURATION_MS:
            return None
        
        # Process if we hit chunk threshold
        if buffer_duration_ms >= self.CHUNK_DURATION_MS:
            return await self._process_buffer(session)
        
        return None
    
    async def force_process(self, session_id: str) -> Optional[TranscriptionSegment]:
        """
        Force processing of current buffer.
        
        Used when:
        - Detecting end of speech
        - Judge interrupt (need immediate transcription)
        - Session ending
        """
        session = self._sessions.get(session_id)
        if not session or not session.audio_buffer:
            return None
        
        return await self._process_buffer(session)
    
    async def _process_buffer(
        self,
        session: TranscriptionSession
    ) -> Optional[TranscriptionSegment]:
        """
        Process audio buffer through Whisper.
        
        Per AUDIO.md:
        - Verbatim capture
        - Preserve filler words and pauses
        - No semantic cleanup
        """
        if not session.audio_buffer:
            return None
        
        # Calculate timing
        buffer_duration = self._calculate_duration_ms(session.audio_buffer) / 1000.0
        start_time = session.total_audio_duration
        end_time = start_time + buffer_duration
        
        # Update session timing
        session.total_audio_duration = end_time
        
        # Convert buffer to WAV for Whisper API
        audio_file = self._create_wav_file(session.audio_buffer)
        
        # Clear buffer
        session.audio_buffer = b""
        
        try:
            # Call Whisper API
            # Per AUDIO.md: No semantic cleanup - use verbatim prompt
            transcription = await asyncio.to_thread(
                self._transcribe_audio,
                audio_file
            )
            
            if not transcription or not transcription.strip():
                # Detected silence/no speech
                segment = TranscriptionSegment(
                    text="",
                    status=TranscriptionStatus.SILENCE,
                    start_time=start_time,
                    end_time=end_time,
                    segment_id=f"{session.session_id}_{len(session.segments)}",
                    speaker_role=session.current_speaker,
                    contains_pause=True
                )
            else:
                # Create segment with verbatim transcription
                segment = TranscriptionSegment(
                    text=transcription,
                    status=TranscriptionStatus.FINAL,
                    start_time=start_time,
                    end_time=end_time,
                    segment_id=f"{session.session_id}_{len(session.segments)}",
                    speaker_role=session.current_speaker,
                    contains_filler=contains_filler_words(transcription),
                    contains_pause=contains_pause_markers(transcription)
                )
                
                session.segments.append(segment)
            
            # Notify callbacks
            self._notify_callbacks(session.session_id, segment)
            
            return segment
            
        except Exception as e:
            # Return error segment
            segment = TranscriptionSegment(
                text=f"[transcription error: {str(e)}]",
                status=TranscriptionStatus.ERROR,
                start_time=start_time,
                end_time=end_time,
                segment_id=f"{session.session_id}_{len(session.segments)}_error",
                speaker_role=session.current_speaker
            )
            self._notify_callbacks(session.session_id, segment)
            return segment
        
        finally:
            # Cleanup temp file
            try:
                os.unlink(audio_file)
            except Exception:
                pass
    
    def _transcribe_audio(self, audio_file_path: str) -> str:
        """
        Transcribe audio file using Whisper API.
        
        Per AUDIO.md Section 2:
        - Verbatim capture
        - Preserve filler words and pauses
        - No semantic cleanup
        """
        with open(audio_file_path, "rb") as audio_file:
            # Use specific prompt to preserve filler words
            # This encourages Whisper to transcribe verbatim
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
                # Prompt to preserve fillers and hesitations
                prompt=(
                    "Transcribe exactly as spoken, including all filler words "
                    "like um, uh, er, ah, hmm, like, you know, I mean. "
                    "Include all hesitations and false starts. "
                    "Do not correct grammar or clean up speech."
                ),
                response_format="text",
            )
        
        return response.strip() if response else ""
    
    # =========================================================================
    # AUDIO UTILITIES
    # =========================================================================
    
    def _calculate_duration_ms(self, audio_data: bytes) -> int:
        """Calculate duration of audio data in milliseconds."""
        if not audio_data:
            return 0
        
        # bytes / (sample_rate * channels * sample_width) * 1000
        bytes_per_second = self.SAMPLE_RATE * self.CHANNELS * self.SAMPLE_WIDTH
        return int(len(audio_data) / bytes_per_second * 1000)
    
    def _create_wav_file(self, audio_data: bytes) -> str:
        """
        Create temporary WAV file from raw PCM data.
        
        Returns:
            Path to temporary WAV file
        """
        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".wav")
        
        try:
            with wave.open(path, "wb") as wav_file:
                wav_file.setnchannels(self.CHANNELS)
                wav_file.setsampwidth(self.SAMPLE_WIDTH)
                wav_file.setframerate(self.SAMPLE_RATE)
                wav_file.writeframes(audio_data)
        finally:
            os.close(fd)
        
        return path
    
    # =========================================================================
    # STREAMING INTERFACE
    # =========================================================================
    
    async def stream_transcription(
        self,
        session_id: str,
        audio_stream: AsyncGenerator[bytes, None],
        speaker: Optional[Role] = None
    ) -> AsyncGenerator[TranscriptionSegment, None]:
        """
        Stream transcription from async audio generator.
        
        Per ARCHITECTURE.md: All audio must be streamed (no blocking).
        
        Args:
            session_id: Session ID
            audio_stream: Async generator yielding audio chunks
            speaker: Optional speaker role
            
        Yields:
            TranscriptionSegment for each processed chunk
        """
        session = self.create_session(session_id, current_speaker=speaker)
        
        try:
            timestamp = 0.0
            
            async for audio_chunk in audio_stream:
                # Calculate timestamp
                chunk_duration = self._calculate_duration_ms(audio_chunk) / 1000.0
                
                # Process chunk
                segment = await self.process_audio_chunk(
                    session_id,
                    audio_chunk,
                    timestamp
                )
                
                if segment:
                    yield segment
                
                timestamp += chunk_duration
            
            # Process any remaining buffer
            final_segment = await self.force_process(session_id)
            if final_segment:
                yield final_segment
                
        finally:
            self.end_session(session_id)
    
    # =========================================================================
    # TRANSCRIPT ACCESS
    # =========================================================================
    
    def get_transcript(self, session_id: str) -> str:
        """Get full transcript for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return ""
        return session.get_full_transcript()
    
    def get_recent_transcript(
        self,
        session_id: str,
        seconds: float = 30.0
    ) -> str:
        """Get recent transcript (last N seconds)."""
        session = self._sessions.get(session_id)
        if not session:
            return ""
        return session.get_recent_transcript(seconds)
    
    def get_segments(
        self,
        session_id: str,
        since_time: Optional[float] = None
    ) -> List[TranscriptionSegment]:
        """
        Get transcription segments.
        
        Args:
            session_id: Session ID
            since_time: Optional start time filter
            
        Returns:
            List of segments
        """
        session = self._sessions.get(session_id)
        if not session:
            return []
        
        segments = session.segments
        
        if since_time is not None:
            segments = [s for s in segments if s.start_time >= since_time]
        
        return segments
    
    def get_transcript_for_state(
        self,
        session_id: str,
        state: TrialState
    ) -> List[Dict[str, Any]]:
        """
        Get transcript formatted for TrialState.
        
        Args:
            session_id: Session ID
            state: Current trial state (for phase info)
            
        Returns:
            List of transcript entries compatible with TrialState.transcript
        """
        session = self._sessions.get(session_id)
        if not session:
            return []
        
        entries = []
        for seg in session.segments:
            if seg.status == TranscriptionStatus.FINAL and seg.text:
                entries.append({
                    "role": seg.speaker_role.value if seg.speaker_role else "unknown",
                    "text": seg.text,
                    "audio_timestamp": seg.start_time,
                    "phase": state.phase.value,
                })
        
        return entries


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_whisper_service(client: Optional[OpenAI] = None) -> WhisperService:
    """
    Create a new Whisper service instance.
    
    Args:
        client: Optional OpenAI client for dependency injection
        
    Returns:
        WhisperService instance
    """
    return WhisperService(client=client)
