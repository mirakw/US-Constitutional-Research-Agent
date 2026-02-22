"""
Case Identifier (Step 1)
Uses Gemini to identify which specific cases, statutes, and legal
concepts are relevant to the user's question BEFORE we search any database.
"""

import json
import re
import logging

logger = logging.getLogger(__name__)


class CaseIdentifier:
    """Uses Gemini to identify what to search for."""

    def __init__(self, gemini_client):
        self.gemini = gemini_client

    def identify(self, question: str) -> dict:
        """
        Ask Gemini: for this legal question, what specific cases and
        statutes should we look up?

        Returns:
            {
                "cases": ["Harlow v. Fitzgerald", "Pearson v. Callahan", ...],
                "statutes": ["42 U.S.C. § 1983", ...],
                "search_queries": ["qualified immunity excessive force", ...]
            }
        """
        prompt = f"""You are a legal research expert. A user has a legal question and I need to search legal databases to find relevant cases and statutes.

For this question, tell me:
1. The specific court cases (by name) that are most important and relevant
2. Any specific federal statutes that apply
3. Good search queries I should use to find additional relevant cases in a legal database

USER'S QUESTION:
{question}

Respond in EXACTLY this JSON format and nothing else — no markdown, no backticks, no explanation:
{{
    "cases": ["Case Name v. Other Party", "Another Case v. State"],
    "statutes": ["42 U.S.C. § 1983", "Title VII of the Civil Rights Act"],
    "search_queries": ["qualified immunity excessive force", "clearly established right"]
}}

List 5-10 of the most important cases. List any relevant statutes (empty list if none apply). List 2-3 search queries."""

        try:
            response = self.gemini.ask(prompt, temperature=0.0, max_tokens=2048)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"Identifier error: {e}")
            return self._fallback(question)

    def _parse_response(self, text: str) -> dict:
        """Parse Gemini's JSON response."""
        # Strip markdown code fences if present
        text = text.strip()
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        try:
            data = json.loads(text)
            return {
                "cases": data.get("cases", []),
                "statutes": data.get("statutes", []),
                "search_queries": data.get("search_queries", []),
            }
        except json.JSONDecodeError:
            logger.warning(f"Could not parse Gemini JSON: {text[:200]}")
            # Try to extract case names from plain text
            return self._extract_from_text(text)

    def _extract_from_text(self, text: str) -> dict:
        """Fallback: extract case names from plain text using v. pattern."""
        cases = []
        # Match patterns like "Something v. Something"
        pattern = r'([A-Z][a-zA-Z\s\.\',]+\s+v\.\s+[A-Z][a-zA-Z\s\.\',]+)'
        matches = re.findall(pattern, text)
        for match in matches:
            name = match.strip().rstrip(",.")
            if len(name) > 5 and name not in cases:
                cases.append(name)

        return {
            "cases": cases[:10],
            "statutes": [],
            "search_queries": [],
        }

    def _fallback(self, question: str) -> dict:
        """If Gemini fails entirely, generate basic search queries."""
        words = question.lower().split()
        stop = {"what", "how", "is", "the", "in", "for", "has", "been", "are",
                "does", "do", "can", "a", "an", "of", "to", "and", "or"}
        terms = [w.strip("?.,!") for w in words if w not in stop and len(w) > 3]

        return {
            "cases": [],
            "statutes": [],
            "search_queries": [" ".join(terms[:5])],
        }
