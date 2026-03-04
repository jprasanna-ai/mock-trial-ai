"""
Text-to-Speech Service

Per AUDIO.md Section 3:
- One persistent voice per agent per session
- Persona controls: Pace, Authority, Nervousness, Interruptiveness
- Judge voice ALWAYS has priority

Per AUDIO.md - Audio Processing Pipeline:
- TTS calls are handled by backend services
- Agents request TTS via backend with persona parameters
- No keys are exposed in frontend or agent code

Per ARCHITECTURE.md:
- AI: Text → GPT-4.1 → Persona Conditioning → TTS → WebRTC → Speaker
- All audio must be streamed (no blocking)
- API keys (OpenAI, TTS) are stored only in backend environment variables
"""

import asyncio
import logging
import os
import time
from typing import Optional, Dict, Any, List, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO

from openai import OpenAI

logger = logging.getLogger(__name__)

from ..graph.trial_graph import Role


# =============================================================================
# VOICE CONFIGURATION
# =============================================================================

class OpenAIVoice(str, Enum):
    """Available OpenAI TTS voices (gpt-4o-mini-tts supports all of these)."""
    ALLOY = "alloy"
    ASH = "ash"         # clearly male, young
    BALLAD = "ballad"
    CORAL = "coral"     # clearly female, young
    ECHO = "echo"
    FABLE = "fable"
    NOVA = "nova"       # female, energetic
    ONYX = "onyx"
    SAGE = "sage"
    SHIMMER = "shimmer"  # female, warm


# Voices tuned for gpt-4o-mini-tts with clear gender distinction:
#   Male:   ASH (young, clear male)
#   Female: CORAL (young, clear female)
DEFAULT_VOICE_MAPPING: Dict[Role, OpenAIVoice] = {
    Role.JUDGE: OpenAIVoice.SAGE,
    Role.ATTORNEY_PLAINTIFF: OpenAIVoice.CORAL,
    Role.ATTORNEY_DEFENSE: OpenAIVoice.ASH,
    Role.WITNESS: OpenAIVoice.CORAL,
    Role.COACH: OpenAIVoice.SAGE,
}

FEMALE_VOICES = [OpenAIVoice.CORAL, OpenAIVoice.NOVA, OpenAIVoice.SHIMMER]
MALE_VOICES = [OpenAIVoice.ASH, OpenAIVoice.ECHO, OpenAIVoice.BALLAD]

COMMON_FEMALE_NAMES = frozenset({
    "mary", "patricia", "jennifer", "linda", "barbara", "elizabeth", "susan",
    "jessica", "sarah", "karen", "lisa", "nancy", "betty", "margaret", "sandra",
    "ashley", "dorothy", "kimberly", "emily", "donna", "michelle", "carol",
    "amanda", "melissa", "deborah", "stephanie", "rebecca", "sharon", "laura",
    "cynthia", "kathleen", "amy", "angela", "shirley", "anna", "brenda",
    "pamela", "emma", "nicole", "helen", "samantha", "katherine", "christine",
    "debra", "rachel", "carolyn", "janet", "catherine", "maria", "heather",
    "diane", "ruth", "julie", "olivia", "joyce", "virginia", "victoria",
    "kelly", "lauren", "christina", "joan", "evelyn", "judith", "megan",
    "andrea", "cheryl", "hannah", "jacqueline", "martha", "gloria", "teresa",
    "ann", "sara", "madison", "frances", "kathryn", "janice", "jean", "abigail",
    "alice", "judy", "sophia", "grace", "denise", "amber", "doris", "marilyn",
    "danielle", "beverly", "isabella", "theresa", "diana", "natalie", "brittany",
    "charlotte", "marie", "kayla", "alexis", "lori", "elena", "maya", "rosa",
    "sofia", "ana", "gabriela", "carmen", "valentina", "lucia", "adriana",
    "alejandra", "mariana", "paula", "claudia", "priya", "anita", "sunita",
    "nina", "tanya", "sonia", "meena", "dana", "jodie", "micah",
})

