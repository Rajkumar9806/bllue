"""
AI Provider System for Arrow API
Supports: Gemini, Claude (Anthropic), OpenAI GPT
"""

import os
import httpx
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Base class for AI providers"""

    @abstractmethod
    async def generate(self, prompt: str, temperature: float = 0.9, max_tokens: int = 2048) -> str:
        """Generate text response from AI provider

        Args:
            prompt: The prompt to send to the AI model
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response

        Returns:
            Raw text response from the model

        Raises:
            ValueError: If API key is not configured
            Exception: If API call fails
        """
        raise NotImplementedError


class GeminiProvider(AIProvider):
    """Google Gemini 2.0 Flash provider"""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        self.model = "gemini-2.0-flash"

    async def generate(self, prompt: str, temperature: float = 0.9, max_tokens: int = 2048) -> str:
        """Generate response using Gemini API"""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not configured")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_url}?key={self.api_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": temperature,
                            "topP": 0.95,
                            "maxOutputTokens": max_tokens
                        }
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                    raise Exception(f"Gemini API returned {response.status_code}")

                data = response.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

                if not text:
                    raise Exception("No text in Gemini response")

                return text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise


class ClaudeProvider(AIProvider):
    """Anthropic Claude provider"""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-sonnet-4-20250514"
        self.api_version = "2023-06-01"

    async def generate(self, prompt: str, temperature: float = 0.9, max_tokens: int = 2048) -> str:
        """Generate response using Claude API"""
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not configured")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": self.api_version,
                        "content-type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Claude API error: {response.status_code} - {response.text}")
                    raise Exception(f"Claude API returned {response.status_code}")

                data = response.json()

                # Extract text from response
                if "content" not in data or not data["content"]:
                    raise Exception("No content in Claude response")

                text = data["content"][0].get("text", "")

                if not text:
                    raise Exception("No text in Claude response")

                return text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o"

    async def generate(self, prompt: str, temperature: float = 0.9, max_tokens: int = 2048) -> str:
        """Generate response using OpenAI API"""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not configured")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                )

                if response.status_code != 200:
                    logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                    raise Exception(f"OpenAI API returned {response.status_code}")

                data = response.json()

                # Extract text from response
                if "choices" not in data or not data["choices"]:
                    raise Exception("No choices in OpenAI response")

                text = data["choices"][0].get("message", {}).get("content", "")

                if not text:
                    raise Exception("No text in OpenAI response")

                return text

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


def clean_response_text(text: str) -> str:
    """Clean AI response text by removing markdown code blocks"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def get_ai_provider(provider_name: str) -> AIProvider:
    """Factory function to get an AI provider instance

    Args:
        provider_name: Name of provider ('gemini', 'claude', 'openai')

    Returns:
        AIProvider instance

    Raises:
        ValueError: If provider is not recognized
    """
    provider_map = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
    }

    provider_class = provider_map.get(provider_name.lower())
    if not provider_class:
        logger.warning(f"Unknown provider '{provider_name}', defaulting to Gemini")
        provider_class = GeminiProvider

    return provider_class()


def get_available_providers() -> list[str]:
    """Get list of providers that have API keys configured

    Returns:
        List of available provider names
    """
    available = []

    if os.getenv("GEMINI_API_KEY"):
        available.append("gemini")
    if os.getenv("ANTHROPIC_API_KEY"):
        available.append("claude")
    if os.getenv("OPENAI_API_KEY"):
        available.append("openai")

    return available
