# AIM Transcript Intelligence — Master Plan

## The One-Line Pitch
> "We didn't just analyze AIM's past. We built the intelligence layer AIM needs to make better content decisions — starting today."

---

## Business Framing (Core Reframe)

AIM is a media company. Judges are AIM employees/stakeholders. The output must look like
something their editorial team would open on Monday morning — not a hackathon demo.

**AIM's real objectives we serve:**
| Objective | What We Deliver |
|---|---|
| Audience growth | Topics rising fast that AIM is undercovering — editorial opportunities |
| Content strategy | What gets watched vs what gets produced — the gap |
| Sponsorship revenue | Companies/tools appearing in high-performing content — who to pitch |
| Event programming | Topics and speakers audience responds to most (directly useful for MLDS) |
| Brand authority | AIM as early predictor — 8 trends called before mainstream |

**Visualization reframe:**
| Old | New |
|---|---|
| Hype Cycle Chart | "Rising topics you're undercovering — editorial opportunities" |
| Speaker Network | "Your most influential guests and brand associations" |
| What AIM Predicted Early | "Your credibility score — trends you called first" |
| Hype vs Reality Quadrant | "What your audience watches vs what you produce" |
| Sentiment Trajectory | "How audience tone has shifted — what resonates" |

---

## What We're Building
An automated multi-agent Content Intelligence Dashboard — transforming 10 years of AIM Media
House YouTube transcripts into actionable editorial, sponsorship, and brand strategy intelligence.

---

## MLDS 2026 Day 1 — Principles Directly Applied

Our architecture is explicitly informed by frameworks presented by practitioners at MLDS 2026, Day 1.
We cite specific speakers. Judges will recognize their own conference in our design.

| Speaker | Company | Session Title | How We Apply It |
|---|---|---|---|
| Anshul Singh & Sanketh Gadadinni | MathCo | *Building Smarter AI Agents with Memory and Context* | All 3 memory types implemented in DuckDB: Episodic (event log), Semantic (RAG vector index), Procedural (runbook rules table) — shared across all agents |
| Shashank Rao | Atlassian | *Agentic Request Delegation and Resolution* | Orchestrator as Supervisor with hierarchical replanning; Auditor triggers reruns |
| Vaibhav Jain | Millennium | *Building Trust in an AI Agent When Stakes Get Real* | Edit Distance KPI on dashboard; shadow mode; immutable audit log |
| Ayushman Gupta & Chirag Jain | Genpact | *A Unified Framework for Training, Trajectory Improvement, Optimization, and Evaluation of Agentic AI Systems* | Judge agent evaluates full reasoning traces; 5% Tier 2 sampling + 100% Tier 3 |
| Nikhil Mohanlal Daxini | EY GDS | *From Cost Center to AI Command Center: Building an AI-Native Innovation Hub* | Core framing: "intelligence arbitrage." Adaptive pipeline config via YAML. |
| Alok Shrivastwa | Microland | *Agentic AI is Easy. Running It in Production is Not.* | Shadow mode Auditor; intent-logged actions; 4-layer agent stack; no silent failures |
| Sumeet Tandure | Snowflake | *Guiding Principals for Multi-Agentic Applications Architecture* | Human-readable DuckDB schema (semantic layer); Decision Intelligence framing |
| Sarath M & Rajesh Parvathini | Tiger Analytics | *Reframing Classical Data Science Solutions within an Agentic AI Framework* | Self-correcting agentic loops; Analyst re-runs on quality drop |
| Soummo Bose | Tata Steel | *Building Production-Grade ML Systems for Heavy Industry* | Auditor runs in passive shadow mode for first 100 videos to calibrate thresholds |
| Prof. Snehanshu Saha | BITS Pilani | *Intelligence in Structure, Not Policy* | Hype Cycle graph encodes topic relationships structurally — intelligence in shape |
| Siddharth Taliyan | TiDB | *The Data Layer for AI Agents: Why Your Database Architecture Will Make or Break Your Agent* | DuckDB status column for crash recovery; parallel solution path isolation |
| Vignesh Subrahmaniam | Intuit | *Reinforcement Learning and beyond: Grounding AI in a Stochastic World* | Judge grounds evaluations against source transcripts — outcome-based, not linguistic |
| Prof. Ganesh Ramakrishnan | IIT Bombay / BharatGen | *BharatGen: Sovereign & Shared: Frugally Scalable Multilingual-Multimodal AI for Bharat* | Report + dashboard available in Hindi, Tamil, Telugu via AI4Bharat translation layer |

