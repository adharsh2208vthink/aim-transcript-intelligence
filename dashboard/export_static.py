"""
Export all dashboard charts + yearly syntheses as a single standalone HTML file.
No server needed — judges open this file in any browser.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from pipeline.database import get_connection
from analysis.hype_cycle import build_chart as build_hype_chart
from analysis.early_predictor import build_chart as build_early_chart
from analysis.hype_reality import build_chart as build_reality_chart
from analysis.sentiment_trajectory import build_chart as build_sentiment_chart

OUTPUT = Path("outputs/dashboard_static.html")
OUTPUT.parent.mkdir(exist_ok=True)


def get_yearly_syntheses():
    con = get_connection()
    rows = con.execute("""
        SELECT year, video_count, judge_score, summary_final, summary_draft,
               top_topics, top_entities
        FROM yearly_summaries ORDER BY year ASC
    """).fetchall()
    con.close()
    results = []
    for year, vc, js, sf, sd, tt, te in rows:
        synthesis = sf or sd or ""
        topics = json.loads(tt) if tt else []
        entities = json.loads(te) if te else []
        results.append({
            "year": year,
            "video_count": vc or 0,
            "judge_score": js,
            "synthesis": synthesis,
            "topics": topics[:8],
            "entities": entities[:8],
        })
    return results


def get_pipeline_stats():
    con = get_connection()
    total = con.execute("SELECT COUNT(*) FROM episodic").fetchone()[0]
    cost_gemini = con.execute("SELECT COALESCE(SUM(cost_gemini), 0) FROM episodic").fetchone()[0]
    cost_claude_ep = con.execute("SELECT COALESCE(SUM(cost_claude), 0) FROM episodic").fetchone()[0]
    cost_claude_ys = con.execute("SELECT COALESCE(SUM(cost_claude), 0) FROM yearly_summaries").fetchone()[0]
    total_cost = cost_gemini + cost_claude_ep + cost_claude_ys

    fetch_rows = con.execute("""
        SELECT fetch_method, COUNT(*) FROM episodic
        WHERE fetch_method IS NOT NULL GROUP BY fetch_method
    """).fetchall()
    fetch_map = {r[0]: r[1] for r in fetch_rows}

    status_rows = con.execute("""
        SELECT status, COUNT(*) FROM episodic GROUP BY status
    """).fetchall()
    status_map = {r[0]: r[1] for r in status_rows}

    con.close()
    return {
        "total": total,
        "cost": total_cost,
        "cost_gemini": cost_gemini,
        "cost_claude": cost_claude_ep + cost_claude_ys,
        "fetch": fetch_map,
        "status": status_map,
    }


def build_all():
    print("Building static dashboard...")

    # Generate all charts
    charts = {}
    for name, builder in [
        ("hype_cycle", build_hype_chart),
        ("early_predictor", build_early_chart),
        ("hype_reality", build_reality_chart),
        ("sentiment", build_sentiment_chart),
    ]:
        try:
            fig = builder(output_path=None)
            if fig:
                charts[name] = fig.to_html(full_html=False, include_plotlyjs=False)
                print(f"  {name}: OK")
            else:
                charts[name] = f"<p>Chart not available (no data)</p>"
                print(f"  {name}: no data")
        except Exception as e:
            charts[name] = f"<p>Error: {e}</p>"
            print(f"  {name}: error - {e}")

    # Speaker network
    try:
        from analysis.speaker_network import build_network
        build_network(output_path="data/speaker_network.html")
        network_html = Path("data/speaker_network.html").read_text()
        charts["network"] = network_html
        print("  speaker_network: OK")
    except Exception as e:
        charts["network"] = f"<p>Error: {e}</p>"
        print(f"  speaker_network: error - {e}")

    syntheses = get_yearly_syntheses()
    stats = get_pipeline_stats()

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIM Content Intelligence Dashboard</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0e1117; color: #fafafa; line-height: 1.6; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
    header {{ text-align: center; padding: 40px 20px; border-bottom: 1px solid #333; }}
    header h1 {{ font-size: 2em; margin-bottom: 8px; }}
    header p {{ color: #aaa; font-size: 1.1em; }}
    .stats-bar {{ display: flex; justify-content: center; gap: 40px; margin: 20px 0; }}
    .stat {{ text-align: center; }}
    .stat .number {{ font-size: 1.8em; font-weight: bold; color: #ff4b4b; }}
    .stat .label {{ font-size: 0.85em; color: #aaa; }}
    nav {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; padding: 20px; border-bottom: 1px solid #333; }}
    nav a {{ padding: 8px 16px; background: #262730; color: #fafafa; text-decoration: none; border-radius: 6px; font-size: 0.9em; }}
    nav a:hover {{ background: #ff4b4b; }}
    section {{ padding: 40px 0; border-bottom: 1px solid #222; }}
    section h2 {{ font-size: 1.5em; margin-bottom: 8px; }}
    section .subtitle {{ color: #aaa; margin-bottom: 20px; font-size: 0.95em; }}
    .chart-container {{ background: #1a1a2e; border-radius: 8px; padding: 10px; margin: 20px 0; }}
    .network-frame {{ width: 100%; height: 700px; border: none; border-radius: 8px; }}
    .year-card {{ background: #1a1a2e; border-radius: 8px; padding: 24px; margin: 20px 0; }}
    .year-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
    .year-header h3 {{ font-size: 1.3em; }}
    .badge {{ background: #ff4b4b; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; }}
    .tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }}
    .tag {{ background: #262730; padding: 3px 10px; border-radius: 4px; font-size: 0.8em; color: #ccc; }}
    .synthesis {{ color: #ddd; white-space: pre-wrap; }}
    .data-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
    .data-table th, .data-table td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }}
    .data-table th {{ color: #aaa; font-weight: 600; font-size: 0.85em; text-transform: uppercase; }}
    footer {{ text-align: center; padding: 30px; color: #666; font-size: 0.85em; }}
</style>
</head>
<body>

<header>
    <h1>AIM Media House | Content Intelligence Dashboard</h1>
    <p>10 years. {stats['total']:,} videos. Transformed into editorial, sponsorship & brand intelligence.</p>
    <div class="stats-bar">
        <div class="stat"><div class="number">{stats['total']:,}</div><div class="label">Videos Analyzed</div></div>
        <div class="stat"><div class="number">${stats['cost']:.2f}</div><div class="label">Total LLM Cost</div></div>
        <div class="stat"><div class="number">{len(syntheses)}</div><div class="label">Yearly Reports</div></div>
        <div class="stat"><div class="number">7</div><div class="label">AI Agents</div></div>
    </div>
</header>

<nav>
    <a href="#hype-cycle">Hype Cycle</a>
    <a href="#speaker-network">Speaker Network</a>
    <a href="#early-predictor">AIM Predicted Early</a>
    <a href="#hype-reality">Hype vs Reality</a>
    <a href="#sentiment">Sentiment Trajectory</a>
    <a href="#syntheses">Yearly Syntheses</a>
    <a href="#pipeline">Pipeline Status</a>
</nav>

<div class="container">

<section id="hype-cycle">
    <h2>AI Topic Hype Cycle</h2>
    <p class="subtitle">Rising lines = topics AIM is undercovering. Peaks = hype moments. Flat = evergreen content.</p>
    <div class="chart-container">{charts.get('hype_cycle', '<p>No data</p>')}</div>
</section>

<section id="speaker-network">
    <h2>Speaker & Brand Network</h2>
    <p class="subtitle">Larger nodes = most mentioned people and orgs. Connected clusters = natural co-occurrence.</p>
    <div class="chart-container">
        <iframe srcdoc='{charts.get("network", "").replace(chr(39), "&#39;")}' class="network-frame"></iframe>
    </div>
</section>

<section id="early-predictor">
    <h2>What AIM Predicted Early</h2>
    <p class="subtitle">AIM covered these AI trends before mainstream adoption. Credibility proof for the media kit.</p>
    <div class="chart-container">{charts.get('early_predictor', '<p>No data</p>')}</div>
</section>

<section id="hype-reality">
    <h2>Hype vs Reality</h2>
    <p class="subtitle">Top-right = Enduring Relevance. High coverage AND high views. Where sponsors get ROI.</p>
    <div class="chart-container">{charts.get('hype_reality', '<p>No data</p>')}</div>
</section>

<section id="sentiment">
    <h2>Sentiment Trajectory</h2>
    <p class="subtitle">How AI conversations on AIM have shifted from optimistic to critical over 10 years.</p>
    <div class="chart-container">{charts.get('sentiment', '<p>No data</p>')}</div>
</section>

<section id="syntheses">
    <h2>10-Year Annual Intelligence Reports</h2>
    <p class="subtitle">Generated by Claude Sonnet from aggregated video data. Audited and Judge-scored.</p>
"""

    for s in syntheses:
        score_badge = f'{s["judge_score"]:.1f}/10' if s["judge_score"] else "Pending"
        topics_html = "".join(f'<span class="tag">{t}</span>' for t in s["topics"])
        entities_html = "".join(f'<span class="tag">{e}</span>' for e in s["entities"])
        paragraphs = s["synthesis"].replace("\n\n", "</p><p>") if s["synthesis"] else "<em>Not yet generated</em>"

        html += f"""
    <div class="year-card">
        <div class="year-header">
            <h3>{s['year']}</h3>
            <div>
                <span class="badge">{s['video_count']} videos</span>
                <span class="badge">Score: {score_badge}</span>
            </div>
        </div>
        <div class="tags">{topics_html}{entities_html}</div>
        <div class="synthesis"><p>{paragraphs}</p></div>
    </div>
"""

    # Pipeline status
    fetch = stats["fetch"]
    total_fetched = sum(fetch.values())
    unavailable = fetch.get("unavailable", 0)
    coverage = (total_fetched - unavailable) / max(total_fetched, 1) * 100

    html += f"""
</section>

<section id="pipeline">
    <h2>Pipeline Status</h2>
    <p class="subtitle">Data coverage and agent processing summary.</p>
    <table class="data-table">
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Total Videos</td><td>{stats['total']:,}</td></tr>
        <tr><td>Data Coverage</td><td>{coverage:.1f}%</td></tr>
        <tr><td>Native Transcripts</td><td>{fetch.get('transcript_api', 0):,}</td></tr>
        <tr><td>yt-dlp Fallback</td><td>{fetch.get('ytdlp_subtitle', 0):,}</td></tr>
        <tr><td>Researcher Agent</td><td>{fetch.get('description_api', 0):,}</td></tr>
        <tr><td>Unavailable</td><td>{unavailable:,}</td></tr>
        <tr><td>Gemini Cost</td><td>${stats['cost_gemini']:.2f}</td></tr>
        <tr><td>Claude Cost</td><td>${stats['cost_claude']:.2f}</td></tr>
        <tr><td>Total Cost</td><td>${stats['cost']:.2f}</td></tr>
    </table>
</section>

</div>

<footer>
    AIM Transcript Intelligence | MLDS 2026 Hackathon | Built during the conference it analyzes.
</footer>

</body>
</html>"""

    OUTPUT.write_text(html, encoding="utf-8")
    print(f"\nStatic dashboard saved to: {OUTPUT}")
    print(f"File size: {OUTPUT.stat().st_size / 1024:.0f} KB")
    print("Open in any browser — no server needed.")


if __name__ == "__main__":
    build_all()
