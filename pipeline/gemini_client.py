"""
Gemini API Client
Shared client used by both the Identifier (step 1) and Synthesizer (step 3).
"""

import json
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-pro"


class GeminiClient:
    """Simple wrapper around Gemini API."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def ask(self, prompt: str, temperature: float = 0.0, max_tokens: int = 8192) -> str:
        """
        Send a prompt to Gemini, get text back.
        """
        url = f"{GEMINI_API_URL}/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        response = requests.post(url, json=payload, timeout=90)

        # Log the actual HTTP status and error if it fails
        if response.status_code != 200:
            error_text = response.text[:500]
            logger.error(f"Gemini API error (HTTP {response.status_code}): {error_text}")
            # Try fallback model
            if self.model != "gemini-2.0-flash":
                logger.warning(f"Retrying with gemini-2.0-flash...")
                return self._ask_with_model("gemini-2.0-flash", prompt, temperature, max_tokens)
            raise ValueError(f"Gemini API error: HTTP {response.status_code}")

        data = response.json()

        # Check for blocked content or errors in response
        if "error" in data:
            logger.error(f"Gemini response error: {data['error']}")
            raise ValueError(f"Gemini error: {data['error'].get('message', 'Unknown')}")

        candidates = data.get("candidates", [])
        if not candidates:
            logger.error(f"No candidates in response. Full response: {json.dumps(data)[:500]}")
            # Try fallback
            if self.model != "gemini-2.0-flash":
                logger.warning(f"Retrying with gemini-2.0-flash...")
                return self._ask_with_model("gemini-2.0-flash", prompt, temperature, max_tokens)
            raise ValueError("Empty response from Gemini - no candidates")

        # Handle thinking models (2.5 Pro, 3 Pro) that may return thought + text parts
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            logger.error(f"No parts in candidate. Candidate: {json.dumps(candidates[0])[:500]}")
            raise ValueError("Empty response from Gemini - no parts")

        # Collect all text parts (skip thought parts)
        text_parts = []
        for part in parts:
            if "text" in part:
                # Some models return {"thought": true, "text": "..."} for thinking
                # We want the non-thought text
                if not part.get("thought", False):
                    text_parts.append(part["text"])

        # If all parts were thoughts, just use all text
        if not text_parts:
            text_parts = [p.get("text", "") for p in parts if "text" in p]

        result = "\n".join(text_parts).strip()
        if not result:
            raise ValueError("Empty text in Gemini response")

        return result

    def _ask_with_model(self, model: str, prompt: str, temperature: float, max_tokens: int) -> str:
        """Try a specific model as fallback."""
        url = f"{GEMINI_API_URL}/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text_parts = [p.get("text", "") for p in parts if "text" in p and not p.get("thought", False)]
            if not text_parts:
                text_parts = [p.get("text", "") for p in parts if "text" in p]
            result = "\n".join(text_parts).strip()
            if result:
                return result
        raise ValueError(f"Fallback model {model} also returned empty")
