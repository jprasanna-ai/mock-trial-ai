"""
OpenAI Client Wrapper with Retry Logic

Provides a centralized OpenAI client with:
- Automatic retry on rate limits and transient errors
- Exponential backoff
- Client injection for testing
- Consistent error handling
"""

import asyncio
import os
import time
from typing import Optional, Dict, Any, List, Callable, TypeVar, Union
from dataclasses import dataclass
from functools import wraps
import logging

from openai import OpenAI, AsyncOpenAI
from openai import (
    APIError as OpenAIAPIError,
    RateLimitError as OpenAIRateLimitError,
    APIConnectionError,
    APITimeoutError,
)

logger = logging.getLogger(__name__)

# Type variable for generic retry decorator
T = TypeVar("T")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class OpenAIError(Exception):
    """Base exception for OpenAI client errors."""
    pass


class RateLimitError(OpenAIError):
    """Rate limit exceeded, even after retries."""
    pass


class APIError(OpenAIError):
    """API error that could not be recovered."""
    pass


# =============================================================================
# RETRY CONFIGURATION
# =============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0     # seconds
    exponential_base: float = 2.0
    jitter: bool = True         # Add randomness to prevent thundering herd
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return delay


DEFAULT_RETRY_CONFIG = RetryConfig()


# =============================================================================
# RETRY DECORATOR
# =============================================================================

def with_retry(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (
        OpenAIRateLimitError,
        APIConnectionError,
        APITimeoutError,
    )
):
    """
    Decorator that adds retry logic to a function.
    
    Args:
        config: Retry configuration (uses default if not provided)
        retryable_exceptions: Tuple of exceptions that should trigger a retry
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_retries + 1} attempts failed. "
                            f"Last error: {e}"
                        )
                except OpenAIAPIError as e:
                    # Non-retryable API errors
                    logger.error(f"OpenAI API error (non-retryable): {e}")
                    raise APIError(str(e)) from e
            
            # If we get here, all retries exhausted
            if isinstance(last_exception, OpenAIRateLimitError):
                raise RateLimitError(
                    f"Rate limit exceeded after {config.max_retries + 1} attempts"
                ) from last_exception
            raise APIError(str(last_exception)) from last_exception
        
        return wrapper
    return decorator


def with_retry_async(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (
        OpenAIRateLimitError,
        APIConnectionError,
        APITimeoutError,
    )
):
    """
    Async version of retry decorator.
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_retries + 1} attempts failed. "
                            f"Last error: {e}"
                        )
                except OpenAIAPIError as e:
                    logger.error(f"OpenAI API error (non-retryable): {e}")
                    raise APIError(str(e)) from e
            
            if isinstance(last_exception, OpenAIRateLimitError):
                raise RateLimitError(
                    f"Rate limit exceeded after {config.max_retries + 1} attempts"
                ) from last_exception
            raise APIError(str(last_exception)) from last_exception
        
        return wrapper
    return decorator


# =============================================================================
# OPENAI CLIENT WRAPPER
# =============================================================================