---

## Pitch Lines (Use Verbatim in README, Video, Report)

> *"As Nikhil Daxini (EY GDS) said in 'From Cost Center to AI Command Center' — we didn't build bolt-on AI. We reimagined the entire analysis workflow from the ground up."*

> *"Shashank Rao (Atlassian) introduced the Supervisor-Specialist architecture in 'Agentic Request Delegation and Resolution.' Our Orchestrator implements exactly that — including hierarchical replanning when the Auditor signals a quality failure."*

> *"Vaibhav Jain (Millennium) made Edit Distance the north star KPI in 'Building Trust in an AI Agent When Stakes Get Real.' We track it live on our dashboard — every rerun is logged."*

> *"Ayushman Gupta and Chirag Jain (Genpact) introduced trajectory-based learning in 'A Unified Framework for Training, Trajectory Improvement, Optimization, and Evaluation of Agentic AI Systems.' Our Judge agent evaluates the full reasoning trace of every yearly synthesis."*

> *"Alok Shrivastwa (Microland) warned us in 'Agentic AI is Easy. Running It in Production is Not.' — our Auditor runs in shadow mode first, and every agent action is logged with intent. Silent failures don't make it through."*

> *"Anshul Singh and Sanketh Gadadinni (MathCo) showed in 'Building Smarter AI Agents with Memory and Context' that production agents need Episodic, Semantic, and Procedural memory. We implement all three within a Shared Blackboard in DuckDB — one store, all agents, zero context rot."*

> *"Prof. Snehanshu Saha (BITS Pilani) argued in 'Intelligence in Structure, Not Policy' that well-designed structure outperforms complex policy. Our Hype Cycle graph encodes topic relationships structurally — intelligence in the shape of the data, not just the model."*

> *"Inspired by Prof. Ganesh Ramakrishnan's session 'BharatGen: Sovereign & Shared: Frugally Scalable Multilingual-Multimodal AI for Bharat' — our report is available in Hindi, Tamil, and Telugu via AI4Bharat's open-source translation layer."*

---

## Adaptive Architecture (Level 2: Agent Configuration Adaptation)

The Orchestrator reads `context/insights.yaml` at startup and **reconfigures the pipeline** —
which agents activate, in what order, and with what parameters — based on the latest insights.
This is genuine decision-making, not just prompt injection.

### How It Works

```
context/insights.yaml contains:
  - focus_areas: [governance, memory, structural_intelligence]
  - emphasis: high_stakes_trust
  - additional_analysis: [grounding, rlaif]
```

Orchestrator reads this and decides:
- `governance` flagged → activate Auditor with strict intent-validation mode
- `memory` flagged → enable full 3-tier LTM for all agents
- `high_stakes_trust` → Judge agent runs on every summary, not just spot-checks
- `grounding` flagged → Judge validates all claims against source transcripts (RL-AIF style)

### What Changes Between Day 1 and Day 2 Context
- New focus areas → different agents activate or run in stricter modes
- Only the affected steps re-run (e.g., re-synthesis costs ~$0.50)
- Decision log shows exactly what the Orchestrator changed and why

### ⚠️ SUBMISSION NOTE — Day 2 Adaptation Feature
**We are submitting before Day 2 ends. Highlight this explicitly in README, video, and report:**

