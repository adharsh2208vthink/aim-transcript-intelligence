"""
Hype vs Reality Quadrant — What your audience watches vs what you produce.

Business framing for AIM:
  "What gets watched vs what you produce — the gap is your opportunity."
  "Use this for sponsorship targeting: top-right quadrant = sponsor-ready content."

4 quadrants:
  Top-right  — Enduring Relevance  (high hype + high engagement)  → sponsor here
  Top-left   — Hidden Gem          (low hype + high engagement)    → undercover winners
  Bottom-right — Overhyped         (high hype + low engagement)    → covered too much
  Bottom-left  — Fading Fast       (low hype + low engagement)     → drop these

X-axis: mention frequency across all videos (normalized) = HYPE
Y-axis: average view count for videos mentioning the term = REALITY / ENGAGEMENT
"""

import json
from collections import defaultdict

import plotly.graph_objects as go
import plotly.express as px

from pipeline.database import get_connection
from analysis.hype_cycle import WATCHLIST


def compute_quadrant_data() -> list[dict]:
    """Compute hype (frequency) vs reality (engagement) per term."""
    con = get_connection()

    rows = con.execute("""
        SELECT transcript, view_count, year
        FROM episodic
        WHERE transcript IS NOT NULL
          AND triage_tier != 'skip'
    """).fetchall()
    con.close()

    total_videos = len(rows)
    term_videos = defaultdict(int)
    term_total_views = defaultdict(int)

    for transcript, view_count, year in rows:
        if not transcript:
            continue
        text_lower = transcript.lower()
        views = view_count or 0

        for term in WATCHLIST:
            if term in text_lower:
                term_videos[term] += 1
                term_total_views[term] += views

    result = []
    for term in WATCHLIST:
        count = term_videos.get(term, 0)
        if count == 0:
            continue
        hype = count / total_videos
        avg_views = term_total_views[term] / count if count > 0 else 0
        result.append({
            "term": term,
            "hype": hype,
            "avg_views": avg_views,
            "video_count": count,
        })

    return result


def build_chart(output_path: str = "data/hype_reality.html") -> go.Figure:
    """Build the Hype vs Reality quadrant chart."""
    data = compute_quadrant_data()
    if not data:
        print("No data available yet.")
        return None

    terms = [d["term"] for d in data]
    hype = [d["hype"] for d in data]
    avg_views = [d["avg_views"] for d in data]
    counts = [d["video_count"] for d in data]

    median_hype = sorted(hype)[len(hype)//2]
    median_views = sorted(avg_views)[len(avg_views)//2]

    # Quadrant labels
    def quadrant(h, v):
        if h >= median_hype and v >= median_views:
            return "Enduring Relevance"
        elif h < median_hype and v >= median_views:
            return "Hidden Gem"
        elif h >= median_hype and v < median_views:
            return "Overhyped"
        else:
            return "Fading Fast"

    quadrants = [quadrant(h, v) for h, v in zip(hype, avg_views)]
    quad_colors = {
        "Enduring Relevance": "#198754",
        "Hidden Gem": "#0d6efd",
        "Overhyped": "#fd7e14",
        "Fading Fast": "#6c757d",
    }
    colors = [quad_colors[q] for q in quadrants]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=hype,
        y=avg_views,
        mode="markers+text",
        text=terms,
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(
            color=colors,
            size=[8 + c // 10 for c in counts],  # size by video count
            opacity=0.8,
            line=dict(width=1, color="white"),
        ),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Coverage rate: %{x:.1%}<br>"
            "Avg views: %{y:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    # Quadrant dividers
    fig.add_vline(x=median_hype, line_dash="dash", line_color="lightgrey", opacity=0.7)
    fig.add_hline(y=median_views, line_dash="dash", line_color="lightgrey", opacity=0.7)

    # Quadrant labels
    x_max = max(hype) * 1.05
    y_max = max(avg_views) * 1.1
    label_style = dict(xref="x", yref="y", showarrow=False,
                       font=dict(size=11, color="grey"), opacity=0.6)

    fig.add_annotation(text="ENDURING RELEVANCE<br>(sponsor here)", bgcolor="rgba(25,135,84,0.1)",
                       x=x_max * 0.75, y=y_max * 0.9, **label_style)
    fig.add_annotation(text="HIDDEN GEM<br>(double down)", bgcolor="rgba(13,110,253,0.1)",
                       x=median_hype * 0.3, y=y_max * 0.9, **label_style)
    fig.add_annotation(text="OVERHYPED<br>(reduce coverage)", bgcolor="rgba(253,126,20,0.1)",
                       x=x_max * 0.75, y=median_views * 0.2, **label_style)
    fig.add_annotation(text="FADING FAST<br>(phase out)", bgcolor="rgba(108,117,125,0.1)",
                       x=median_hype * 0.3, y=median_views * 0.2, **label_style)

    fig.update_layout(
        title={
            "text": "AIM Content: Hype vs Reality<br>"
                    "<sub>X = coverage frequency | Y = average views | "
                    "Bubble size = number of videos</sub>",
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis=dict(title="Coverage Rate (Hype)", tickformat=".0%"),
        yaxis=dict(title="Avg Views per Video (Reality / Audience Engagement)"),
        height=600,
        template="plotly_white",
        annotations=[a for a in fig.layout.annotations] + [
            dict(
                text="<b>Top-right quadrant = Enduring Relevance.</b> "
                     "These topics have both editorial credibility and proven audience. "
                     "This is your sponsorship sweet spot.",
                xref="paper", yref="paper",
                x=0, y=-0.13, showarrow=False,
                font=dict(size=10, color="#198754"),
            )
        ]
    )

    if output_path:
        fig.write_html(output_path)
        print(f"Hype vs Reality chart saved to {output_path}")

    return fig


if __name__ == "__main__":
    fig = build_chart()
    if fig:
        fig.show()
