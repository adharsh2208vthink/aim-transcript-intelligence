# AIM Transcript Intelligence
### Content Intelligence Dashboard | MLDS 2026 Hackathon

> *"We didn't just analyze AIM's past. We built the intelligence layer AIM needs to make better content decisions, starting today."*

**10 years · 3,173 videos · Under $1 total LLM cost**

<!-- Fill in after pipeline runs: use the most surprising real finding -->
> **Key finding:** `[FILL: e.g. "AIM covered RAG 2 years before it went mainstream, and the data proves it"]`

### TL;DR for Judges

> **7 AI agents** analyze a decade of AIM's YouTube content and produce editorial, sponsorship, and brand intelligence. Every architectural decision (memory design, supervisor pattern, trust calibration, production path) was directly inspired by what we learned in **13 MLDS Day 1 sessions**. Agents don't just execute, they **adapt and self-correct**: the Archivist skips methods it knows won't work, the Auditor rejects bad summaries and triggers reruns, and the Judge evaluates reasoning quality. All of this for **under $1** because local ML handles the heavy lifting and LLMs are reserved for synthesis only. Day 2 insights can be plugged in via `insights.yaml`, no code changes.
>
> **Quick start:** `python run.py --sprint-demo` then `streamlit run dashboard/app.py`
>
> **Detailed judge guide:** [`JUDGES.md`](JUDGES.md)

---

## What This Is

An automated 7-agent pipeline that transforms 10 years of AIM Media House YouTube transcripts into **actionable editorial, sponsorship, and brand intelligence**, the kind AIM's team can open on Monday morning.

| AIM Business Goal | What We Deliver |
|---|---|
| Audience growth | Topics rising fast that AIM is undercovering. Editorial calendar gaps |
| Sponsorship revenue | Companies appearing in high-performing content. Who to pitch |
| Event programming | Speakers + topics with highest engagement. MLDS lineup decisions |
| Brand authority | Trends AIM called before mainstream. Credibility proof |
| Content strategy | What gets watched vs what gets produced. The gap |

---

## Demo

```bash
# Judges: run this to see the full pipeline end-to-end in ~5 minutes
python run.py --sprint-demo

# Launch dashboard
streamlit run dashboard/app.py
```

<!-- Fill in after pipeline runs -->
**Live dashboard:** `[FILL: screenshot or gif of dashboard]`

---

## Architecture

```mermaid
flowchart LR
    subgraph INPUT
        YT["YouTube\n@aimmediahouse\n3,173 videos"]
        YAML["insights.yaml\nMLDS Day 1 Config"]
    end

    subgraph ORCHESTRATOR
        ORC["Orchestrator\nSupervisor"]
    end

    subgraph AGENTS
        direction LR
        ARC["Archivist\nAPI → yt-dlp → unavailable"]
        TRI["Triage\ntier1 / tier2 / skip"]
        ANL["Analyst\nTF-IDF · spaCy · VADER\nFREE LOCAL"]
        NAR2["Narrator T2\nGemini Flash\nfree tier"]
        AUD["Auditor\nShadow mode\nEdit Distance KPI"]
        NAR3["Narrator T3\nClaude Sonnet\n10 x 1000-word"]
        JDG["Judge\nLLM-as-Judge\n100% T3 + 5% T2"]
        ARC --> TRI --> ANL --> NAR2 --> AUD --> NAR3 --> JDG
    end

    subgraph BLACKBOARD["SHARED BLACKBOARD — DuckDB 3-Tier Memory"]
        EPI["Episodic Memory\nPENDING-FETCHED-TRIAGED-ANALYZED-SUMMARIZED-AUDITED"]
        SEM["Semantic Memory\nRAG chunks"]
        PRO["Procedural Memory\nRunbook rules\nmlds_day1 / mlds_day2"]
    end

    subgraph OUTPUT
        DASH["Streamlit Dashboard\n5 Visualizations"]
        RPT["PDF Report\n10 Yearly Syntheses"]
        MULTI["Multilingual\nHindi / Tamil / Telugu"]
    end

    YT --> ARC
    YAML --> ORC
    ORC --> AGENTS
    AUD -->|"signal_rerun()"| ORC
    AGENTS --> BLACKBOARD
    YAML -->|"adaptive rules"| PRO
    BLACKBOARD --> OUTPUT
```

---

## Five Visualizations