> *"This submission was built and running before Day 2. The architecture already supports
> live Day 2 adaptation — no code changes required. Add Day 2 insights to
> `context/insights.yaml`, run `python run.py --complete-deep-dive`, and the Orchestrator
> reconfigures the full pipeline automatically. We built the system to learn from the
> conference it was presented at."*

**Why this scores points:**
- Innovation (10%): Architecture that adapts to new intelligence without code changes
- Agentic Workflow (25%): Genuine orchestrator decision-making, not hardcoded script
- Presentation (10%): Shows live awareness that this is a real-world hackathon setting

**Where to say it:**
- README: "Architecture note" section with the exact YAML → re-run flow
- Video: "...and if new insights emerge from Day 2, one YAML update reruns the synthesis"
- Report intro: "Designed to adapt to MLDS Day 2 insights in real time"

### What We Claim (Accurately)
*"The Orchestrator reads a context layer and reconfigures the pipeline — which agents activate,
in what order, with what parameters — based on the latest insights from MLDS 2026 Day 1.
The architecture is already live-ready for Day 2 without a single code change."*

This is Daxini's "built-in AI" principle made literal. The architecture adapts to new intelligence
without code changes.

---

## Agent Architecture

Seven agents with genuine decision logic. Each emits a structured decision log judges can inspect.

| Agent | Role | The Decision It Makes |
|---|---|---|
| **Orchestrator** (Supervisor) | Manages queue, state, failures | Routes work, triggers retries, listens for Auditor rerun signals |
| **Archivist** | Fetches transcripts | Per video: API transcript → yt-dlp fallback → flag unprocessable |
| **Triage** | Scores transcript quality | Routes to Tier 2 (full analysis), Tier 1 (keywords only), or skip |
| **Analyst** | Extracts topics, entities, trends | Chooses analysis depth based on Triage score. Uses ReAct. |
| **Narrator** | Writes yearly summaries | Selects narrative framing: "emergence", "peak", "decline", "resurgence" |
| **Auditor** (Shadow + Reflection) | Validates output | Shadow mode first 100 videos to calibrate. Then: critiques Narrator, calls `signal_rerun()` to Orchestrator if quality fails. Logs Edit Distance. |
| **Judge** | Evaluates reasoning traces | 100% of Tier 3 (10 yearly syntheses) + random 5% of Tier 2. Not all 3000. |

### Auditor → Orchestrator Feedback Loop (genuine agency)
Auditor is not passive. If Edit Distance exceeds threshold:
1. Auditor calls `signal_rerun(video_id, reason, prompt_adjustment)`
2. Orchestrator re-queues the video for Narrator with modified prompt
3. Max 2 reruns per video to prevent infinite loops
4. All rerun signals logged to Blackboard for Judge inspection

### Shared Memory: MathCo 3-Tier Framework in a Shared Blackboard (DuckDB)

MathCo (Anshul Singh & Sanketh Gadadinni) defined 3 memory types. We implement all 3 within
a single shared DuckDB store — not isolated per-agent silos. All agents read/write to the same
database. One agent's failure becomes everyone's learning.

**Episodic Memory** — `episodic` table
Discrete event log. What happened to each video, in order, immutably.
| Column | Purpose |
|---|---|
| `video_id` | Primary key |
| `status` | `PENDING → FETCHED → TRIAGED → ANALYZED → SUMMARIZED → AUDITED` |
| `fetch_method` | `transcript_api` / `ytdlp_subtitle` / `unavailable` |
| `triage_score` | Float 0–1, set by Triage agent |
| `rerun_count` | How many times Auditor triggered a Narrator rerun |
| `edit_distance` | Delta between Narrator draft and Auditor-approved final |
| `cost_gemini` | Token cost for this video (Gemini Flash) |
| `cost_claude` | Token cost for this video (Claude Sonnet) |
| `agent_log` | JSON array of every agent action + decision on this video |