COMMON_MALE_NAMES = frozenset({
    "james", "robert", "john", "michael", "david", "william", "richard",
    "joseph", "thomas", "charles", "christopher", "daniel", "matthew", "anthony",
    "mark", "donald", "steven", "paul", "andrew", "joshua", "kenneth",
    "kevin", "brian", "george", "timothy", "ronald", "edward", "jason",
    "jeffrey", "ryan", "jacob", "gary", "nicholas", "eric", "jonathan",
    "stephen", "larry", "justin", "scott", "brandon", "benjamin", "samuel",
    "raymond", "gregory", "frank", "alexander", "patrick", "jack", "dennis",
    "jerry", "tyler", "aaron", "jose", "adam", "nathan", "henry", "peter",
    "zachary", "douglas", "harold", "kyle", "noah", "gerald", "carl",
    "ethan", "arthur", "lawrence", "jesse", "dylan", "bryan", "joe",
    "jordan", "billy", "bruce", "albert", "willie", "gabriel", "logan",
    "alan", "juan", "ralph", "roy", "eugene", "russell", "bobby",
    "mason", "philip", "louis", "harry", "carlos", "miguel", "luis",
    "rafael", "diego", "sergio", "alejandro", "pablo", "ricardo", "raj",
    "arjun", "vikram", "rahul", "amit", "suresh", "darren", "dylan",
    "parker", "dakota", "aaron", "chris", "ryan",
})


def guess_gender_from_name(name: str) -> str:
    """Guess gender from first name. Returns 'female', 'male', or 'unknown'."""
    if not name:
        return "unknown"
    first_name = name.strip().split()[0].lower()
    if first_name in COMMON_FEMALE_NAMES:
        return "female"
    if first_name in COMMON_MALE_NAMES:
        return "male"
    return "unknown"


def get_voice_for_speaker(name: str, role: Role, speaker_index: int = 0) -> OpenAIVoice:
    """Select a clearly gendered TTS voice for gpt-4o-mini-tts.

    Uses CORAL (female) and ASH (male) as primary voices — these have
    unambiguous gender on the gpt-4o-mini-tts model.
    """
    if name and name.lower() == "court clerk":
        return OpenAIVoice.SHIMMER

    gender = guess_gender_from_name(name)

    if role == Role.ATTORNEY_PLAINTIFF:
        return OpenAIVoice.CORAL if gender == "female" else OpenAIVoice.ASH
    elif role == Role.ATTORNEY_DEFENSE:
        return OpenAIVoice.NOVA if gender == "female" else OpenAIVoice.ECHO
    elif role == Role.JUDGE:
        return OpenAIVoice.ASH if gender == "male" else OpenAIVoice.CORAL
    elif role == Role.WITNESS:
        if gender == "female":
            return FEMALE_VOICES[speaker_index % len(FEMALE_VOICES)]
        elif gender == "male":
            return MALE_VOICES[speaker_index % len(MALE_VOICES)]
        return OpenAIVoice.SAGE
    
    return DEFAULT_VOICE_MAPPING.get(role, OpenAIVoice.SAGE)


@dataclass
class VoicePersona:
    """
    Voice persona parameters for TTS.
    
    The `instructions` field is the primary way to control emotion, tone,
    and speaking style when using gpt-4o-mini-tts.
    """
    voice: OpenAIVoice = OpenAIVoice.ALLOY
    
    # Speed: 0.25 to 4.0 (1.0 is normal)
    speed: float = 1.0
    
    # Emotional / style instructions for gpt-4o-mini-tts
    instructions: str = ""
    
    # Persona traits (affect text conditioning, not direct TTS params)
    authority: float = 0.5
    nervousness: float = 0.0
    warmth: float = 0.5
    
    # Priority for interrupt handling
    priority: int = 0
    
    def get_effective_speed(self) -> float:
        base = self.speed
        if self.nervousness > 0.5:
            base *= 1.0 + (self.nervousness - 0.5) * 0.2
        return max(0.25, min(4.0, base))


# =============================================================================
# AUDIO SEGMENT
# =============================================================================