| Chart | Business Value |
|---|---|
| **Hype Cycle** | Rising topics AIM is undercovering. Editorial opportunities |
| **Speaker Network** | Most influential guests and brand associations |
| **AIM Predicted Early** | Trends called before mainstream. Brand authority proof |
| **Hype vs Reality** | What gets watched vs what gets produced. Sponsorship targeting |
| **Sentiment Trajectory** | How audience tone has shifted over 10 years |

---

## Agent Architecture

| Agent | Decision It Makes |
|---|---|
| **Orchestrator** | Routes work, reads YAML config, triggers reruns, crash recovery |
| **Archivist** | Per video: youtube-transcript-api → yt-dlp → **Researcher Agent** (YouTube Data API description+tags) → unavailable. **Year-Based Heuristic:** pre-2021 or < 2 min → skip yt-dlp entirely (no captions existed), go straight to Researcher Agent. 5–7× faster. |
| **Triage** | Quality score → tier2 (Gemini) / tier1 (local only) / skip |
| **Analyst** | TF-IDF keywords + spaCy NER + VADER sentiment on all 3,173 videos |
| **Narrator T2** | Gemini Flash 1-paragraph summary per video (free tier) |
| **Auditor** | Shadow mode first 100 videos → Edit Distance KPI → signal_rerun() |
| **Narrator T3** | Claude Sonnet 1000-word yearly synthesis × 10 years |
| **Judge** | 100% of yearly syntheses + 5% random Tier 2 sample |

### The Agentic Loop
When the Auditor finds a bad summary, it rejects it back to the Narrator with an adjusted prompt. Agents talk to each other, not just execute. Self-correction is measured using state-of-the-art metrics. Every decision logged to `agent_log` JSON in DuckDB. Inspired by Vaibhav Jain from Millennium in his session *"Building Trust in an AI Agent When Stakes Get Real"*. We applied his Edit Distance KPI and shadow mode approach.

### Year-Based Heuristic: Agentic Innovation

The Archivist doesn't blindly retry every method for every video. It **adapts its strategy based on metadata:**

| Condition | Strategy | Reason |
|---|---|---|
| Pre-2021 video | Skip yt-dlp → Researcher Agent directly | YouTube auto-captions weren't widely available before 2020 |
| Duration < 2 min | Skip yt-dlp → Researcher Agent directly | Short clips are typically music/text overlays with no speech |
| 2021+ and > 2 min | Full pipeline: transcript API → yt-dlp → Researcher | Modern videos likely have auto-captions |

**Result:** 5–7× faster fetch for the ~1,100 older videos that would otherwise waste 10 seconds each on yt-dlp timeouts. The system learns which videos are worth trying and which to skip, not by external config, but by reasoning about the data it already has.

---

## Shared Blackboard: DuckDB 3-Tier Memory

*Inspired by Anshul Singh & Sanketh Gadadinni from MathCo in their session "Building Smarter AI Agents with Memory and Context", MLDS 2026 Day 1*

| Tier | Table | Purpose |
|---|---|---|
| **Episodic** | `episodic` | Immutable event log per video. Status, cost, agent decisions |
| **Semantic** | `semantic` | Transcript chunks for RAG. Grounds Narrator + Judge |
| **Procedural** | `procedural` | Runbook rules. Updated by YAML config at startup |

---

## Adaptive Architecture: Day 1 → Day 2

*Inspired by Nikhil Daxini from EY GDS in his session "From Cost Center to AI Command Center", MLDS 2026 Day 1*

The Orchestrator reads `context/insights.yaml` at startup and **reconfigures the pipeline without code changes**:

```bash
# After Day 2 sessions: add new insights to insights.yaml, then:
python run.py --complete-deep-dive
# Orchestrator re-adapts automatically. Re-synthesis costs ~$0.50.
```

This system was **submitted during MLDS 2026**. It is designed to learn from the same conference it was evaluated at.

---

## AIM's Suggested Path to Production

So, how can AIM take this project to production?

As Nikhil Daxini from EY GDS argued in his session *"From Cost Center to AI Command Center"*, AI stops being an experiment the moment it drives decisions that generate revenue. The analysis is already here. The next step is **pushing insights into the tools AIM's team already opens every day:**

The bridge: **MCP (Model Context Protocol) connectors**. One config addition per tool, no pipeline rework.

| AIM Team | Tool They Use | What Gets Pushed | Business Impact |
|---|---|---|---|
| Editorial | Notion / Google Docs | Rising topics undercovered → 4-week content calendar, pre-drafted | Audience growth |
| Sponsorship | HubSpot / Salesforce | Companies in high-performing content → CRM leads with context | Revenue pipeline |
| Events (MLDS) | Airtable | Speakers + topics ranked by engagement → shortlist ready | Programming decisions |
| All teams | Slack | Weekly digest: trends, gaps, early calls | Monday morning intelligence |