**Semantic Memory** — `semantic` table + vector index
Relationships between content. Grounds Narrator and Judge in actual transcript data.
| Column | Purpose |
|---|---|
| `chunk_id` | Primary key |
| `video_id` | Foreign key to episodic |
| `year` | Upload year |
| `chunk_text` | 500-token transcript chunk |
| `embedding` | Float array (sentence-transformers `all-MiniLM-L6-v2`, local/free) |
| `topics` | Extracted topic tags |
| `entities` | Extracted PERSON + ORG entities (spaCy) |

Narrator queries this before writing: *"what transcripts are most relevant to 2022?"*
Judge validates claims: *"does this assertion appear in source chunks?"*

**Procedural Memory** — `procedural` table
How-to logic. Quality thresholds, retry rules, escalation conditions. Updated when context YAML changes.
| Column | Purpose |
|---|---|
| `rule_id` | Primary key |
| `condition` | e.g. `triage_score < 0.3` |
| `action` | e.g. `skip` / `tier1_only` / `tier2_full` |
| `rerun_prompt_modifier` | Injected into Narrator prompt on Auditor rerun |
| `source` | `default` / `mlds_day1` / `mlds_day2` (which context loaded this rule) |

When Orchestrator reads `context/insights.yaml`, it writes new rows to `procedural` —
this is the adaptive pipeline in action, fully traceable.

Status column enables crash recovery — Orchestrator queries `WHERE status != 'AUDITED'` to resume.

---

## 3-Tier Processing (Cost Control)

```
Tier 1 — FREE (ALL videos):
  TF-IDF term frequency by year
  spaCy NER entity extraction (PERSON + ORG)
  First-mention date detection per term
  YouTube engagement data (views, likes via yt-dlp)
  → Powers all 5 signature visualizations

Tier 2 — Haiku (~$0.10 total, ALL transcripts):
  1-paragraph summary per video
  3-5 topic tags
  Sentiment label
  → Input to yearly synthesis

Tier 3 — Sonnet (~$0.50 total, 10 calls):
  1000-word yearly synthesis from Tier 2 summaries
  Narrative arc framing per year
  → Required PDF/HTML report
```

**Target total LLM cost: under $1. Displayed live as a feature.**

---

## Five Signature Visualizations

### 1. AIM Hype Cycle Chart
- Multi-line Plotly chart: 30 AI terms × 10 years, frequency normalized by video count
- Terms: blockchain, deep learning, NLP, AutoML, MLOps, GPT, LLM, RAG, agents, etc.
- Structural graph encodes topic relationships (BITS Pilani UMST principle)
- **This is the first thing judges see on the dashboard**

### 2. Speaker Network Graph
- spaCy NER extracts PERSON + ORG entities from all transcripts
- Pyvis interactive HTML: nodes = people/orgs/topics, edges = co-occurrence
- Node size = total mentions, edge weight = co-occurrence count
- Interactive — judges can click and explore

### 3. "What AIM Predicted Early"
- AIM's first-mention date vs hardcoded mainstream breakthrough dates
- Topics where AIM led by 6+ months = "Early Call" badge
- Timeline with "AIM covered → mainstream adoption" arrows
- **Judges are AIM people. This flatters the channel with data.**

### 4. Hype vs Reality Quadrant (Gartner-style)
- X-axis: mention frequency (hype), Y-axis: engagement trend (reality)
- 4 quadrants: Enduring Relevance / Overhyped / Hidden Gem / Fading Fast
- Needs view/like counts from yt-dlp alongside transcripts

### 5. Sentiment Trajectory (Core Objective — required by rubric)
- VADER sentiment (free, local, no API) on every transcript → positive/neutral/negative score per video
- Aggregated by year → line chart showing AIM's tone toward AI over 10 years
- Expected story: cautiously optimistic (2016) → euphoric (2022) → measured/critical (2024) → excited again (2025)
- Cross-reference with Hype Cycle: does sentiment spike when a topic first appears?
- Implementation: `pip install vaderSentiment` — runs on all 3173 transcripts in seconds

