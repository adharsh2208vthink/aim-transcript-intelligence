"""
Sentiment Trajectory — How AIM's tone toward AI has shifted over 10 years.

Business framing for AIM:
  "How your audience's emotional relationship with AI has evolved."
  "Use this to understand what content resonates — optimistic vs critical."

VADER sentiment aggregated by year → line chart with annotations.
Expected story: cautiously optimistic (2016) → euphoric (2022) → measured/critical (2024)
                → excited again (2025 with agentic AI)

Cross-reference with Hype Cycle: does sentiment spike when a new term first appears?
"""

import plotly.graph_objects as go

from pipeline.database import get_connection


def compute_yearly_sentiment() -> dict:
    """Returns {year: {pos, neg, neu, label, video_count}} aggregated from VADER scores."""
    con = get_connection()

    rows = con.execute("""
        SELECT year,
               AVG(sentiment_pos) as avg_pos,
               AVG(sentiment_neg) as avg_neg,
               AVG(sentiment_neu) as avg_neu,
               COUNT(*) as n,
               SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) as n_pos,
               SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) as n_neg,
               SUM(CASE WHEN sentiment_label = 'neutral'  THEN 1 ELSE 0 END) as n_neu
        FROM episodic
        WHERE year IS NOT NULL
          AND sentiment_pos IS NOT NULL
          AND triage_tier != 'skip'
        GROUP BY year
        ORDER BY year
    """).fetchall()
    con.close()

    result = {}
    for year, avg_pos, avg_neg, avg_neu, n, n_pos, n_neg, n_neu in rows:
        result[year] = {
            "pos": round(float(avg_pos or 0), 4),
            "neg": round(float(avg_neg or 0), 4),
            "neu": round(float(avg_neu or 0), 4),
            "n": n,
            "pct_positive": round(n_pos / n * 100, 1) if n > 0 else 0,
            "pct_negative": round(n_neg / n * 100, 1) if n > 0 else 0,
            "pct_neutral":  round(n_neu / n * 100, 1) if n > 0 else 0,
            # Net sentiment: pos - neg (simple compound proxy)
            "net": round(float((avg_pos or 0) - (avg_neg or 0)), 4),
        }

    return result


# Key narrative moments to annotate on the chart
NARRATIVE_ANNOTATIONS = {
    2017: "AlphaGo &<br>Deep Learning hype",
    2020: "COVID accelerates<br>digital AI adoption",
    2022: "ChatGPT launch:<br>peak optimism",
    2023: "LLM reality check:<br>costs, hallucinations",
    2025: "Agentic AI era:<br>measured excitement",
}


def get_inflection_points() -> dict:
    """Pull Judge-identified Strategic Inflection Points from yearly_summaries."""
    try:
        con = get_connection()
        rows = con.execute("""
            SELECT year, judge_feedback FROM yearly_summaries
            WHERE judge_feedback IS NOT NULL
        """).fetchall()
        con.close()
        inflections = {}
        import json as _json
        for year, feedback_json in rows:
            try:
                fb = _json.loads(feedback_json)
                if fb.get("is_inflection_point"):
                    inflections[year] = fb.get("narrative_pivot", "Strategic Inflection Point")
            except Exception:
                pass
        return inflections
    except Exception:
        return {}


def build_chart(output_path: str = "data/sentiment_trajectory.html") -> go.Figure:
    """Build the Sentiment Trajectory chart."""
    data = compute_yearly_sentiment()

    if not data:
        print("No sentiment data available yet (run Analyst agent first).")
        return None

    years = sorted(data.keys())
    pos_vals = [data[y]["pos"] for y in years]
    neg_vals = [data[y]["neg"] for y in years]
    net_vals = [data[y]["net"] for y in years]
    pct_pos  = [data[y]["pct_positive"] for y in years]
    pct_neg  = [data[y]["pct_negative"] for y in years]

    fig = go.Figure()

    # Net sentiment line (primary)
    fig.add_trace(go.Scatter(
        x=years, y=net_vals,
        mode="lines+markers",
        name="Net Sentiment (Positive − Negative)",
        line=dict(color="#0d6efd", width=3),
        marker=dict(size=8),
        hovertemplate="<b>%{x}</b><br>Net sentiment: %{y:.3f}<extra></extra>",
    ))

    # Positive area
    fig.add_trace(go.Scatter(
        x=years, y=pos_vals,
        mode="lines",
        name="Avg Positive Score",
        line=dict(color="#198754", width=1.5, dash="dot"),
        fill="tozeroy",
        fillcolor="rgba(25,135,84,0.1)",
        hovertemplate="<b>%{x}</b><br>Positive: %{y:.3f}<extra></extra>",
    ))

    # Negative area
    fig.add_trace(go.Scatter(
        x=years, y=[-v for v in neg_vals],
        mode="lines",
        name="Avg Negative Score (inverted)",
        line=dict(color="#dc3545", width=1.5, dash="dot"),
        fill="tozeroy",
        fillcolor="rgba(220,53,69,0.1)",
        hovertemplate="<b>%{x}</b><br>Negative: %{y:.3f}<extra></extra>",
    ))

    # Zero line
    fig.add_hline(y=0, line_dash="dash", line_color="lightgrey")

    # Strategic Inflection Points from Judge (red vertical lines)
    inflections = get_inflection_points()
    for year, pivot_text in inflections.items():
        if year in data:
            fig.add_vline(
                x=year,
                line_dash="dash",
                line_color="red",
                line_width=2,
                annotation=None,
            )

    # Narrative annotations
    for year, note in NARRATIVE_ANNOTATIONS.items():
        if year in data:
            fig.add_annotation(
                x=year, y=net_vals[years.index(year)],
                text=note,
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowcolor="#6c757d",
                ax=0, ay=-40,
                font=dict(size=9, color="#495057"),
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="#dee2e6",
                borderwidth=1,
            )

    fig.update_layout(
        title={
            "text": "AIM Media House — Sentiment Trajectory 2015–2025<br>"
                    "<sub>VADER sentiment aggregated across all videos by year | "
                    "Blue line = net sentiment (positive − negative)</sub>",
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis=dict(title="Year", tickmode="linear", dtick=1),
        yaxis=dict(title="VADER Sentiment Score"),
        height=550,
        margin=dict(b=100, t=120),
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="right", x=1),
        annotations=list(fig.layout.annotations) + [
            dict(
                text="Powered by VADER sentiment analysis (free, local). "
                     "Ran on all 3,173 transcripts without API cost.",
                xref="paper", yref="paper",
                x=0, y=-0.22, showarrow=False,
                font=dict(size=10, color="grey"),
            )
        ]
    )

    if output_path:
        fig.write_html(output_path)
        print(f"Sentiment Trajectory chart saved to {output_path}")

    return fig


if __name__ == "__main__":
    fig = build_chart()
    if fig:
        fig.show()
