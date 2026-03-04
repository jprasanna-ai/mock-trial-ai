"""
Audio Streaming Endpoints

Per ARCHITECTURE.md:
- User: Mic → WebRTC → Whisper → Text
- AI: Text → GPT-4.1 → Persona Conditioning → TTS → WebRTC → Speaker
- All audio must be streamed (no blocking)

Per AUDIO.md:
- Audio is primary interface
- Judge voice ALWAYS has priority
- Interrupted audio must stop immediately
"""

from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..graph.trial_graph import (
    Role,
    validate_speaker,
    TESTIMONY_STATES,
)
from ..services import (
    TranscriptionSegment,
    TranscriptionStatus,
)
from .session import get_session, _sessions


router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class TTSRequest(BaseModel):
    """Request to generate TTS audio."""
    text: str
    role: str


class TTSResponse(BaseModel):
    """Response with TTS status."""
    session_id: str
    segment_id: str
    text: str
    role: str
    duration: float


class InterruptRequest(BaseModel):
    """Request to interrupt current audio."""
    interrupter_role: str


class InterruptResponse(BaseModel):
    """Response for interrupt request."""
    success: bool
    interrupter: str
    interrupted: Optional[str]
    message: str


# =============================================================================
# WEBSOCKET: MIC AUDIO → WHISPER
# =============================================================================

