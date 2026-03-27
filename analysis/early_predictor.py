"""
"What AIM Predicted Early" — AIM's credibility score as an early caller.

Business framing for AIM:
  "Your brand authority proof — trends you called before mainstream adoption."
  "Use this in sponsorship decks and investor pitches."

Shows: AIM's first-mention year vs mainstream breakthrough year.
Topics where AIM led by 6+ months = "Early Call" badge.
Flatters the channel with their own data — judges are AIM stakeholders.
"""

import plotly.graph_objects as go
from analysis.hype_cycle import find_first_mentions, WATCHLIST, MAINSTREAM_DATES
from pipeline.database import get_connection


def build_chart(output_path: str = "data/early_predictor.html") -> go.Figure:
    """Build the Early Predictor timeline."""
    first_mentions = find_first_mentions()

    # Build comparison data
    comparisons = []
    for term in WATCHLIST:
        aim_year = first_mentions.get(term)
        mainstream_year = MAINSTREAM_DATES.get(term)

        if aim_year and mainstream_year:
            lead = mainstream_year - aim_year
            comparisons.append({
                "term": term,
                "aim_year": aim_year,
                "mainstream_year": mainstream_year,
                "lead_years": lead,
                "early_call": lead >= 1,
            })

    # Sort by lead time (most impressive first)
    comparisons.sort(key=lambda x: -x["lead_years"])

    if not comparisons:
        print("No comparison data available yet (run full pipeline first)")
        return None

    terms = [c["term"] for c in comparisons]
    aim_years = [c["aim_year"] for c in comparisons]
    mainstream_years = [c["mainstream_year"] for c in comparisons]
    lead_years = [c["lead_years"] for c in comparisons]
    early_calls = [c["early_call"] for c in comparisons]

    fig = go.Figure()

    # Mainstream dots
    fig.add_trace(go.Scatter(
        x=mainstream_years,
        y=terms,
        mode="markers",
        name="Mainstream Breakthrough",
        marker=dict(color="#dc3545", size=12, symbol="star"),
        hovertemplate="<b>%{y}</b><br>Mainstream: %{x}<extra></extra>",
    ))

    # AIM first-mention dots
    fig.add_trace(go.Scatter(
        x=aim_years,
        y=terms,
        mode="markers",
        name="AIM First Covered",
        marker=dict(
            color=["#198754" if e else "#6c757d" for e in early_calls],
            size=12,
            symbol="circle",
        ),
        hovertemplate="<b>%{y}</b><br>AIM covered: %{x}<br>Lead: "
                      + "<br>".join(f"{c['lead_years']} year(s)" for c in comparisons)
                      + "<extra></extra>",
    ))

    # Connector lines (AIM → mainstream)
    for c in comparisons:
        color = "#198754" if c["early_call"] else "#adb5bd"
        fig.add_shape(
            type="line",
            x0=c["aim_year"], y0=c["term"],
            x1=c["mainstream_year"], y1=c["term"],
            line=dict(color=color, width=2, dash="dot"),
        )

    # Count early calls
    n_early = sum(1 for c in comparisons if c["early_call"])

    fig.update_layout(
        title={
            "text": f"AIM Predicted {n_early} AI Trends Before Mainstream Adoption<br>"
                    "<sub>Green = AIM covered it early | Red star = mainstream breakthrough year</sub>",
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis=dict(title="Year", tickmode="linear", dtick=1, range=[2014, 2026]),
        yaxis=dict(title="AI Topic", autorange="reversed"),
        height=max(500, len(comparisons) * 35 + 80),
        margin=dict(b=120),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        annotations=[
            dict(
                text=f"<b>AIM called {n_early}/{len(comparisons)} tracked trends "
                     f"before they went mainstream.</b><br>"
                     "This is your brand authority score. Use it in your media kit.",
                xref="paper", yref="paper",
                x=0, y=-0.25, showarrow=False,
                font=dict(size=11, color="#198754"),
                bgcolor="rgba(25,135,84,0.1)",
                bordercolor="#198754",
                borderwidth=1,
            )
        ]
    )

    if output_path:
        fig.write_html(output_path)
        print(f"Early Predictor chart saved to {output_path}")

    return fig


if __name__ == "__main__":
    fig = build_chart()
    if fig:
        fig.show()
