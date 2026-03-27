# AIM Transcript Intelligence: Judge's Quick Guide

**30-second version for busy evaluators**

---

## What It Does

7 AI agents analyze **10 years of AIM Media House YouTube content** (3,173 videos) and produce actionable editorial, sponsorship, and brand intelligence, for **under $1 total LLM cost**.

## How to Run It

```bash
python run.py --sprint-demo       # full pipeline in ~5 min
streamlit run dashboard/app.py    # launch dashboard
```

## What Makes Us Different

| Criterion | What We Did |
|---|---|
| **Lessons Learnt from MLDS Conference** | This isn't a pre-built project. Every architectural decision (memory design, supervisor pattern, trust calibration, production path) was directly inspired by what we learned in 13 sessions on Day 1 of the MLDS conference. |
| **Pluggable with Day 2 Insights** | After Day 2 sessions, simply add new learnings to `insights.yaml` and re-run the pipeline. The Orchestrator picks them up automatically and produces updated synthesis. |
| **Fully Agentic** | 7 agents with real decision-making: Archivist adapts fetch strategy per video (Year-Based Heuristic), Auditor rejects bad summaries and triggers reruns, Judge scores reasoning quality. Every decision logged. Inspired from MLDS sessions of Shashank Rao from Atlassian, Ayushman Gupta & Chirag Jain from Genpact, and Alok Shrivastwa from Microland. |
| **Self-Correction Loop with State-of-the-Art Metrics** | When the Auditor finds a bad summary, it rejects it back to the Narrator with an adjusted prompt. Agents talk to each other, not just execute. Inspired by Vaibhav Jain from Millennium in his session *"Building Trust in an AI Agent When Stakes Get Real"*. We applied his Edit Distance KPI and shadow mode approach. |
| **Smart LLM Usage: Under $1 Total** | Local ML (spaCy, TF-IDF, VADER) handles 100% of videos for free. Gemini Flash (free tier) for summaries. Claude Sonnet only for 10 yearly syntheses + Judge. Total: <$1. |
| **Memory Architecture** | DuckDB 3-tier blackboard (Episodic/Semantic/Procedural). Inspired by Anshul Singh & Sanketh Gadadinni from MathCo in their session *"Building Smarter AI Agents with Memory and Context"*. |
| **Smart Data Coverage Strategy** | Year-Based Heuristic: pre-2021 videos skip yt-dlp (no captions existed), go straight to Researcher Agent (YouTube Data API description+tags). 99.97% coverage. |
| **Business Value** | Not just analysis. 5 charts that answer: What should AIM cover next? Who should they pitch? Which speakers drive engagement? |

## Key Deliverables

| Deliverable | Location | What's Inside |
|---|---|---|
| **Interactive Dashboard** | [**Open Dashboard**](https://adharsh2208vthink.github.io/aim-transcript-intelligence/IMPORTANT_FOR_JUDGES/dashboard.html) | 5 interactive Plotly charts + 12 yearly syntheses. Click to view live. |
| **Yearly Report** | [**Open Report**](IMPORTANT_FOR_JUDGES/report.html) | 10 yearly intelligence reports with Judge scores + System Log appendix |
| **Demo Video: Architecture** | [`AIM_Intelligence_Agent_Architecture.mp4`](IMPORTANT_FOR_JUDGES/AIM_Intelligence_Agent_Architecture.mp4) | AI-generated walkthrough of the 7-agent pipeline (NotebookLM) |
| **Demo Video: Summary** | [`Summary_AIM_YouTube_Channel.mp4`](IMPORTANT_FOR_JUDGES/Summary_AIM_YouTube_Channel.mp4) | AI-generated overview of AIM channel intelligence (NotebookLM) |
| **Architecture** | See [README.md](README.md#architecture) | 7-agent pipeline with shared DuckDB blackboard, MLDS Day 1 citations throughout |

## Inspired by 13 MLDS Day 1 Sessions

Every architectural decision traces back to something we learned on Day 1. Five examples:

| Session | Speaker | How We Applied It |
|---|---|---|
| *Building Smarter AI Agents with Memory and Context* | Anshul Singh & Sanketh Gadadinni (MathCo) | 3-tier DuckDB blackboard: Episodic, Semantic, Procedural memory |
| *Building Trust in an AI Agent When Stakes Get Real* | Vaibhav Jain (Millennium) | Edit Distance KPI + shadow mode. Auditor validates before blocking |
| *Agentic Request Delegation and Resolution* | Shashank Rao (Atlassian) | Orchestrator Supervisor pattern. Routes, re-queues, recovers |
| *From Cost Center to AI Command Center* | Nikhil Daxini (EY GDS) | Adaptive YAML config + MCP production path. Built-in, not bolt-on |
| *Intelligence in Structure, Not Policy* | Prof. Snehanshu Saha (BITS Pilani) | Hype Cycle as structural graph. Trend detection from topology, not rules |

Plus 4 more sessions applied across the pipeline (see [full citation table in README](README.md#lessons-learnt-from-mlds-day-1--applied-directly)).

## AIM's Suggested Path to Production

So, how can AIM take this project to production?

As Nikhil Daxini from EY GDS argued in his session *"From Cost Center to AI Command Center"*, AI stops being an experiment the moment it drives decisions that generate revenue. The analysis is already here. The next step is **pushing insights into the tools AIM's team already opens every day:**

| AIM Team | Push Intelligence Into | What They Get Monday Morning |
|---|---|---|
| Editorial | Notion / Google Docs | Rising topics they're undercovering, ready as a 4-week content calendar |
| Sponsorship | HubSpot / Salesforce | Companies in high-performing content, warm leads with context |
| Events (MLDS) | Airtable | Speakers + topics ranked by engagement, lineup shortlist |
| All teams | Slack | Weekly digest: trends, gaps, early calls |

The bridge: **MCP (Model Context Protocol) connectors**. One YAML entry per tool, zero pipeline rework. No new code. Just configuration.

---

**Full details:** [README.md](README.md) | **Repo:** `feature/pipeline` branch
