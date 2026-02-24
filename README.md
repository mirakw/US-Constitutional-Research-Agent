# ⚖️ US Constitutional Law Research Agent

**An AI-powered legal research agent that identifies relevant case law, fetches real court opinions, and synthesizes clear answers with proper citations.**

> * This project demonstrates a two-pass RAG pipeline — Gemini identifies what matters, real legal databases provide the evidence, and Gemini synthesizes the answer. The result: grounded legal research where every case is real, every citation is verified, and the system is transparent about what's sourced vs. interpreted.*

---

## What It Does

You ask a legal research question in plain language. The agent:

1. **Identifies** the specific cases and statutes relevant to your question using Gemini
2. **Fetches** real court opinions from CourtListener (V4 API), landmark cases from the SCOTUS database, and legislation from Congress.gov
3. **Filters** for relevance — only passes verified, on-topic results forward
4. **Synthesizes** everything into a structured answer: TLDR, key cases with holdings and links, relevant statutes, a connecting analysis, and research gaps
5. **Labels transparency** — statutes not found in databases but explained by Gemini are clearly marked as "⚠️ Gemini Interpretation"

### Example

```
> How has the 4th Amendment been applied to digital privacy and cell phone searches?

  [1/3] Asking Gemini to identify relevant cases... ✓
  Found 7 cases to research:
    • Riley v. California
    • Carpenter v. United States
    • Katz v. United States
    • United States v. Jones
    • Kyllo v. United States
    • Smith v. Maryland
    • City of Ontario v. Quon
  Found 2 statutes to research:
    • Electronic Communications Privacy Act of 1986 (ECPA)
    • Stored Communications Act (SCA), 18 U.S.C. § 2701 et seq.

  [2/3] Fetching from CourtListener, SCOTUS, Congress.gov... ✓
  Retrieved: 7 cases, 2 statutes

  [3/3] Synthesizing answer... ✓

  💡 TLDR
  The Supreme Court has extended Fourth Amendment protections to digital data,
  recognizing a person's reasonable expectation of privacy in the vast information
  stored on their cell phone and in their historical location data. Police generally
  need a warrant to search the digital contents of a cell phone, even during an
  arrest, and to obtain a person's historical cell-site location information.

  ⚖️  KEY CASES
  Riley v. California, 136 S. Ct. 506 (2015)
  - HOLDING: Police may not search a cell phone without a warrant during arrest.
  - LINK: https://www.courtlistener.com/opinion/8421386/riley-v-california/
  ...

  📜 RELEVANT STATUTES
  ⚠️ Gemini Interpretation — not sourced from database
  Stored Communications Act (SCA), 18 U.S.C. § 2701 et seq. — Governs how
  the government can compel service providers to disclose stored electronic
  communications and subscriber records...
```

---

## Quick Start

```bash
git clone https://github.com/mirakw/constitutional-law-research-agent.git
cd constitutional-law-research-agent

pip install -r requirements.txt
```

### Get API Keys (all free, no credit card)

