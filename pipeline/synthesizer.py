"""
Synthesizer (Step 3)
Takes the real fetched data from legal databases and uses Gemini
to produce the final answer: TLDR, Key Cases, Answer, Gaps.
"""

import re
import logging

logger = logging.getLogger(__name__)


class Synthesizer:
    """Uses Gemini to synthesize fetched legal data into a clear answer."""

    def __init__(self, gemini_client):
        self.gemini = gemini_client

    def synthesize(self, question: str, fetched_data: dict) -> dict:
        """
        Take fetched case law and statutes and produce a clear answer.

        Returns:
            {
                "tldr": str,
                "key_cases": str,
                "answer": str,
                "gaps": str
            }
        """
        cases_text = self._format_cases(fetched_data.get("cases", []))
        statutes_text = self._format_statutes(fetched_data.get("statutes", []))

        missing_statutes = self._missing_statutes_text(fetched_data)

        prompt = f"""You are a legal research expert. I searched legal databases and found the case law and statutes below. Use this data to answer the user's question.

CRITICAL RULES:
- ONLY cite cases from the data below. Never invent or hallucinate cases.
- List ALL cases from the data below — they were already filtered for relevance. Do not skip any.
- For statutes: If real statute data was retrieved below, cite it normally. If statutes were identified as relevant but NOT found in the database, you may explain them from your own knowledge BUT you MUST clearly label those as "⚠️ Gemini Interpretation — not sourced from database."
- Be direct. No filler. Answer like a sharp legal expert.
- Include CourtListener links where available.

USER'S QUESTION:
{question}

CASE LAW FOUND:
{cases_text if cases_text else "No cases were found in the databases."}

STATUTES FOUND IN DATABASE:
{statutes_text if statutes_text else "No relevant statutes found in database."}

STATUTES IDENTIFIED BUT NOT FOUND IN DATABASE:
{missing_statutes if missing_statutes else "None."}

Now produce EXACTLY these five sections. Use these EXACT headers:

## TLDR
2-3 sentences that directly answer the question. Be specific about what the law says. No hedging.

## KEY CASES
List ALL cases from the retrieved data (do not skip any). For each:

**Case Name**, Citation (Year)
- HOLDING: What the court decided in one sentence.
- KEY FACTS: The facts that mattered, 1-2 sentences.
- WHY IT MATTERS: Why this case matters for the user's question.
- LINK: [CourtListener link if available from the data]

## RELEVANT STATUTES
For statutes found in the database, summarize them with proper citations. For statutes identified as relevant but NOT found in database, explain them and prefix each with: ⚠️ Gemini Interpretation — not sourced from database

## ANSWER
2-4 paragraphs connecting the cases and statutes to answer the question. Explain how the legal standard works in practice. Give concrete examples of what would and wouldn't meet the standard. If courts disagree, explain the split.

## GAPS
2-3 bullet points on what's missing from this analysis and what additional research would help."""

        try:
            response = self.gemini.ask(prompt, temperature=0.0, max_tokens=8192)
            return self._parse(response)
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return {
                "tldr": f"Error generating synthesis: {e}",
                "key_cases": cases_text,
                "answer": "",
                "gaps": ""
            }

    def _parse(self, text: str) -> dict:
        """Parse Gemini's response into sections."""
        sections = {"tldr": "", "key_cases": "", "statutes": "", "answer": "", "gaps": ""}

        markers = [
            ("TLDR", "tldr"),
            ("KEY CASES", "key_cases"),
            ("RELEVANT STATUTES", "statutes"),
            ("ANSWER", "answer"),
            ("GAPS", "gaps"),
        ]

        current_key = None
        current_lines = []

        for line in text.split("\n"):
            stripped = line.strip().lstrip("#").strip()
            stripped_upper = stripped.upper()

            matched = False
            for keyword, key in markers:
                if stripped_upper.startswith(keyword):
                    if current_key:
                        sections[current_key] = "\n".join(current_lines).strip()
                    current_key = key
                    current_lines = []
                    matched = True
                    break

            if not matched and current_key:
                current_lines.append(line)

        if current_key:
            sections[current_key] = "\n".join(current_lines).strip()

        # Fallback
        if not any(sections.values()):
            sections["answer"] = text

        return sections

    def _format_cases(self, cases: list) -> str:
        if not cases:
            return ""

        lines = []
        for i, case in enumerate(cases, 1):
            name = case.get("case_name", "Unknown")
            citation = case.get("citation", "No citation")
            date = case.get("date_filed", "")
            court = case.get("court", "")
            snippet = case.get("snippet", case.get("topic", ""))
            url = case.get("absolute_url", "")
            is_landmark = case.get("is_landmark", False)

            if snippet:
                snippet = re.sub(r'<[^>]+>', '', snippet)
                snippet = snippet.replace("&amp;", "&")[:800]

            entry = f"Case {i}: {name}"
            entry += f"\n  Citation: {citation}"
            if court:
                entry += f"\n  Court: {court}"
            if date:
                entry += f"\n  Date: {date}"
            if is_landmark:
                entry += f"\n  [LANDMARK CASE]"
            if url:
                entry += f"\n  CourtListener URL: https://www.courtlistener.com{url}"
            if snippet:
                entry += f"\n  Excerpt/Topic: {snippet}"
            lines.append(entry + "\n")

        return "\n".join(lines)

    def _format_statutes(self, statutes: list) -> str:
        if not statutes:
            return ""

        lines = []
        for i, s in enumerate(statutes, 1):
            title = s.get("title", "Unknown")
            number = s.get("number", "")
            policy = s.get("policy_area", "")

            entry = f"Statute {i}: {title}"
            if number:
                entry += f" ({number})"
            if policy:
                entry += f"\n  Policy Area: {policy}"
            lines.append(entry)

        return "\n".join(lines)

    def _missing_statutes_text(self, data: dict) -> str:
        """List statutes that were identified but not found in database."""
        identified = data.get("identified_statutes", [])
        found = data.get("statutes", [])

        if not identified:
            return ""

        # Get titles of found statutes
        found_titles = set()
        for s in found:
            found_titles.add(s.get("title", "").lower())

        # List the ones not found
        missing = []
        for name in identified:
            name_lower = name.lower()
            was_found = any(name_lower in t or t in name_lower for t in found_titles)
            if not was_found:
                missing.append(name)

        if missing:
            return "\n".join(f"- {name}" for name in missing)
        return ""