```
Current state:  Pipeline → Dashboard (pull)
Production:     Pipeline → MCP connectors → Notion / HubSpot / Slack (push)
Code change:    Zero. One entry in insights.yaml per connector.
```

This is what Nikhil described as the shift from "AI as experiment" to "AI as command center": intelligence embedded in the workflow, not sitting in a tab nobody opens.

### Day 1 → Production: Three Next Steps

| MLDS Day 1 Session | Production Insight | What It Means for AIM |
|---|---|---|
| Nikhil Daxini (EY GDS), *From Cost Center to AI Command Center* | **Built-in, not Bolt-on** | Don't add AI to the editorial workflow. Rebuild it starting from AI briefs. MCP connectors (above) are step one. |
| Vignesh Subrahmaniam (Intuit), *RL and beyond: Grounding AI in a Stochastic World* | **LLM → SLM Transfer** | The Judge's reasoning traces are fine-tuning data. At 1,000 videos/year, train a smaller model. Same quality, 10x cheaper. Groundwork already laid. |
| Anshul Singh & Sanketh Gadadinni (MathCo), *Building Smarter AI Agents with Memory and Context* | **Semantic Layer** | Translate `tfidf_keywords` and `vader_compound` scores into editorial language AIM's team can act on without a data scientist in the room. |

---

## Lessons Learnt from MLDS Day 1: Applied Directly

| Speaker | Company | Session | Applied As |
|---|---|---|---|
| Anshul Singh & Sanketh Gadadinni | MathCo | *Building Smarter AI Agents with Memory and Context* | 3-tier DuckDB blackboard |
| Shashank Rao | Atlassian | *Agentic Request Delegation and Resolution* | Orchestrator Supervisor pattern |
| Vaibhav Jain | Millennium | *Building Trust in an AI Agent When Stakes Get Real* | Edit Distance KPI + shadow mode |
| Ayushman Gupta & Chirag Jain | Genpact | *Unified Framework for...Agentic AI Systems* | Judge on full reasoning traces |
| Nikhil Daxini | EY GDS | *From Cost Center to AI Command Center* | Adaptive YAML config layer + MCP push connectors for production path |
| Alok Shrivastwa | Microland | *Agentic AI is Easy. Running It in Production is Not.* | Shadow mode + intent logging |
| Prof. Snehanshu Saha | BITS Pilani | *Intelligence in Structure, Not Policy* | Hype Cycle structural graph |
| Vignesh Subrahmaniam | Intuit | *RL and beyond: Grounding AI in a Stochastic World* | Judge grounds vs source transcripts |
| Prof. Ganesh Ramakrishnan | IIT Bombay | *BharatGen: Sovereign & Shared* | AI4Bharat multilingual output |

---

## Cost Breakdown

| Component | Tool | Cost |
|---|---|---|
| Transcript fetch | youtube-transcript-api + yt-dlp | Free |
| NER + sentiment + topics | spaCy + VADER + TF-IDF | Free |
| Video summaries (~500) | Gemini Flash (free tier) | $0.00 |
| Yearly syntheses (×10) | Claude Sonnet | ~$0.50 |
| Judge evaluation | Claude Sonnet | ~$0.20 |
| **Total** | | **< $1.00** |

---

## Setup

```bash
git clone https://github.com/[YOUR_USERNAME]/aim-transcript-intelligence
cd aim-transcript-intelligence
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Add API keys
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, GOOGLE_API_KEY, YOUTUBE_API_KEY

# Run pipeline
python run.py --sprint-demo          # ~5 min, for live demo
python run.py --complete-deep-dive   # full 3,173 videos

# Launch dashboard
streamlit run dashboard/app.py

# Generate PDF report
python report/generator.py
```

---

## Tech Stack

```
Data:       youtube-transcript-api · yt-dlp · YouTube Data API v3
Storage:    DuckDB (analytics blackboard) · JSON transcript cache
Local ML:   scikit-learn TF-IDF · spaCy en_core_web_sm · VADER sentiment
LLM T2:     Gemini 1.5 Flash (free tier), bulk video summaries
LLM T3:     claude-sonnet-4-6, yearly synthesis + Judge
Dashboard:  Streamlit · Plotly · Pyvis
Report:     Jinja2 → WeasyPrint PDF
Multilingual: AI4Bharat Dhruva API
```

---

*MLDS 2026 Hackathon | AIM Media House · Built during the conference it analyzes.*
