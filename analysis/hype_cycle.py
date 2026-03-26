"""
Hype Cycle Chart — AIM's 10-year AI term frequency timeline.

Business framing for AIM:
  "Rising topics you're undercovering — editorial opportunities."

Shows 30 AI terms tracked year-over-year, normalized by video count per year.
Peaks = hype moments. Flat = evergreen. Rising = editorial opportunity now.

Implements Prof. Snehanshu Saha's (BITS Pilani) principle:
  "Intelligence in Structure, Not Policy"
  The shape of the curve encodes insight — not just the model.
"""

import json
from collections import defaultdict

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pipeline.database import get_connection

# 30 AI terms to track (chosen for 10-year narrative arc)
WATCHLIST = [
    # Early era (2015-2018)
    "deep learning", "neural network", "machine learning", "nlp", "computer vision",
    # Hype era (2018-2021)
    "blockchain", "automl", "reinforcement learning", "gpt", "bert",
    # Transition (2020-2022)
    "mlops", "data science", "python", "tensorflow", "pytorch",
    # LLM era (2022-2024)
    "chatgpt", "llm", "large language model", "generative ai", "stable diffusion",
    # Agentic era (2023-2025)
    "rag", "agent", "fine-tuning", "multimodal", "vector database",
    # Current (2024-2025)
    "claude", "gemini", "mistral", "llama", "sora",
]

# Terms with known mainstream breakthrough dates (for Early Predictor)
MAINSTREAM_DATES = {
    "chatgpt": 2022,
    "llm": 2023,
    "rag": 2023,
    "agent": 2024,
    "multimodal": 2023,
    "stable diffusion": 2022,
    "reinforcement learning": 2022,
    "mlops": 2021,
    "automl": 2020,
    "blockchain": 2018,
}


def compute_hype_data() -> dict:
    """
    Returns {term: {year: normalized_frequency}} for all watchlist terms.
    Normalized by number of videos that year to avoid 2025 dominating.
    """
    con = get_connection()

    # Get all transcripts with year
    rows = con.execute("""
        SELECT year, transcript FROM episodic
        WHERE year IS NOT NULL
          AND transcript IS NOT NULL
          AND triage_tier != 'skip'
        ORDER BY year
    """).fetchall()

    # Video count per year for normalization
    year_counts = con.execute("""
        SELECT year, COUNT(*) FROM episodic
        WHERE year IS NOT NULL AND triage_tier != 'skip'
        GROUP BY year
    """).fetchall()
    videos_per_year = {r[0]: r[1] for r in year_counts}

    con.close()

    # Count term mentions per year
    term_year_counts = defaultdict(lambda: defaultdict(int))

    for year, transcript in rows:
        text_lower = transcript.lower()
        for term in WATCHLIST:
            if term in text_lower:
                term_year_counts[term][year] += 1

    # Normalize by video count
    result = {}
    years = sorted(videos_per_year.keys())

    for term in WATCHLIST:
        result[term] = {}
        for year in years:
            count = term_year_counts[term].get(year, 0)
            total = videos_per_year.get(year, 1)
            result[term][year] = round(count / total, 4)

    return result, years


def find_first_mentions() -> dict:
    """Find the first year AIM mentioned each tracked term."""
    con = get_connection()
    rows = con.execute("""
        SELECT year, transcript FROM episodic
        WHERE year IS NOT NULL AND transcript IS NOT NULL
        ORDER BY year ASC
    """).fetchall()
    con.close()

    first_mention = {}
    for year, transcript in rows:
        text_lower = transcript.lower()
        for term in WATCHLIST:
            if term not in first_mention and term in text_lower:
                first_mention[term] = year

    return first_mention


def build_chart(output_path: str = "data/hype_cycle.html") -> go.Figure:
    """Build the interactive Hype Cycle chart."""
    hype_data, years = compute_hype_data()

    # Group terms by era for color coding
    era_colors = {
        "early": "#6c757d",    # grey
        "hype": "#fd7e14",     # orange
        "llm": "#0d6efd",      # blue
        "agentic": "#198754",  # green
        "current": "#dc3545",  # red
    }

    term_eras = {
        "deep learning": "early", "neural network": "early",
        "machine learning": "early", "nlp": "early", "computer vision": "early",
        "blockchain": "hype", "automl": "hype", "reinforcement learning": "hype",
        "gpt": "hype", "bert": "hype",
        "mlops": "hype", "data science": "early", "python": "early",
        "tensorflow": "early", "pytorch": "early",
        "chatgpt": "llm", "llm": "llm", "large language model": "llm",
        "generative ai": "llm", "stable diffusion": "llm",
        "rag": "agentic", "agent": "agentic", "fine-tuning": "agentic",
        "multimodal": "agentic", "vector database": "agentic",
        "claude": "current", "gemini": "current", "mistral": "current",
        "llama": "current", "sora": "current",
    }

    fig = go.Figure()

    # Add a trace per term
    for term in WATCHLIST:
        y_vals = [hype_data[term].get(yr, 0) for yr in years]
        era = term_eras.get(term, "early")
        color = era_colors[era]

        fig.add_trace(go.Scatter(
            x=years,
            y=y_vals,
            mode="lines+markers",
            name=term,
            line=dict(color=color, width=1.5),
            marker=dict(size=4),
            hovertemplate=f"<b>{term}</b><br>Year: %{{x}}<br>Coverage: %{{y:.1%}}<extra></extra>",
        ))

    fig.update_layout(
        title={
            "text": "AIM Media House — 10-Year AI Hype Cycle<br>"
                    "<sub>Term frequency normalized by videos/year | "
                    "Rising lines = editorial opportunity</sub>",
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis=dict(title="Year", tickmode="linear", dtick=1),
        yaxis=dict(title="Coverage Rate (% of videos mentioning term)",
                   tickformat=".0%"),
        hovermode="x unified",
        legend=dict(
            orientation="v",
            x=1.01, y=1,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="lightgrey",
        ),
        height=600,
        template="plotly_white",
        annotations=[
            dict(
                text="As Prof. Snehanshu Saha (BITS Pilani) said: 'Intelligence in Structure, Not Policy'<br>"
                     "The shape of this curve encodes 10 years of AI narrative.",
                xref="paper", yref="paper",
                x=0, y=-0.15, showarrow=False,
                font=dict(size=10, color="grey"),
            )
        ]
    )

    if output_path:
        fig.write_html(output_path)
        print(f"Hype Cycle chart saved to {output_path}")

    return fig


if __name__ == "__main__":
    fig = build_chart()
    fig.show()
