"""
AIM Transcript Intelligence — Content Intelligence Dashboard

Opens on the Hype Cycle chart (first impression).
Live cost counter in top-right.
All 5 visualizations + yearly synthesis viewer + agent decision log.
"""

import json
import streamlit as st
import plotly.graph_objects as go

from pipeline.database import get_connection
from analysis.hype_cycle import build_chart as build_hype_chart, compute_hype_data
from analysis.speaker_network import build_network
from analysis.early_predictor import build_chart as build_early_chart
from analysis.hype_reality import build_chart as build_reality_chart
from analysis.sentiment_trajectory import build_chart as build_sentiment_chart

st.set_page_config(
    page_title="AIM Content Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── HEADER ────────────────────────────────────────────────────────────────────

col_title, col_cost = st.columns([3, 1])

with col_title:
    st.title("AIM Media House — Content Intelligence Dashboard")
    st.caption(
        "10 years · 3,173 videos · Transformed into editorial, sponsorship & brand intelligence"
    )

with col_cost:
    con = get_connection()
    cost_gemini = con.execute("SELECT COALESCE(SUM(cost_gemini), 0) FROM episodic").fetchone()[0]
    cost_claude_ep = con.execute("SELECT COALESCE(SUM(cost_claude), 0) FROM episodic").fetchone()[0]
    cost_claude_ys = con.execute("SELECT COALESCE(SUM(cost_claude), 0) FROM yearly_summaries").fetchone()[0]
    total_cost = cost_gemini + cost_claude_ep + cost_claude_ys

    counts = con.execute("""
        SELECT status, COUNT(*) FROM episodic GROUP BY status
    """).fetchall()
    status_map = {r[0]: r[1] for r in counts}
    total = sum(status_map.values())
    audited = status_map.get("AUDITED", 0) + status_map.get("SUMMARIZED", 0)
    con.close()

    st.metric("Total LLM Cost", f"${total_cost:.2f}")
    st.caption(f"Gemini: ${cost_gemini:.2f} | Claude: ${cost_claude_ep + cost_claude_ys:.2f}")
    st.progress(audited / max(total, 1), text=f"{audited}/{total} videos processed")

st.divider()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "View",
        [
            "Hype Cycle",
            "Speaker Network",
            "AIM Predicted Early",
            "Hype vs Reality",
            "Sentiment Trajectory",
            "Yearly Syntheses",
            "Pipeline Status",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("**Architecture:** 7-agent pipeline")
    st.caption("**Memory:** DuckDB 3-tier blackboard")
    st.caption("**LLMs:** Gemini Flash + Claude Sonnet")
    st.caption("**Built for MLDS 2026 Hackathon**")

# ── PAGES ─────────────────────────────────────────────────────────────────────

if page == "Hype Cycle":
    st.subheader("AI Topic Hype Cycle — 10 Years on AIM")
    st.info(
        "**Editorial opportunity:** Rising lines = topics AIM is undercovering. "
        "Peaks = hype moments. Flat = evergreen content that always performs.",
        icon="📈",
    )
    fig = build_hype_chart(output_path=None)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Run the full pipeline first: `python run.py --complete-deep-dive`")

    # Top rising terms this year
    st.subheader("Rising Now — Editorial Opportunities")
    try:
        hype_data, years = compute_hype_data()
        if len(years) >= 2:
            last_year, prev_year = years[-1], years[-2]
            rising = []
            for term, by_year in hype_data.items():
                curr = by_year.get(last_year, 0)
                prev = by_year.get(prev_year, 0)
                if prev > 0:
                    growth = (curr - prev) / prev * 100
                    rising.append((term, curr, growth))
            rising.sort(key=lambda x: -x[2])
            cols = st.columns(4)
            for i, (term, freq, growth) in enumerate(rising[:8]):
                cols[i % 4].metric(
                    term.title(),
                    f"{freq:.0%} coverage",
                    f"{growth:+.0f}% vs {prev_year}",
                )
    except Exception:
        pass


elif page == "Speaker Network":
    st.subheader("Speaker & Brand Network — Who's Connected to What")
    st.info(
        "**Event programming:** Larger nodes = most mentioned people and orgs. "
        "Connected clusters = natural co-occurrence. Use this to plan your next speaker lineup.",
        icon="🕸️",
    )
    with st.spinner("Building network graph..."):
        build_network(output_path="data/speaker_network.html")
    try:
        with open("data/speaker_network.html", "r") as f:
            html = f.read()
        st.components.v1.html(html, height=750, scrolling=False)
    except FileNotFoundError:
        st.warning("Run the full pipeline first.")

    st.caption(
        "Red = People | Blue = Organizations | Green = Tools & Technologies | "
        "Node size = total mentions | Edge weight = co-occurrence frequency"
    )


elif page == "AIM Predicted Early":
    st.subheader("What AIM Predicted Early — Your Brand Authority Score")
    st.info(
        "**Sponsorship deck:** AIM covered these AI trends before mainstream adoption. "
        "This is your credibility proof. Use it in your media kit.",
        icon="🔮",
    )
    fig = build_early_chart(output_path=None)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Run the full pipeline first.")


elif page == "Hype vs Reality":
    st.subheader("Hype vs Reality — What Your Audience Actually Watches")
    st.info(
        "**Sponsorship targeting:** Top-right = Enduring Relevance — "
        "high coverage AND high views. This is where sponsors get ROI.",
        icon="🎯",
    )
    fig = build_reality_chart(output_path=None)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Run the full pipeline first.")


elif page == "Sentiment Trajectory":
    st.subheader("Sentiment Trajectory — How AI Conversations Have Shifted")
    st.info(
        "**Content strategy:** Shows whether your coverage is optimistic, critical, or neutral "
        "by year. Cross-reference with hype cycle to see sentiment spikes at topic launches.",
        icon="📉",
    )
    fig = build_sentiment_chart(output_path=None)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Run Analyst agent first: `python -c \"from agents.analyst import run; run()\"`")

    # Yearly breakdown table
    con = get_connection()
    rows = con.execute("""
        SELECT year,
               COUNT(*) as n,
               ROUND(AVG(sentiment_pos)*100, 1) as pos_pct,
               ROUND(AVG(sentiment_neg)*100, 1) as neg_pct,
               SUM(CASE WHEN sentiment_label='positive' THEN 1 ELSE 0 END) as n_pos,
               SUM(CASE WHEN sentiment_label='negative' THEN 1 ELSE 0 END) as n_neg
        FROM episodic
        WHERE year IS NOT NULL AND sentiment_label IS NOT NULL
        GROUP BY year ORDER BY year DESC
    """).fetchall()
    con.close()

    if rows:
        import pandas as pd
        df = pd.DataFrame(rows, columns=["Year", "Videos", "Avg Pos%", "Avg Neg%", "# Positive", "# Negative"])
        st.dataframe(df, use_container_width=True, hide_index=True)


elif page == "Yearly Syntheses":
    st.subheader("10-Year Annual Intelligence Reports")
    st.caption(
        "Generated by Claude Sonnet from aggregated video data. "
        "Audited and Judge-scored."
    )

    con = get_connection()
    years = con.execute("""
        SELECT year, video_count, judge_score, summary_final, summary_draft
        FROM yearly_summaries
        ORDER BY year DESC
    """).fetchall()
    con.close()

    if not years:
        st.warning("Run Narrator Tier 3 first: `from agents.narrator import run_tier3; run_tier3()`")
    else:
        year_options = [str(r[0]) for r in years]
        selected = st.selectbox("Select Year", year_options)

        for year, video_count, judge_score, summary_final, summary_draft in years:
            if str(year) == selected:
                col1, col2, col3 = st.columns(3)
                col1.metric("Year", year)
                col2.metric("Videos Analyzed", video_count or "—")
                col3.metric("Judge Score", f"{judge_score:.1f}/10" if judge_score else "—")

                synthesis = summary_final or summary_draft or ""
                if synthesis:
                    st.markdown(synthesis)
                else:
                    st.info("Synthesis not yet generated for this year.")
                break


elif page == "Pipeline Status":
    st.subheader("Pipeline Status — Agent Decision Log")

    con = get_connection()

    # Status distribution
    status_rows = con.execute("""
        SELECT status, COUNT(*) as n FROM episodic GROUP BY status ORDER BY n DESC
    """).fetchall()

    if status_rows:
        import pandas as pd
        cols = st.columns(min(len(status_rows), 5))
        for i, (status, count) in enumerate(status_rows[:5]):
            cols[i].metric(status, count)

        st.divider()

    # ── DATA INTEGRITY SCORE ──────────────────────────────────────────────────
    st.subheader("System Health — Data Integrity")
    fetch_rows = con.execute("""
        SELECT fetch_method, COUNT(*) FROM episodic
        WHERE fetch_method IS NOT NULL GROUP BY fetch_method
    """).fetchall()
    if fetch_rows:
        import pandas as pd
        fetch_map = {r[0]: r[1] for r in fetch_rows}
        total_fetched = sum(fetch_map.values())
        native = fetch_map.get("transcript_api", 0)
        ytdlp = fetch_map.get("ytdlp_subtitle", 0)
        description = fetch_map.get("description_api", 0)
        unavailable = fetch_map.get("unavailable", 0)
        coverage_pct = (total_fetched - unavailable) / max(total_fetched, 1) * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Data Coverage", f"{coverage_pct:.1f}%")
        c2.metric("Native Transcripts", native, help="youtube-transcript-api")
        c3.metric("yt-dlp Fallback", ytdlp, help="Subtitle extraction")
        c4.metric("Researcher Agent", description, help="Description+tags for no-caption videos")

        import plotly.express as px
        labels = ["Native Captions", "yt-dlp Subtitles", "Researcher Agent", "Unavailable"]
        values = [native, ytdlp, description, unavailable]
        fig = px.pie(values=values, names=labels, hole=0.5,
                     color_discrete_sequence=["#00CC96", "#636EFA", "#FFA15A", "#EF553B"],
                     title="Data Lineage — How Every Video Was Covered")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("**Researcher Agent** = specialized fallback for 'dark' videos with no captions — fetches title, description, and tags via YouTube Data API v3.")

    # Triage breakdown
    triage_rows = con.execute("""
        SELECT triage_tier, COUNT(*) FROM episodic
        WHERE triage_tier IS NOT NULL GROUP BY triage_tier
    """).fetchall()
    if triage_rows:
        st.caption("**Triage Routing:**")
        for tier, count in triage_rows:
            st.write(f"  - `{tier}`: {count} videos")

    # ── REJECTION LOOP — Agentic Self-Correction ──────────────────────────────
    st.subheader("Agentic Rejection Loop — Where the System Self-Corrected")
    st.caption("Every row here is proof of agency: Auditor rejected, Orchestrator re-queued, Narrator reran.")

    rerun_rows = con.execute("""
        SELECT video_id, title, agent_log FROM episodic
        WHERE status = 'RERUN_REQUESTED'
           OR (agent_log LIKE '%RERUN_REQUESTED%' OR agent_log LIKE '%rerun%')
        ORDER BY updated_at DESC LIMIT 20
    """).fetchall()

    if rerun_rows:
        import pandas as pd
        rerun_display = []
        for video_id, title, log_json in rerun_rows:
            log = json.loads(log_json) if log_json else []
            rerun_entry = next((e for e in log if "rerun" in e.get("action","").lower()), None)
            if rerun_entry:
                rerun_display.append({
                    "Video": (title or video_id)[:50],
                    "Agent": rerun_entry.get("agent", "auditor"),
                    "Status": "REJECTED → RERUN",
                    "Reason": rerun_entry.get("detail", "")[:80],
                })
        if rerun_display:
            st.dataframe(pd.DataFrame(rerun_display), use_container_width=True, hide_index=True)
    else:
        st.info("Rerun events will appear here after Auditor runs. (Pipeline not yet complete.)")

    st.divider()

    # Recent agent log entries
    st.subheader("Recent Agent Decisions")
    recent = con.execute("""
        SELECT video_id, title, agent_log FROM episodic
        WHERE agent_log IS NOT NULL AND agent_log != '[]'
        ORDER BY updated_at DESC LIMIT 10
    """).fetchall()
    con.close()

    for video_id, title, log_json in recent:
        log = json.loads(log_json) if log_json else []
        if log:
            with st.expander(f"{title or video_id} — {len(log)} decisions"):
                for entry in log[-5:]:
                    st.write(
                        f"`{entry.get('agent','?')}` → **{entry.get('action','?')}**: "
                        f"{entry.get('detail','')}"
                    )

    # Adaptive config
    st.subheader("Adaptive Config (context/insights.yaml)")
    try:
        import yaml
        with open("context/insights.yaml") as f:
            config = yaml.safe_load(f)
        st.json(config.get("focus_areas", []))
        st.caption(f"Source: {config.get('source','?')} | Loaded: {config.get('loaded_at','?')}")
    except Exception:
        st.caption("context/insights.yaml not loaded")

    # Day 2 callout
    st.info(
        "**Day 2 Adaptation:** Add new insights to `context/insights.yaml` under `day2_insights:`, "
        "then run `python run.py --complete-deep-dive`. The Orchestrator re-adapts the full pipeline "
        "automatically — no code changes required.",
        icon="🔄",
    )
