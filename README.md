# ⚖️ Constitutional Law Research Agent

A professional-grade legal research tool that aggregates case law and statutory data from multiple authoritative sources and uses AI to produce structured research memos with proper citations.

## What It Does

Enter a legal research question like *"How has the 4th Amendment been applied to digital privacy?"* and the agent will:

1. **Search** CourtListener, the Supreme Court database, and Congress.gov in parallel
2. **Retrieve** relevant case law, statutes, and legislative history
3. **Deduplicate & rank** results by court level, relevance, and recency
4. **Synthesize** everything into a structured research memo using Google Gemini
5. **Output** a TLDR + full memo with Bluebook citations

## Data Sources

| Source | What It Provides |
|--------|-----------------|
| **CourtListener** (Free Law Project) | Supreme Court & federal circuit opinions, citation networks |
| **Supreme Court Database** | Current term slip opinions, landmark case references |
| **Congress.gov** (Library of Congress) | Federal legislation, bill text, legislative history |

## Setup

1. **Clone and install dependencies:**
```bash
cd project2-constitutional-research-agent
pip install -r requirements.txt
```

2. **Get your API keys (all free):**
   - CourtListener: https://www.courtlistener.com/sign-in/
   - Congress.gov: https://api.data.gov/signup/
   - Google Gemini: https://aistudio.google.com/apikey

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. **Run the app:**
```bash
python main.py
```
   Ask a legal question at the prompt; each run is saved to the `output/` folder (see **Output** below).

## Architecture

```
User Question
     │
     ▼
Query Parser ──→ search terms for each source
     │
     ▼
Multi-Source Retriever (parallel)
     ├── CourtListener API (case law)
     ├── SCOTUS Database (recent opinions + landmarks)
     └── Congress.gov API (statutes)
     │
     ▼
Deduplicator ──→ merge, rank, clean
     │
     ▼
Gemini Synthesizer ──→ TLDR + Research Memo
```

## Output

- **Folder:** `output/`
- Every research run writes one JSON file: `YYYY-MM-DD_HH-MM-SS_<question_slug>.json`
- Contents: `question`, `timestamp`, and `result` (tldr, key_cases, statutes, answer, gaps)

## Tech Stack

- **Backend:** Python (CLI)
- **Data Sources:** CourtListener API, Congress.gov API, supremecourt.gov
- **AI Synthesis:** Google Gemini API

## Disclaimer

This tool is for research purposes only and does not constitute legal advice.