class OpenAIClient:
    """
    Wrapper around OpenAI client with retry logic and testing support.
    
    Features:
    - Automatic retry with exponential backoff
    - Client injection for testing
    - Consistent error handling
    - Logging
    """
    
    DEFAULT_MODEL = "gpt-4.1"
    
    def __init__(
        self,
        client: Optional[OpenAI] = None,
        async_client: Optional[AsyncOpenAI] = None,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        """
        Initialize OpenAI client wrapper.
        
        Args:
            client: Injected OpenAI client (for testing)
            async_client: Injected async OpenAI client (for testing)
            api_key: API key (uses env var if not provided)
            retry_config: Configuration for retry behavior
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._retry_config = retry_config or DEFAULT_RETRY_CONFIG
        
        # Allow client injection for testing
        self._client = client
        self._async_client = async_client
    
    @property
    def client(self) -> OpenAI:
        """Get or create sync OpenAI client."""
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key)
        return self._client
    
    @property
    def async_client(self) -> AsyncOpenAI:
        """Get or create async OpenAI client."""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(api_key=self._api_key)
        return self._async_client
    
    # =========================================================================
    # CHAT COMPLETIONS
    # =========================================================================
    
    @with_retry()
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """
        Generate chat completion with retry logic.
        
        Args:
            messages: List of message dicts with role and content
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional arguments passed to OpenAI
            
        Returns:
            Generated text content
        """
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        return response.choices[0].message.content.strip()
    
    @with_retry_async()
    async def chat_completion_async(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """
        Async version of chat completion with retry logic.
        """
        response = await self.async_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        return response.choices[0].message.content.strip()
    
    def chat_completion_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 500,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> str:
        """
        Convenience method for system + user prompt pattern.
        
        Args:
            system_prompt: System message defining behavior
            user_prompt: User message with the request
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            conversation_history: Optional prior conversation context
            **kwargs: Additional OpenAI arguments
            
        Returns:
            Generated text content
        """
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        if conversation_history:
            # Include last N messages for context
            messages.extend(conversation_history[-10:])
        
        messages.append({"role": "user", "content": user_prompt})
        
        return self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    async def chat_completion_with_system_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 500,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> str:
        """
        Async version of chat_completion_with_system.
        """
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        if conversation_history:
            messages.extend(conversation_history[-10:])
        
        messages.append({"role": "user", "content": user_prompt})
        
        return await self.chat_completion_async(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    # =========================================================================
    # EMBEDDINGS
    # =========================================================================
    
    @with_retry()
    def create_embedding(
        self,
        text: str,
        model: str = "text-embedding-ada-002"
    ) -> List[float]:
        """
        Create text embedding with retry logic.
        
        Args:
            text: Text to embed
            model: Embedding model to use
            
        Returns:
            List of embedding floats
        """
        response = self.client.embeddings.create(
            model=model,
            input=text
        )
        
        return response.data[0].embedding
    
    @with_retry_async()
    async def create_embedding_async(
        self,
        text: str,
        model: str = "text-embedding-ada-002"
    ) -> List[float]:
        """
        Async version of create_embedding.
        """
        response = await self.async_client.embeddings.create(
            model=model,
            input=text
        )
        
        return response.data[0].embedding
    
    # =========================================================================
    # TTS
    # =========================================================================
    
    @with_retry()
    def create_speech(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1",
        speed: float = 1.0,
    ) -> bytes:
        """
        Create speech from text with retry logic.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use
            model: TTS model
            speed: Speech speed
            
        Returns:
            Audio bytes
        """
        response = self.client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed,
        )
        
        return response.content
    
    # =========================================================================
    # TRANSCRIPTION (Whisper)
    # =========================================================================
    
    @with_retry()
    def transcribe(
        self,
        audio_file,
        model: str = "whisper-1",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> str:
        """
        Transcribe audio with retry logic.
        
        Args:
            audio_file: Audio file object
            model: Whisper model
            language: Optional language hint
            prompt: Optional prompt for context
            
        Returns:
            Transcribed text
        """
        kwargs = {
            "model": model,
            "file": audio_file,
        }
        
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["prompt"] = prompt
        
        response = self.client.audio.transcriptions.create(**kwargs)
        
        return response.text


# =============================================================================
# SINGLETON / FACTORY
# =============================================================================

_default_client: Optional[OpenAIClient] = None


def get_openai_client() -> OpenAIClient:
    """
    Get the default OpenAI client singleton.
    
    Creates a new client if one doesn't exist.
    """
    global _default_client
    
    if _default_client is None:
        _default_client = OpenAIClient()
    
    return _default_client


def create_openai_client(
    client: Optional[OpenAI] = None,
    async_client: Optional[AsyncOpenAI] = None,
    api_key: Optional[str] = None,
    retry_config: Optional[RetryConfig] = None,
) -> OpenAIClient:
    """
    Create a new OpenAI client wrapper.
    
    Use this for testing with mocked clients.
    
    Args:
        client: Injected sync client
        async_client: Injected async client
        api_key: API key
        retry_config: Retry configuration
        
    Returns:
        New OpenAIClient instance
    """
    return OpenAIClient(
        client=client,
        async_client=async_client,
        api_key=api_key,
        retry_config=retry_config,
    )


def set_default_client(client: OpenAIClient) -> None:
    """
    Set the default OpenAI client.
    
    Useful for testing to inject a mock client.
    """
    global _default_client
    _default_client = client


def reset_default_client() -> None:
    """
    Reset the default client to None.
    
    Next call to get_openai_client() will create a new one.
    """
    global _default_client
    _default_client = None