@router.websocket("/{session_id}/mic")
async def mic_audio_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming mic audio to Whisper.
    
    Per ARCHITECTURE.md: Mic → WebRTC → Whisper → Text
    Per AUDIO.md: Streaming transcription only, verbatim capture.
    
    Protocol:
    - Client sends binary PCM audio chunks (16kHz, mono, 16-bit)
    - Server sends JSON transcription segments back
    
    Messages from server:
    - {"type": "transcription", "text": "...", "start_time": 0.0, ...}
    - {"type": "error", "message": "..."}
    - {"type": "permission_denied", "reason": "..."}
    """
    await websocket.accept()
    
    # Get session
    if session_id not in _sessions:
        await websocket.send_json({
            "type": "error",
            "message": "Session not found"
        })
        await websocket.close()
        return
    
    session = _sessions[session_id]
    
    if not session.whisper:
        await websocket.send_json({
            "type": "error",
            "message": "Whisper service not initialized"
        })
        await websocket.close()
        return
    
    # Create whisper session
    whisper_session = session.whisper.create_session(
        session_id=f"{session_id}_mic",
        current_speaker=session.human_role
    )
    
    timestamp = 0.0
    
    try:
        while True:
            # Receive audio data
            data = await websocket.receive_bytes()
            
            if not data:
                continue
            
            # Validate speaker permission before processing
            if session.human_role:
                valid, reason = validate_speaker(session.trial_state, session.human_role)
                if not valid:
                    await websocket.send_json({
                        "type": "permission_denied",
                        "reason": reason
                    })
                    continue
            
            # Calculate chunk duration
            chunk_duration = session.whisper._calculate_duration_ms(data) / 1000.0
            
            # Process audio chunk
            segment = await session.whisper.process_audio_chunk(
                f"{session_id}_mic",
                data,
                timestamp
            )
            
            # Send transcription if available
            if segment and segment.status == TranscriptionStatus.FINAL:
                await websocket.send_json({
                    "type": "transcription",
                    "text": segment.text,
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                    "segment_id": segment.segment_id,
                    "contains_filler": segment.contains_filler,
                    "speaker_role": segment.speaker_role.value if segment.speaker_role else None,
                    "is_final": True,
                })
                
                # Add to trial transcript
                if segment.text:
                    session.trial_state.transcript.append({
                        "role": session.human_role.value if session.human_role else "unknown",
                        "text": segment.text,
                        "audio_timestamp": segment.start_time,
                        "phase": session.trial_state.phase.value,
                    })
            
            # Send interim (partial) transcriptions for real-time feedback
            elif segment and segment.status == TranscriptionStatus.PARTIAL:
                await websocket.send_json({
                    "type": "transcription",
                    "text": segment.text,
                    "start_time": segment.start_time,
                    "segment_id": segment.segment_id,
                    "is_final": False,
                })
            
            elif segment and segment.status == TranscriptionStatus.SILENCE:
                await websocket.send_json({
                    "type": "silence",
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                })
            
            timestamp += chunk_duration
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception:
            pass
    finally:
        # Process remaining buffer
        final_segment = await session.whisper.force_process(f"{session_id}_mic")
        
        if final_segment and final_segment.status == TranscriptionStatus.FINAL:
            try:
                await websocket.send_json({
                    "type": "transcription",
                    "text": final_segment.text,
                    "start_time": final_segment.start_time,
                    "end_time": final_segment.end_time,
                    "segment_id": final_segment.segment_id,
                    "final": True,
                })
            except Exception:
                pass
        
        # End whisper session
        session.whisper.end_session(f"{session_id}_mic")


# =============================================================================
# WEBSOCKET: TTS AUDIO STREAMING
# =============================================================================

@router.websocket("/{session_id}/speaker")
async def tts_audio_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming TTS audio to frontend.
    
    Per ARCHITECTURE.md: TTS → WebRTC → Speaker
    Per AUDIO.md: Judge voice ALWAYS has priority.
    
    Protocol:
    - Client sends JSON requests: {"action": "speak", "text": "...", "role": "..."}
    - Client sends JSON requests: {"action": "interrupt", "role": "..."}
    - Server sends binary audio chunks
    - Server sends JSON control messages
    
    Control messages from server:
    - {"type": "start", "role": "...", "text": "..."}
    - {"type": "end", "role": "...", "segment_id": "..."}
    - {"type": "interrupted", "by": "...", "was_speaking": "..."}
    - {"type": "error", "message": "..."}
    """
    await websocket.accept()
    
    # Get session
    if session_id not in _sessions:
        await websocket.send_json({
            "type": "error",
            "message": "Session not found"
        })
        await websocket.close()
        return
    
    session = _sessions[session_id]
    
    if not session.tts:
        await websocket.send_json({
            "type": "error",
            "message": "TTS service not initialized"
        })
        await websocket.close()
        return
    
    # Ensure TTS session exists
    if not session.tts.get_session(session_id):
        session.tts.create_session(session_id)
    
    try:
        while True:
            # Receive request
            message = await websocket.receive_json()
            action = message.get("action")
            
            if action == "speak":
                text = message.get("text", "")
                role_str = message.get("role", "")
                
                if not text or not role_str:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Missing text or role"
                    })
                    continue
                
                # Parse role
                try:
                    role = Role(role_str)
                except ValueError:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Invalid role: {role_str}"
                    })
                    continue
                
                # Validate speaker permission
                valid, reason = validate_speaker(session.trial_state, role)
                if not valid:
                    await websocket.send_json({
                        "type": "permission_denied",
                        "role": role_str,
                        "reason": reason
                    })
                    continue
                
                # Send start notification
                await websocket.send_json({
                    "type": "start",
                    "role": role_str,
                    "text": text
                })
                
                # Stream TTS audio
                segment_id = f"{session_id}_{len(session.tts.get_segments(session_id))}"
                
                async for chunk in session.tts.stream_speech(session_id, text, role):
                    await websocket.send_bytes(chunk)
                
                # Send end notification
                await websocket.send_json({
                    "type": "end",
                    "role": role_str,
                    "segment_id": segment_id
                })
                
                # Add to trial transcript
                session.trial_state.transcript.append({
                    "role": role_str,
                    "text": text,
                    "audio_timestamp": session.trial_state.transcript[-1]["audio_timestamp"] + 1 if session.trial_state.transcript else 0,
                    "phase": session.trial_state.phase.value,
                })
            
            elif action == "interrupt":
                interrupter_str = message.get("role", "")
                
                try:
                    interrupter = Role(interrupter_str)
                except ValueError:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Invalid role: {interrupter_str}"
                    })
                    continue
                
                current_speaker = session.tts.get_current_speaker(session_id)
                
                success = session.tts.request_interrupt(session_id, interrupter)
                
                await websocket.send_json({
                    "type": "interrupted" if success else "interrupt_denied",
                    "by": interrupter_str,
                    "was_speaking": current_speaker.value if current_speaker else None,
                    "success": success
                })
            
            elif action == "judge_interrupt":
                # Judge can always interrupt
                current_speaker = session.tts.get_current_speaker(session_id)
                session.tts.judge_interrupt(session_id)
                
                await websocket.send_json({
                    "type": "interrupted",
                    "by": "judge",
                    "was_speaking": current_speaker.value if current_speaker else None,
                    "success": True
                })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: {action}"
                })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception:
            pass


# =============================================================================
# HTTP ENDPOINTS
# =============================================================================