### 6. Cost Efficiency Live Counter
- Every Anthropic + Gemini API call logs tokens + cost via cost_tracker.py
- Streamlit dashboard shows running total, live during pipeline execution
- Target: under $1. Final number displayed as dashboard hero metric.

---

## First-Impression Design

With 100+ teams, judges spend ~3-5 minutes per submission. Design for the first 10 seconds.

**Dashboard:** Opens on Hype Cycle Chart — not a pipeline diagram, not a table of videos.
Cost counter (`Total LLM spend: $X.XX`) in top-right corner.

**README:** Line 1-3 = most surprising finding from actual data (written after pipeline runs).
Not "we built a pipeline."

**Architecture diagram:** Eraser.io (beautiful, hand-drawn aesthetic). Not Mermaid boxes.

**Video (HeyGen AI avatar):** Opens with the punchline finding. Shows hype cycle chart at 0:20.
Ends with the cost number. Script written after real insights are extracted.

**The hook number (everywhere):** `10 years. 500+ videos. Under $1.`

---

## Tech Stack

```
Data:         youtube-transcript-api (primary) + yt-dlp (fallback + engagement)
Storage:      DuckDB (analytics) + JSON transcript cache (never re-fetch)
Local ML:     scikit-learn TF-IDF + spaCy en_core_web_sm NER
LLM Tier 2:   Gemini 1.5 Flash (FREE) — 500 video summaries, 1M token context
LLM Tier 3:   claude-sonnet-4-6 (~$0.70 total) — yearly synthesis + Judge agent
Agents:       Python async custom orchestrator — no CrewAI/LangGraph bloat
Context:      context/insights.yaml — injection layer for MLDS Day 1/2 learnings
Viz:          Plotly (hype chart, quadrant) + Pyvis (network graph) + Streamlit
Report:       Jinja2 HTML + WeasyPrint → PDF
Diagram:      Eraser.io export → architecture.png
Video:        HeyGen AI avatar, 2 min
```

**LLM Cost Dashboard (shown live):**
```
Gemini 1.5 Flash:   ~500 calls    $0.00  (free tier)
Claude Sonnet:        ~20 calls    $0.70
─────────────────────────────────────────
Total:                             $0.70
```
Deliberate model selection per task = "Smart LLM Usage" rubric points.

---

## Project Structure

```
aim-transcript-intelligence/
├── agents/
│   ├── orchestrator.py       # Supervisor: queue, state, failure handling
│   ├── archivist.py          # Fetch with fallback decision logic
│   ├── triage.py             # Quality scoring + routing
│   ├── analyst.py            # TF-IDF + NER + ReAct topic modeling
│   ├── narrator.py           # LLM summary generation
│   ├── auditor.py            # Shadow mode + reflection + Edit Distance logging
│   └── judge.py              # LLM-as-a-Judge trace evaluation
├── memory/
│   ├── episodic.py           # Processed video log
│   ├── semantic.py           # RAG index over transcripts
│   └── procedural.py         # Runbooks per quality tier
├── pipeline/
│   ├── youtube_client.py     # yt-dlp wrapper (metadata + transcripts + engagement)
│   ├── transcript_cache.py   # DuckDB storage + JSON cache
│   └── cost_tracker.py       # Token counting + live cost accumulator
├── analysis/
│   ├── hype_cycle.py         # Term frequency timeline (structural graph)
│   ├── speaker_network.py    # Entity co-occurrence graph
│   ├── early_predictor.py    # AIM vs mainstream first-mention
│   └── hype_reality.py       # Engagement vs frequency quadrant
├── context/
│   └── insights.yaml         # MLDS Day 1/2 injection layer (adaptive architecture)
├── dashboard/
│   └── app.py                # Streamlit — opens on hype cycle chart
├── report/
│   ├── generator.py          # Jinja2 → HTML → PDF
│   └── templates/yearly_report.html
├── data/
│   ├── transcripts/          # JSON cache
│   ├── channel.duckdb        # Processed analytics
│   └── term_watchlist.py     # 30 AI terms + mainstream breakthrough dates
├── PLAN.md                   # This file
├── README.md                 # Hook-first, real findings, architecture diagram
├── architecture.png          # Eraser.io export
└── requirements.txt
```