| Service | Sign Up | What It Provides |
|---------|---------|-----------------|
| **CourtListener** | [courtlistener.com/sign-in](https://www.courtlistener.com/sign-in/) | Case law search across federal courts |
| **Congress.gov** | [api.data.gov/signup](https://api.data.gov/signup/) | Federal legislation and bill data |
| **Google Gemini** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | AI identification + synthesis |

### Configure and Run

```bash
cp .env.example .env
# Edit .env with your three API keys

python main.py
```

Type your legal question at the prompt. Type `quit` to exit.

---

## Architecture

The agent uses a **two-pass Gemini pipeline** — Gemini is the brain that knows what to look for, and the synthesizer that writes up what was found. Real legal databases provide the evidence in between.

```
User Question (plain language)
        │
        ▼
   ┌─────────────────────────────┐
   │  STEP 1: Case Identifier    │
   │  Gemini identifies which     │
   │  cases and statutes matter   │
   └──────────────┬──────────────┘
                  │
        List of specific case names + statute names
                  │
                  ▼
   ┌─────────────────────────────┐
   │  STEP 2: Case Fetcher       │
   │  Parallel search across:     │
   │  • CourtListener (V4 API)   │
   │  • SCOTUS Landmark DB       │
   │  • Congress.gov API         │
   │                              │
   │  Deduplicates + ranks by    │
   │  court level and relevance  │
   └──────────────┬──────────────┘
                  │
        Real case data: citations, holdings, excerpts, links
                  │
                  ▼
   ┌─────────────────────────────┐
   │  STEP 3: Synthesizer        │
   │  Gemini produces:           │
   │  • TLDR                     │
   │  • Key Cases + Holdings     │
   │  • Relevant Statutes        │
   │  • Connecting Analysis      │
   │  • Research Gaps            │
   └─────────────────────────────┘
```

### Why Two Passes?

A single-pass approach (search databases → summarize) produces garbage results because keyword search returns irrelevant cases. The two-pass approach solves this:

- **Pass 1:** Gemini already knows that qualified immunity requires *Harlow v. Fitzgerald*, *Pearson v. Callahan*, and *Kisela v. Hughes*. It tells the system exactly what to fetch.
- **Pass 2:** Gemini synthesizes only from verified, retrieved data. It cannot hallucinate cases because it's constrained to what the databases returned.

This separation of "what to find" from "what to say about it" is what makes the output reliable.

---

## Data Sources

| Source | API | What It Provides |
|--------|-----|-----------------|
| **CourtListener** | REST V4 (Free Law Project) | 5M+ opinions from federal and state courts. Full-text search, citations, court metadata, opinion excerpts, and direct links. |
| **SCOTUS Landmark DB** | Built-in | Curated database of landmark Supreme Court cases organized by constitutional topic (4th Amendment, 1st Amendment, Equal Protection, etc.) with case names, citations, and holdings. |
| **Congress.gov** | REST (Library of Congress) | Federal bills, resolutions, and legislative actions. Searched for relevant statutes and legislation. |
| **Google Gemini** | REST (3-Flash-Preview) | Case identification (Step 1) and synthesis (Step 3). Temperature set to 0.0 for deterministic, reproducible output. |

---

## Output Structure

Every response follows this format:

| Section | What It Contains |
|---------|-----------------|
| **💡 TLDR** | 2-3 sentence direct answer to the question |
| **⚖️ Key Cases** | Every retrieved case with: holding, key facts, why it matters, CourtListener link |
| **📜 Relevant Statutes** | Statutes from database (cited normally) + statutes explained by Gemini (labeled "⚠️ Gemini Interpretation") |
| **📋 Answer** | 2-4 paragraph analysis connecting cases and statutes to the question |
| **🔍 Gaps** | What's missing from this research and where to dig deeper |

---

## Project Structure

```
constitutional-law-research-agent/
├── main.py                     # Terminal entry point (interactive loop)
├── .env.example                # Template for API keys
├── requirements.txt            # Python dependencies
│
├── pipeline/                   # Three-step processing pipeline
│   ├── gemini_client.py        # Shared Gemini API wrapper (temperature=0.0)
│   ├── identifier.py           # Step 1: Gemini identifies cases + statutes
│   ├── fetcher.py              # Step 2: Fetches from legal databases in parallel
│   └── synthesizer.py          # Step 3: Gemini synthesizes the final answer
│
├── sources/                    # Legal database clients
│   ├── courtlistener.py        # CourtListener V4 API client
│   ├── congress.py             # Congress.gov API client
│   └── scotus.py               # SCOTUS landmark case database
│
└── tests/
```

---

## Sample Questions

These are good starting points that exercise different parts of the system:

| Question | Tests |
|----------|-------|
| "How has the 4th Amendment been applied to digital privacy and cell phone searches?" | Core constitutional law, multiple landmark cases, statute interpretation |
| "What is the current standard for qualified immunity in excessive force cases?" | Judge-made doctrine, circuit courts, evolving standards |
| "Can police search my cell phone without a warrant during a traffic stop?" | Practical application, Riley v. California |
| "What protections exist against excessive force by police officers?" | Civil rights, Section 1983, Graham v. Connor |
| "What are students' free speech rights in public schools?" | First Amendment, Tinker v. Des Moines |
| "What due process rights exist in civil asset forfeiture proceedings?" | Due process, property rights |

---

## Design Decisions

- **Terminal-only:** No web UI. The focus is on output quality, not presentation. This is a research tool, not a product demo.
- **Two-pass pipeline:** Gemini identifies → databases verify → Gemini synthesizes. This eliminates the garbage-in-garbage-out problem of keyword search.
- **Transparency labeling:** When the system uses Gemini's own knowledge (e.g., explaining a statute not found in Congress.gov), it says so explicitly. Users always know what's sourced vs. interpreted.
- **Deterministic output:** Temperature set to 0.0. Same question produces the same answer every time. For legal research, consistency matters.
- **All free APIs:** No credit card required for any data source. CourtListener, Congress.gov, and Gemini all have free tiers.

---

## Limitations & Disclaimer

⚖️ **This is for research purposes only — not legal advice.** Always consult a licensed attorney for legal matters.

- AI synthesis is assistive — Gemini can misinterpret holdings or miss nuance
- CourtListener search may not surface every relevant case, especially from state courts
- Congress.gov searches bills, not codified law — many relevant statutes (like 42 U.S.C. § 1983) won't appear in database results
- The SCOTUS landmark database is curated but not exhaustive
- Case excerpts from CourtListener are summaries, not full opinions

---

## Author

**Mira Kapoor Wadehra** — AI Product Manager
[LinkedIn](https://linkedin.com/in/mira-wadehra)

Building AI tools that make legal research more accessible.

---

## License

MIT