@dataclass
class TTSSegment:
    """A segment of generated audio."""
    audio_data: bytes
    text: str
    role: Role
    start_time: float
    duration: float
    segment_id: str
    was_interrupted: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without audio data)."""
        return {
            "text": self.text,
            "role": self.role.value,
            "start_time": self.start_time,
            "duration": self.duration,
            "segment_id": self.segment_id,
            "was_interrupted": self.was_interrupted,
        }


# =============================================================================
# TTS SESSION
# =============================================================================

@dataclass
class TTSSession:
    """Active TTS session state."""
    session_id: str
    
    # Voice assignments per role
    voice_personas: Dict[Role, VoicePersona] = field(default_factory=dict)
    
    # Current playback state
    current_speaker: Optional[Role] = None
    is_playing: bool = False
    
    # Interrupt state
    interrupt_requested: bool = False
    interrupt_by: Optional[Role] = None
    
    # Generated segments
    segments: List[TTSSegment] = field(default_factory=list)
    
    # Timing
    started_at: float = field(default_factory=time.time)
    total_audio_duration: float = 0.0


# =============================================================================
# TTS SERVICE
# =============================================================================

class TTSService:
    """
    Text-to-Speech service using OpenAI TTS.
    
    Per AUDIO.md Section 3:
    - One persistent voice per agent per session
    - Persona controls: Pace, Authority, Nervousness, Interruptiveness
    - Judge voice ALWAYS has priority
    
    Per AUDIO.md Section 4:
    - Judges may interrupt any speaker
    - Objections may interrupt testimony
    - Interrupted audio must stop immediately
    """
    
    # gpt-4o-mini-tts supports the `instructions` parameter for emotional delivery
    MODEL = "gpt-4o-mini-tts"
    
    # Audio format — mp3 for universal browser compatibility
    RESPONSE_FORMAT = "mp3"
    SAMPLE_RATE = 24000
    
    # Chunk size for streaming (bytes)
    STREAM_CHUNK_SIZE = 4096
    
    def __init__(self, client: Optional[OpenAI] = None):
        """
        Initialize TTS service.
        
        Args:
            client: Optional OpenAI client for dependency injection
        """
        self.client = client or OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Active sessions
        self._sessions: Dict[str, TTSSession] = {}
        
        # Playback callbacks
        self._playback_callbacks: Dict[str, List[Callable]] = {}
        
        # Interrupt callbacks
        self._interrupt_callbacks: Dict[str, List[Callable]] = {}
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    def create_session(self, session_id: str) -> TTSSession:
        """
        Create a new TTS session with default voice assignments.
        
        Per AUDIO.md: One persistent voice per agent per session.
        """
        session = TTSSession(session_id=session_id)
        
        # Assign default voices
        for role, voice in DEFAULT_VOICE_MAPPING.items():
            persona = VoicePersona(voice=voice)
            
            # Set judge priority highest
            if role == Role.JUDGE:
                persona.priority = 100
                persona.authority = 0.9
            elif role in {Role.ATTORNEY_PLAINTIFF, Role.ATTORNEY_DEFENSE}:
                persona.priority = 50
                persona.authority = 0.7
            elif role == Role.WITNESS:
                persona.priority = 10
            elif role == Role.COACH:
                persona.priority = 5
            
            session.voice_personas[role] = persona
        
        self._sessions[session_id] = session
        self._playback_callbacks[session_id] = []
        self._interrupt_callbacks[session_id] = []
        
        return session
    
    def get_session(self, session_id: str) -> Optional[TTSSession]:
        """Get an active session."""
        return self._sessions.get(session_id)
    
    def end_session(self, session_id: str) -> Optional[TTSSession]:
        """End a TTS session."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        del self._sessions[session_id]
        if session_id in self._playback_callbacks:
            del self._playback_callbacks[session_id]
        if session_id in self._interrupt_callbacks:
            del self._interrupt_callbacks[session_id]
        
        return session
    
    def configure_voice(
        self,
        session_id: str,
        role: Role,
        persona: VoicePersona
    ) -> None:
        """
        Configure voice persona for a role.
        
        Per AUDIO.md: Persona controls pace, authority, nervousness.
        """
        session = self._sessions.get(session_id)
        if session:
            # Preserve judge priority
            if role == Role.JUDGE:
                persona.priority = 100
            session.voice_personas[role] = persona
    
    def update_persona_trait(
        self,
        session_id: str,
        role: Role,
        trait: str,
        value: float
    ) -> None:
        """Update a single persona trait."""
        session = self._sessions.get(session_id)
        if session and role in session.voice_personas:
            persona = session.voice_personas[role]
            if hasattr(persona, trait):
                setattr(persona, trait, value)
    
    # =========================================================================
    # CALLBACKS
    # =========================================================================
    
    def register_playback_callback(
        self,
        session_id: str,
        callback: Callable[[TTSSegment], None]
    ) -> None:
        """Register callback for playback events."""
        if session_id in self._playback_callbacks:
            self._playback_callbacks[session_id].append(callback)
    
    def register_interrupt_callback(
        self,
        session_id: str,
        callback: Callable[[Role, Role], None]
    ) -> None:
        """Register callback for interrupt events (interrupter, interrupted)."""
        if session_id in self._interrupt_callbacks:
            self._interrupt_callbacks[session_id].append(callback)
    
    def _notify_playback(self, session_id: str, segment: TTSSegment) -> None:
        """Notify playback callbacks."""
        for callback in self._playback_callbacks.get(session_id, []):
            try:
                callback(segment)
            except Exception:
                pass
    
    def _notify_interrupt(
        self,
        session_id: str,
        interrupter: Role,
        interrupted: Role
    ) -> None:
        """Notify interrupt callbacks."""
        for callback in self._interrupt_callbacks.get(session_id, []):
            try:
                callback(interrupter, interrupted)
            except Exception:
                pass
    
    # =========================================================================
    # TEXT CONDITIONING
    # =========================================================================
    
    def _condition_text(self, text: str, persona: VoicePersona) -> str:
        """
        Light text conditioning for more natural TTS delivery.

        Only uses standard ASCII punctuation (commas, periods, ellipses)
        that all TTS engines handle reliably.
        """
        # Strip any non-ASCII punctuation that can confuse TTS
        text = text.replace("\u2014", ", ").replace("\u2013", ", ")  # em/en dash
        text = text.replace("\u201c", '"').replace("\u201d", '"')    # smart quotes
        text = text.replace("\u2018", "'").replace("\u2019", "'")

        # Nervous speakers: add slight pauses after sentences
        if persona.nervousness > 0.5:
            text = text.replace(". ", "... ")

        return text
    
    # =========================================================================
    # TTS GENERATION
    # =========================================================================
    
    async def generate_speech(
        self,
        session_id: str,
        text: str,
        role: Role
    ) -> Optional[TTSSegment]:
        """
        Generate speech audio from text.
        
        Per ARCHITECTURE.md: Text → Persona Conditioning → TTS
        
        Args:
            session_id: Active session ID
            text: Text to convert to speech
            role: Speaker role
            
        Returns:
            TTSSegment with audio data
        """
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        persona = session.voice_personas.get(role)
        if not persona:
            persona = VoicePersona(voice=DEFAULT_VOICE_MAPPING.get(role, OpenAIVoice.ALLOY))
        
        # Condition text based on persona
        conditioned_text = self._condition_text(text, persona)
        
        # Calculate timing
        start_time = session.total_audio_duration
        
        try:
            # Generate audio
            audio_data = await asyncio.to_thread(
                self._generate_audio,
                conditioned_text,
                persona
            )
            
            # Estimate duration (rough calculation)
            # OpenAI TTS produces ~24kbps for opus
            duration = len(audio_data) / 3000  # Rough estimate
            
            segment = TTSSegment(
                audio_data=audio_data,
                text=text,
                role=role,
                start_time=start_time,
                duration=duration,
                segment_id=f"{session_id}_{len(session.segments)}"
            )
            
            session.segments.append(segment)
            session.total_audio_duration += duration
            
            self._notify_playback(session_id, segment)
            
            return segment
            
        except Exception as e:
            logger.error(
                f"TTS generation error for session {session_id}: {e}",
                exc_info=True
            )
            return None
    
    # gpt-4o-mini-tts hard limit per request
    MAX_INPUT_CHARS = 4096

    @staticmethod
    def _split_text(text: str, limit: int) -> List[str]:
        """Split text into chunks ≤ limit chars, breaking at sentence boundaries."""
        if len(text) <= limit:
            return [text]

        chunks: List[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            # Find last sentence-ending punctuation within the limit
            cut = -1
            for delim in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
                idx = remaining.rfind(delim, 0, limit)
                if idx > cut:
                    cut = idx + len(delim) - 1  # include the punctuation, not the space
            if cut <= 0:
                # No sentence boundary found — fall back to last space
                cut = remaining.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            chunks.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()
        return [c for c in chunks if c]

    def _generate_audio(self, text: str, persona: VoicePersona) -> bytes:
        """Generate audio using OpenAI TTS API.

        Automatically chunks text that exceeds the 4096-char API limit and
        concatenates the resulting MP3 segments.
        """
        chunks = self._split_text(text, self.MAX_INPUT_CHARS)

        all_audio = BytesIO()
        for chunk in chunks:
            kwargs: Dict[str, Any] = dict(
                model=self.MODEL,
                voice=persona.voice.value,
                input=chunk,
                response_format=self.RESPONSE_FORMAT,
            )
            if self.MODEL.startswith("gpt-"):
                if persona.instructions:
                    kwargs["instructions"] = persona.instructions
            else:
                kwargs["speed"] = persona.get_effective_speed()

            response = self.client.audio.speech.create(**kwargs)
            for data in response.iter_bytes():
                all_audio.write(data)

        return all_audio.getvalue()
    
    # =========================================================================
    # STREAMING
    # =========================================================================
    
    async def stream_speech(
        self,
        session_id: str,
        text: str,
        role: Role
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream speech audio chunks.
        
        Per ARCHITECTURE.md: All audio must be streamed (no blocking).
        
        Args:
            session_id: Active session ID
            text: Text to convert to speech
            role: Speaker role
            
        Yields:
            Audio data chunks
        """
        session = self._sessions.get(session_id)
        if not session:
            return
        
        persona = session.voice_personas.get(role)
        if not persona:
            persona = VoicePersona(voice=DEFAULT_VOICE_MAPPING.get(role, OpenAIVoice.ALLOY))
        
        # Set current speaker
        session.current_speaker = role
        session.is_playing = True
        
        # Condition text
        conditioned_text = self._condition_text(text, persona)
        text_chunks = self._split_text(conditioned_text, self.MAX_INPUT_CHARS)
        
        try:
            for text_chunk in text_chunks:
                kwargs: Dict[str, Any] = dict(
                    model=self.MODEL,
                    voice=persona.voice.value,
                    input=text_chunk,
                    response_format=self.RESPONSE_FORMAT,
                )
                if self.MODEL.startswith("gpt-"):
                    if persona.instructions:
                        kwargs["instructions"] = persona.instructions
                else:
                    kwargs["speed"] = persona.get_effective_speed()
                response = await asyncio.to_thread(
                    lambda kw=kwargs: self.client.audio.speech.create(**kw)
                )
                
                for chunk in response.iter_bytes(chunk_size=self.STREAM_CHUNK_SIZE):
                    if session.interrupt_requested:
                        session.interrupt_requested = False
                        return
                    
                    yield chunk
                
        finally:
            session.is_playing = False
            session.current_speaker = None
    
    # =========================================================================
    # INTERRUPT HANDLING
    # =========================================================================
    
    def can_interrupt(
        self,
        session_id: str,
        interrupter: Role,
        current_speaker: Optional[Role] = None
    ) -> bool:
        """
        Check if a role can interrupt the current speaker.
        
        Per AUDIO.md Section 4:
        - Judges may interrupt any speaker
        - Objections may interrupt testimony
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        speaker = current_speaker or session.current_speaker
        if not speaker:
            return True  # No one speaking
        
        # Judge can always interrupt
        if interrupter == Role.JUDGE:
            return True
        
        # Get priorities
        interrupter_persona = session.voice_personas.get(interrupter)
        speaker_persona = session.voice_personas.get(speaker)
        
        if not interrupter_persona or not speaker_persona:
            return False
        
        # Higher priority can interrupt lower
        return interrupter_persona.priority > speaker_persona.priority
    
    def request_interrupt(
        self,
        session_id: str,
        interrupter: Role
    ) -> bool:
        """
        Request to interrupt current playback.
        
        Per AUDIO.md Section 4:
        - Interrupted audio must stop immediately
        
        Returns True if interrupt will be honored.
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        if not session.is_playing:
            return True  # Nothing to interrupt
        
        current = session.current_speaker
        if not self.can_interrupt(session_id, interrupter, current):
            return False
        
        # Set interrupt flag
        session.interrupt_requested = True
        session.interrupt_by = interrupter
        
        # Notify callbacks
        if current:
            self._notify_interrupt(session_id, interrupter, current)
        
        return True
    
    def judge_interrupt(self, session_id: str) -> bool:
        """
        Judge interrupts current speaker.
        
        Per AUDIO.md: Judge voice ALWAYS has priority.
        Always succeeds.
        """
        return self.request_interrupt(session_id, Role.JUDGE)
    
    # =========================================================================
    # PLAYBACK STATE
    # =========================================================================
    
    def is_playing(self, session_id: str) -> bool:
        """Check if audio is currently playing."""
        session = self._sessions.get(session_id)
        return session.is_playing if session else False
    
    def get_current_speaker(self, session_id: str) -> Optional[Role]:
        """Get current speaker role."""
        session = self._sessions.get(session_id)
        return session.current_speaker if session else None
    
    def get_segments(self, session_id: str) -> List[TTSSegment]:
        """Get all generated segments."""
        session = self._sessions.get(session_id)
        return session.segments if session else []


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_tts_service(client: Optional[OpenAI] = None) -> TTSService:
    """
    Create a new TTS service instance.
    
    Args:
        client: Optional OpenAI client for dependency injection
        
    Returns:
        TTSService instance
    """
    return TTSService(client=client)


# =============================================================================
# PERSONA HELPERS
# =============================================================================

def create_judge_persona(
    voice: OpenAIVoice = OpenAIVoice.ALLOY,
    speed: float = 1.1,
    authority: float = 0.4
) -> VoicePersona:
    """Create youthful voice persona for judge/scorer."""
    return VoicePersona(
        voice=voice,
        speed=speed,
        authority=authority,
        nervousness=0.0,
        warmth=0.5,
        priority=100,
    )


def create_attorney_persona(
    voice: OpenAIVoice = OpenAIVoice.ALLOY,
    speed: float = 1.15,
    authority: float = 0.3,
    warmth: float = 0.7
) -> VoicePersona:
    """Create youthful voice persona for attorney."""
    return VoicePersona(
        voice=voice,
        speed=speed,
        authority=authority,
        nervousness=0.0,
        warmth=warmth,
        priority=50,
    )


def create_witness_persona(
    voice: OpenAIVoice = OpenAIVoice.ALLOY,
    speed: float = 1.15,
    nervousness: float = 0.3,
    warmth: float = 0.7
) -> VoicePersona:
    """Create youthful voice persona for witness."""
    return VoicePersona(
        voice=voice,
        speed=speed,
        authority=0.1,
        nervousness=nervousness,
        warmth=warmth,
        priority=10,
    )


def create_coach_persona(
    voice: OpenAIVoice = OpenAIVoice.NOVA,
    speed: float = 1.1,
    warmth: float = 0.8
) -> VoicePersona:
    """Create youthful voice persona for coach."""
    return VoicePersona(
        voice=voice,
        speed=speed,
        authority=0.3,
        nervousness=0.0,
        warmth=warmth,
        priority=5,
    )
