"""
Report Generator — Jinja2 → HTML → WeasyPrint PDF

Generates the required 10-year annual report with:
  - Cover page with key stats
  - 10 × ~1000-word yearly synthesis (from Claude Sonnet)
  - Entity tags (topics, people, tech) per year
  - Judge scores
  - MLDS speaker citations

Output:
  outputs/aim_intelligence_report.html
  outputs/aim_intelligence_report.pdf
"""

import json
from pathlib import Path
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from pipeline.database import get_connection

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

TEMPLATE_DIR = Path("report/templates")


def _get_report_data() -> dict:
    """Pull all data needed for the report from DuckDB."""
    con = get_connection()

    # Cost totals
    cost_gemini = con.execute("SELECT COALESCE(SUM(cost_gemini), 0) FROM episodic").fetchone()[0]
    cost_claude_ep = con.execute("SELECT COALESCE(SUM(cost_claude), 0) FROM episodic").fetchone()[0]
    cost_claude_ys = con.execute("SELECT COALESCE(SUM(cost_claude), 0) FROM yearly_summaries").fetchone()[0]
    total_cost = cost_gemini + cost_claude_ep + cost_claude_ys

    total_videos = con.execute("SELECT COUNT(*) FROM episodic").fetchone()[0]

    # Yearly summaries
    yearly_rows = con.execute("""
        SELECT year, video_count, summary_final, summary_draft,
               judge_score, top_topics, top_entities, sentiment_avg
        FROM yearly_summaries
        ORDER BY year ASC
    """).fetchall()

    years_data = []
    for year, video_count, summary_final, summary_draft, judge_score, \
            topics_j, entities_j, sentiment_avg in yearly_rows:

        synthesis = summary_final or summary_draft or ""
        # Split into paragraphs for HTML rendering
        paragraphs = [p.strip() for p in synthesis.split("\n\n") if p.strip()]
        if not paragraphs and synthesis:
            paragraphs = [synthesis]

        topics = json.loads(topics_j) if topics_j else []
        entities = json.loads(entities_j) if entities_j else []

        # Get NER data directly for richer display
        ner_row = con.execute("""
            SELECT
                entities_person,
                entities_org,
                entities_tech
            FROM episodic
            WHERE year = ? AND entities_person IS NOT NULL
            LIMIT 1
        """, [year]).fetchone()

        # Aggregate top persons and tech from the year
        person_rows = con.execute("""
            SELECT entities_person FROM episodic
            WHERE year = ? AND entities_person IS NOT NULL
        """, [year]).fetchall()

        from collections import Counter
        all_persons = Counter()
        all_tech = Counter()
        for (pj,) in person_rows:
            for p in (json.loads(pj) if pj else []):
                all_persons[p] += 1

        tech_rows = con.execute("""
            SELECT entities_tech FROM episodic
            WHERE year = ? AND entities_tech IS NOT NULL
        """, [year]).fetchall()
        for (tj,) in tech_rows:
            for t in (json.loads(tj) if tj else []):
                all_tech[t] += 1

        top_persons = [p for p, _ in all_persons.most_common(8)]
        top_tech = [t for t, _ in all_tech.most_common(10)]

        years_data.append({
            "year": year,
            "video_count": video_count or 0,
            "synthesis_paragraphs": paragraphs,
            "judge_score": judge_score,
            "top_topics": topics[:10],
            "top_entities": entities[:10],
            "top_persons": top_persons,
            "top_tech": top_tech,
            "sentiment_avg": sentiment_avg,
        })

    con.close()

    return {
        "total_videos": total_videos,
        "total_cost": total_cost,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "years": years_data,
    }


def generate_html(output_path: str = "outputs/aim_intelligence_report.html") -> str:
    """Render Jinja2 template → HTML file."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("yearly_report.html")

    data = _get_report_data()
    html = template.render(**data)

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"HTML report saved to {output_path}")
    return output_path


def generate_pdf(html_path: str = None,
                 output_path: str = "outputs/aim_intelligence_report.pdf") -> str:
    """Convert HTML → PDF via WeasyPrint."""
    if html_path is None:
        html_path = generate_html()

    try:
        from weasyprint import HTML
        HTML(filename=html_path).write_pdf(output_path)
        print(f"PDF report saved to {output_path}")
        return output_path
    except Exception as e:
        print(f"WeasyPrint error: {e}")
        print("HTML report is available. Install WeasyPrint dependencies to generate PDF.")
        return html_path


def run():
    print("Generating report...")
    html_path = generate_html()
    pdf_path = generate_pdf(html_path)
    print(f"\nReport generation complete:")
    print(f"  HTML: {html_path}")
    print(f"  PDF:  {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    run()
