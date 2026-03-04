"""
LLM Service Layer

Per ARCHITECTURE.md - LLM Access:
- API keys (OpenAI, Whisper, TTS) are stored only in backend environment variables
- Agents never hold API keys or call OpenAI directly
- Agents communicate with the LLM via local backend functions (e.g., call_llm(prompt, persona))
- All memory, persona, and prompt assembly is done in backend before calling LLM

Per AGENTS.md - Agent → LLM Communication:
- All agent calls to GPT-4.1 or TTS/Whisper go through backend service
- Agents send prompts to backend function call_llm
- Agents are unaware of API keys and cannot call LLM directly
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from ..utils.openai_client import OpenAIClient, get_openai_client

logger = logging.getLogger(__name__)


# =============================================================================
# LLM REQUEST/RESPONSE TYPES
# =============================================================================

@dataclass
class PersonaContext:
    """
    Persona parameters for LLM calls.
    
    Agents provide persona context; LLM service uses it to condition prompts.
    """
    role: str                      # attorney, witness, judge, coach
    name: str                      # Agent name
    style: Optional[str] = None    # e.g., aggressive, methodical
    authority: float = 0.5         # 0.0 to 1.0
    nervousness: float = 0.0       # 0.0 to 1.0
    formality: float = 0.8         # 0.0 to 1.0
    additional_traits: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_traits is None:
            self.additional_traits = {}


@dataclass
class LLMRequest:
    """
    Request from an agent to the LLM service.
    
    Agents construct this request; they do NOT have access to API keys or
    the underlying OpenAI client.
    """
    system_prompt: str
    user_prompt: str
    persona: PersonaContext
    conversation_history: List[Dict[str, str]] = None
    temperature: float = 0.7
    max_tokens: int = 500
    model: str = "gpt-4.1"
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []


@dataclass
class LLMResponse:
    """Response from the LLM service to an agent."""
    content: str
    model: str
    tokens_used: int = 0
    finish_reason: str = "stop"


# =============================================================================
# LLM SERVICE
# =============================================================================

_active_llm_overrides: Dict[str, Any] = {}


def set_llm_overrides(overrides: Dict[str, Any]) -> None:
    """Set session-level LLM config overrides (model, temperature, max_tokens)."""
    global _active_llm_overrides
    _active_llm_overrides = {k: v for k, v in overrides.items() if v is not None}


def get_llm_overrides() -> Dict[str, Any]:
    """Get current LLM config overrides."""
    return dict(_active_llm_overrides)


class LLMService:
    """
    Backend LLM Service.
    
    Per ARCHITECTURE.md:
    - API keys stored only in backend environment variables
    - Agents communicate via this service, not directly with OpenAI
    - All prompt assembly and persona conditioning happens here
    
    This service:
    1. Receives requests from agents (prompts + persona)
    2. Injects API keys and calls OpenAI
    3. Returns responses to agents
    
    Agents NEVER see API keys or make direct API calls.
    """
    
    def __init__(self):
        """
        Initialize LLM service.
        
        API key is retrieved from environment variables here,
        NOT passed in or accessible to agents.
        """
        self._client: Optional[OpenAIClient] = None
        self._initialized = False
    
    @property
    def client(self) -> OpenAIClient:
        """
        Lazy initialization of OpenAI client.
        
        API key is injected from environment here.
        """
        if self._client is None:
            # API key retrieved from environment, not from agents
            self._client = get_openai_client()
            self._initialized = True
            logger.info("LLM Service initialized with API key from environment")
        return self._client
    
    def call_llm(
        self,
        request: LLMRequest
    ) -> LLMResponse:
        """
        Process an LLM request from an agent.
        
        Per AGENTS.md workflow:
        1. Agent generates internal prompt (persona + context + memory)
        2. Sends prompt to this function
        3. This function injects API key and calls LLM
        4. Response is returned to agent
        
        Args:
            request: LLMRequest containing prompt and persona context
            
        Returns:
            LLMResponse with generated content
        """
        conditioned_system = self._apply_persona_conditioning(
            request.system_prompt,
            request.persona
        )

        overrides = _active_llm_overrides
        model = overrides.get("model", request.model)
        temperature = overrides.get("temperature", request.temperature)
        max_tokens = overrides.get("max_tokens", request.max_tokens)
        
        logger.debug(
            f"LLM call for {request.persona.role} '{request.persona.name}' "
            f"using model {model}"
        )

        messages = [{"role": "system", "content": conditioned_system}]
        if request.conversation_history:
            messages.extend(request.conversation_history[-10:])
        messages.append({"role": "user", "content": request.user_prompt})

        from .llm_providers import chat_completion as provider_chat, get_provider_for_model
        provider = get_provider_for_model(model)

        if provider == "openai":
            content = self.client.chat_completion_with_system(
                system_prompt=conditioned_system,
                user_prompt=request.user_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                conversation_history=request.conversation_history,
            )
        else:
            content = provider_chat(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens,
            )
        
        return LLMResponse(content=content, model=model)
    
    async def call_llm_async(
        self,
        request: LLMRequest
    ) -> LLMResponse:
        """Async version of call_llm for non-blocking operations."""
        conditioned_system = self._apply_persona_conditioning(
            request.system_prompt,
            request.persona
        )

        overrides = _active_llm_overrides
        model = overrides.get("model", request.model)
        temperature = overrides.get("temperature", request.temperature)
        max_tokens = overrides.get("max_tokens", request.max_tokens)

        messages = [{"role": "system", "content": conditioned_system}]
        if request.conversation_history:
            messages.extend(request.conversation_history[-10:])
        messages.append({"role": "user", "content": request.user_prompt})

        from .llm_providers import chat_completion_async as provider_chat_async, get_provider_for_model
        provider = get_provider_for_model(model)

        if provider == "openai":
            content = await self.client.chat_completion_with_system_async(
                system_prompt=conditioned_system,
                user_prompt=request.user_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                conversation_history=request.conversation_history,
            )
        else:
            content = await provider_chat_async(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens,
            )
        
        return LLMResponse(content=content, model=model)
    
    def _apply_persona_conditioning(
        self,
        system_prompt: str,
        persona: PersonaContext
    ) -> str:
        """
        Apply persona conditioning to the system prompt.
        
        Per ARCHITECTURE.md: All persona and prompt assembly done in backend.
        """
        # Build persona conditioning prefix
        persona_lines = [
            f"You are {persona.name}, acting as {persona.role}.",
        ]
        
        if persona.style:
            persona_lines.append(f"Your style is {persona.style}.")
        
        if persona.authority > 0.7:
            persona_lines.append("Speak with high authority and confidence.")
        elif persona.authority < 0.3:
            persona_lines.append("Speak with deference and caution.")
        
        if persona.nervousness > 0.7:
            persona_lines.append(
                "You are nervous. Include occasional hesitations, "
                "filler words like 'um' or 'uh', and shorter responses."
            )
        elif persona.nervousness > 0.4:
            persona_lines.append(
                "You are slightly nervous. Occasionally hesitate or pause."
            )
        
        if persona.formality > 0.7:
            persona_lines.append("Use formal, professional language.")
        elif persona.formality < 0.3:
            persona_lines.append("Use casual, conversational language.")
        
        # Add any additional traits
        for trait, value in persona.additional_traits.items():
            if isinstance(value, bool) and value:
                persona_lines.append(f"Exhibit {trait}.")
            elif isinstance(value, str):
                persona_lines.append(f"{trait}: {value}")
        
        persona_prefix = "\n".join(persona_lines)
        
        return f"{persona_prefix}\n\n{system_prompt}"


# =============================================================================
# SINGLETON SERVICE INSTANCE
# =============================================================================

_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get the singleton LLM service instance.
    
    Per ARCHITECTURE.md: Agents use this function to access LLM,
    never creating their own OpenAI clients.
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def call_llm(
    system_prompt: str,
    user_prompt: str,
    persona: PersonaContext,
    conversation_history: List[Dict[str, str]] = None,
    temperature: float = 0.7,
    max_tokens: int = 500,
    model: str = "gpt-4.1"
) -> str:
    """
    Convenience function for agents to call LLM.
    
    Per AGENTS.md: Agents send prompts to this function (call_llm).
    Agents are unaware of API keys and cannot call LLM directly.
    
    Args:
        system_prompt: System instructions
        user_prompt: User/context prompt
        persona: PersonaContext with role parameters
        conversation_history: Optional conversation history
        temperature: LLM temperature (0.0-2.0)
        max_tokens: Maximum response tokens
        model: Model to use (default: gpt-4.1)
        
    Returns:
        Generated text content
    """
    service = get_llm_service()
    
    request = LLMRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        persona=persona,
        conversation_history=conversation_history or [],
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    
    response = service.call_llm(request)
    return response.content


async def call_llm_async(
    system_prompt: str,
    user_prompt: str,
    persona: PersonaContext,
    conversation_history: List[Dict[str, str]] = None,
    temperature: float = 0.7,
    max_tokens: int = 500,
    model: str = "gpt-4.1"
) -> str:
    """
    Async convenience function for agents to call LLM.
    """
    service = get_llm_service()
    
    request = LLMRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        persona=persona,
        conversation_history=conversation_history or [],
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    
    response = await service.call_llm_async(request)
    return response.content