---

## Run Modes

```bash
python run.py --sprint-demo        # ~5 min | top 5 videos/year (~55 total) | judges can re-run live
python run.py --complete-deep-dive # ~4 hrs | all 3173 videos | pre-computed outputs committed to repo
```

Rate limits are not the constraint (YouTube Data API handles 3173 videos in ~64 calls).
Two modes serve different purposes:
- `--sprint-demo`: reproducibility — judges can verify the pipeline actually works in real time
- `--complete-deep-dive`: depth — the full analysis behind the submitted report and dashboard

---

## Execution Order (Day-of)

```
1.  Setup + dependencies (requirements.txt)
2.  Fetch all video metadata + transcripts → cache to disk
3.  Tier 1: TF-IDF + NER on all transcripts (local, fast, free)
4.  Build all 5 visualizations from Tier 1 data
5.  Tier 2: Haiku summaries per video (async, bulk)
6.  Load context/insights.yaml (MLDS Day 1 learnings)
7.  Tier 3: Sonnet yearly synthesis informed by context layer
8.  Judge agent evaluates all 10 yearly traces
9.  Auditor shadow pass → Edit Distance logged
10. Streamlit dashboard + live cost display
11. Jinja2 → HTML → PDF report
12. README written with real numbers + most surprising finding
13. Eraser.io architecture diagram
14. HeyGen video (script from real insights)
```

---

## Resolved Setup

| Item | Status | Detail |
|---|---|---|
| AIM channel | ✅ | `@aimmediahouse` — 3173 videos, 2015–2026 |
| YouTube Data API key | ✅ | Google Cloud Console — enriched all 3173 videos in 33 seconds |
| Anthropic API key | ✅ | `ANTHROPIC_API_KEY` in `.env` |
| Google AI Studio key | ✅ | `GOOGLE_API_KEY` in `.env` — Gemini Flash free tier |
| DuckDB schema | ✅ | 3-tier blackboard initialized, 3173 videos loaded |
| Dependencies | ✅ | All installed including spaCy `en_core_web_sm` + VADER |
| Year distribution | ✅ | 2015: 44, 2016: 142 ... 2025: 971, 2026: 346 |

---

## Hackathon Requirements Coverage

| Requirement | Status | How |
|---|---|---|
| Data Pipeline | ✅ | youtube-transcript-api + yt-dlp fallback + YouTube Data API |
| Transcript Intelligence | ⬜ | Triage agent: noise removal, filler words, quality scoring |
| Year-wise 1000-word summaries | ⬜ | Narrator agent (Gemini Tier 2 → Claude Sonnet Tier 3) |
| Entity Extraction | ⬜ | spaCy NER: PERSON, ORG, tech tools |
| Topic Modeling | ⬜ | TF-IDF + BERTopic clustering |
| Trend Detection (BONUS) | ⬜ | Hype Cycle Chart — term frequency over 10 years |
| Sentiment Analysis (BONUS) | ⬜ | VADER on all transcripts → tone trajectory chart |
| Knowledge Graph (BONUS) | ⬜ | Speaker Network Graph — Pyvis interactive HTML |
| Full Automation (BONUS) | ⬜ | `run.py --sprint-demo` / `--complete-deep-dive` |
| GitHub repo + README | ⬜ | Written after pipeline runs with real numbers |
| <2 min explainer video | ⬜ | HeyGen AI avatar + NotebookLM Audio Overview (bonus) |
| Architecture diagram | ⬜ | Eraser.io export |
| PDF/HTML report | ⬜ | Jinja2 → WeasyPrint |
| Multilingual output | ⬜ | AI4Bharat Dhruva API — Hindi/Tamil/Telugu |
