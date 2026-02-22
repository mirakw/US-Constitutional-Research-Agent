"""
Constitutional Law Research Agent — Terminal Version
Two-pass pipeline:
  1. Gemini identifies which cases/statutes matter for your question
  2. CourtListener + SCOTUS + Congress.gov fetch the real data
  3. Gemini synthesizes everything into a clear answer

Usage: python main.py
"""

import os
import re
import sys
import json
import textwrap
import logging
from datetime import datetime
from dotenv import load_dotenv

from sources.courtlistener import CourtListenerClient
from sources.congress import CongressGovClient
from sources.scotus import SCOTUSClient
from pipeline.gemini_client import GeminiClient
from pipeline.identifier import CaseIdentifier
from pipeline.fetcher import CaseFetcher
from pipeline.synthesizer import Synthesizer

load_dotenv()
logging.basicConfig(level=logging.WARNING)

# ── Colors ──────────────────────────────────────────────────────────
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
LINE = "─" * 70
OUTPUT_DIR = "output"


def _slug(s: str, max_len: int = 40) -> str:
    """Short sanitized string for use in filenames."""
    s = re.sub(r"[^\w\s-]", "", s)[:max_len].strip()
    return re.sub(r"[-\s]+", "_", s) or "research"


def save_result(question: str, result: dict) -> str:
    """Save question and result to a new JSON file in OUTPUT_DIR. Returns path.
    Structure matches terminal output: question, timestamp, tldr, key_cases, statutes, answer, gaps.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    slug = _slug(question)
    filename = f"{timestamp}_{slug}.json"
    path = os.path.join(OUTPUT_DIR, filename)
    payload = {
        "question": question,
        "timestamp": datetime.now().isoformat(),
        "tldr": result.get("tldr", ""),
        "key_cases": result.get("key_cases", ""),
        "statutes": result.get("statutes", ""),
        "answer": result.get("answer", ""),
        "gaps": result.get("gaps", ""),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def wrap(text, indent=2):
    lines = text.split("\n")
    result = []
    for line in lines:
        if line.strip():
            wrapped = textwrap.fill(line.strip(), width=68,
                                    initial_indent=" " * indent,
                                    subsequent_indent=" " * indent)
            result.append(wrapped)
        else:
            result.append("")
    return "\n".join(result)


def main():
    # Initialize everything
    gemini = GeminiClient(api_key=os.getenv("GEMINI_API_KEY"))
    cl_client = CourtListenerClient(api_token=os.getenv("COURTLISTENER_API_TOKEN"))
    congress_client = CongressGovClient(api_key=os.getenv("CONGRESS_API_KEY"))
    scotus_client = SCOTUSClient()

    identifier = CaseIdentifier(gemini)
    fetcher = CaseFetcher(cl_client, congress_client, scotus_client)
    synthesizer = Synthesizer(gemini)

    # Header
    print(f"\n{BOLD}{BLUE}{'═' * 70}{RESET}")
    print(f"{BOLD}{BLUE}  ⚖️  Constitutional Law Research Agent{RESET}")
    print(f"{DIM}  Gemini → CourtListener + SCOTUS + Congress.gov → Gemini{RESET}")
    print(f"{BOLD}{BLUE}{'═' * 70}{RESET}")

    # Check keys
    missing = []
    if not gemini.is_configured():
        missing.append("GEMINI_API_KEY")
    if not cl_client.is_configured():
        missing.append("COURTLISTENER_API_TOKEN")
    if not congress_client.is_configured():
        missing.append("CONGRESS_API_KEY")
    if missing:
        print(f"\n  {YELLOW}⚠ Missing: {', '.join(missing)}")
        print(f"  Add them to .env (see .env.example){RESET}")
        if "GEMINI_API_KEY" in missing:
            print(f"  {YELLOW}Gemini is required for this tool to work.{RESET}")
            return

    # Main loop
    while True:
        print(f"\n{CYAN}  Ask a legal question (or 'quit'):{RESET}")
        question = input(f"  {BOLD}> {RESET}").strip()

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print(f"\n  {DIM}Goodbye!{RESET}\n")
            break

        research(question, identifier, fetcher, synthesizer)


def research(question, identifier, fetcher, synthesizer):
    """The three-step pipeline."""

    # ── STEP 1: Ask Gemini what cases/statutes to look for ───────
    print(f"\n{DIM}  [1/3] Asking Gemini to identify relevant cases...{RESET}",
          end="", flush=True)
    targets = identifier.identify(question)
    print(f" ✓{RESET}")

    case_names = targets.get("cases", [])
    statute_names = targets.get("statutes", [])

    if case_names:
        print(f"  {GREEN}Found {len(case_names)} cases to research:{RESET}")
        for name in case_names:
            print(f"    {DIM}• {name}{RESET}")
    if statute_names:
        print(f"  {GREEN}Found {len(statute_names)} statutes to research:{RESET}")
        for name in statute_names:
            print(f"    {DIM}• {name}{RESET}")

    if not case_names and not statute_names:
        print(f"  {YELLOW}Gemini couldn't identify specific cases. Try rephrasing.{RESET}")
        return

    # ── STEP 2: Fetch real data from legal databases ─────────────
    print(f"\n{DIM}  [2/3] Fetching from CourtListener, SCOTUS, Congress.gov...{RESET}",
          end="", flush=True)
    fetched = fetcher.fetch(case_names, statute_names)
    # Pass along what was identified so synthesizer can flag missing statutes
    fetched["identified_statutes"] = statute_names
    print(f" ✓{RESET}")

    found_cases = len(fetched.get("cases", []))
    found_statutes = len(fetched.get("statutes", []))
    print(f"  {GREEN}Retrieved: {found_cases} cases, {found_statutes} statutes{RESET}")

    # ── STEP 3: Gemini synthesizes the answer ────────────────────
    print(f"\n{DIM}  [3/3] Synthesizing answer...{RESET}", end="", flush=True)
    result = synthesizer.synthesize(question, fetched)
    print(f" ✓{RESET}")

    # ── Save to output folder ────────────────────────────────────
    out_path = save_result(question, result)
    print(f"\n  {DIM}Saved: {out_path}{RESET}")

    # ── Display ──────────────────────────────────────────────────
    display(result)


def display(result):
    """Print the final output."""

    # TLDR
    print(f"\n{BOLD}{YELLOW}{'─' * 70}{RESET}")
    print(f"{BOLD}{YELLOW}  💡 TLDR{RESET}")
    print(f"{BOLD}{YELLOW}{'─' * 70}{RESET}")
    print(wrap(result.get("tldr", "No summary available.")))
    print(f"{BOLD}{YELLOW}{'─' * 70}{RESET}")

    # Key Cases
    cases_text = result.get("key_cases", "")
    if cases_text:
        print(f"\n{BOLD}{CYAN}  ⚖️  KEY CASES{RESET}")
        print(f"{DIM}  {LINE}{RESET}")
        print(wrap(cases_text))

    # Statutes
    statutes_text = result.get("statutes", "")
    if statutes_text:
        print(f"\n{BOLD}{CYAN}  📜 RELEVANT STATUTES{RESET}")
        print(f"{DIM}  {LINE}{RESET}")
        print(wrap(statutes_text))

    # Answer
    answer_text = result.get("answer", "")
    if answer_text:
        print(f"\n{BOLD}{GREEN}  📋 ANSWER{RESET}")
        print(f"{DIM}  {LINE}{RESET}")
        print(wrap(answer_text))

    # Gaps
    gaps_text = result.get("gaps", "")
    if gaps_text:
        print(f"\n{BOLD}{DIM}  🔍 GAPS IN THIS RESEARCH{RESET}")
        print(f"{DIM}  {LINE}{RESET}")
        print(wrap(gaps_text))

    print(f"\n{DIM}  {'─' * 70}{RESET}")
    print(f"{DIM}  ⚠️  For research only. Not legal advice.{RESET}")


if __name__ == "__main__":
    main()