@router.post("/{session_id}/tts", response_model=TTSResponse)
async def generate_tts(session_id: str, request: TTSRequest):
    """
    Generate TTS audio (non-streaming).
    
    Returns audio as streaming response.
    Use WebSocket endpoint for real-time streaming.
    """
    session = get_session(session_id)
    
    if not session.tts:
        raise HTTPException(status_code=400, detail="TTS service not initialized")
    
    # Parse role
    try:
        role = Role(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")
    
    # Validate speaker permission
    valid, reason = validate_speaker(session.trial_state, role)
    if not valid:
        raise HTTPException(status_code=403, detail=reason)
    
    # Ensure TTS session exists
    if not session.tts.get_session(session_id):
        session.tts.create_session(session_id)
    
    # Generate audio
    segment = await session.tts.generate_speech(session_id, request.text, role)
    
    if not segment:
        raise HTTPException(status_code=500, detail="Failed to generate audio")
    
    return TTSResponse(
        session_id=session_id,
        segment_id=segment.segment_id,
        text=request.text,
        role=role.value,
        duration=segment.duration
    )


@router.get("/{session_id}/tts/{segment_id}/audio")
async def get_tts_audio(session_id: str, segment_id: str):
    """
    Get generated TTS audio by segment ID.
    
    Returns audio as streaming response.
    """
    session = get_session(session_id)
    
    if not session.tts:
        raise HTTPException(status_code=400, detail="TTS service not initialized")
    
    # Find segment
    segments = session.tts.get_segments(session_id)
    segment = next((s for s in segments if s.segment_id == segment_id), None)
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    # Return audio as streaming response
    async def audio_generator():
        yield segment.audio_data
    
    return StreamingResponse(
        audio_generator(),
        media_type="audio/opus"
    )


@router.post("/{session_id}/interrupt", response_model=InterruptResponse)
async def interrupt_audio(session_id: str, request: InterruptRequest):
    """
    Request to interrupt current audio playback.
    
    Per AUDIO.md:
    - Judges may interrupt any speaker
    - Objections may interrupt testimony
    - Interrupted audio must stop immediately
    """
    session = get_session(session_id)
    
    if not session.tts:
        raise HTTPException(status_code=400, detail="TTS service not initialized")
    
    # Parse role
    try:
        interrupter = Role(request.interrupter_role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.interrupter_role}")
    
    current_speaker = session.tts.get_current_speaker(session_id)
    
    # Request interrupt
    success = session.tts.request_interrupt(session_id, interrupter)
    
    return InterruptResponse(
        success=success,
        interrupter=interrupter.value,
        interrupted=current_speaker.value if current_speaker else None,
        message="Interrupt successful" if success else "Interrupt denied - insufficient priority"
    )


@router.post("/{session_id}/judge-interrupt", response_model=InterruptResponse)
async def judge_interrupt(session_id: str):
    """
    Judge interrupts current speaker.
    
    Per AUDIO.md: Judge voice ALWAYS has priority.
    Always succeeds.
    """
    session = get_session(session_id)
    
    if not session.tts:
        raise HTTPException(status_code=400, detail="TTS service not initialized")
    
    current_speaker = session.tts.get_current_speaker(session_id)
    
    # Judge interrupt always succeeds
    session.tts.judge_interrupt(session_id)
    
    return InterruptResponse(
        success=True,
        interrupter=Role.JUDGE.value,
        interrupted=current_speaker.value if current_speaker else None,
        message="Judge interrupt - all speakers must yield"
    )


@router.get("/{session_id}/playback-status")
async def get_playback_status(session_id: str):
    """Get current audio playback status."""
    session = get_session(session_id)
    
    if not session.tts:
        raise HTTPException(status_code=400, detail="TTS service not initialized")
    
    return {
        "session_id": session_id,
        "is_playing": session.tts.is_playing(session_id),
        "current_speaker": session.tts.get_current_speaker(session_id).value if session.tts.get_current_speaker(session_id) else None,
        "segments_count": len(session.tts.get_segments(session_id))
    }


@router.get("/{session_id}/transcription")
async def get_transcription(session_id: str):
    """Get current Whisper transcription."""
    session = get_session(session_id)
    
    if not session.whisper:
        raise HTTPException(status_code=400, detail="Whisper service not initialized")
    
    transcript = session.whisper.get_transcript(f"{session_id}_mic")
    segments = session.whisper.get_segments(f"{session_id}_mic")
    
    return {
        "session_id": session_id,
        "full_transcript": transcript,
        "segment_count": len(segments),
        "segments": [
            {
                "text": s.text,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "status": s.status.value,
            }
            for s in segments[-20:]  # Last 20 segments
        ]
    }
