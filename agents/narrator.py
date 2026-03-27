"""
Narrator Agent — LLM-powered summarization at two tiers.

Tier 2 (Gemini Flash): 1-paragraph summary per video
  - Only for triage_tier = 'tier2' videos
  - Respects Gemini free-tier rate limits (15 RPM)
  - Batch-processes with exponential backoff

Tier 3 (Claude Sonnet): 1000-word yearly synthesis
  - Groups videos by year (2015–2025)
  - Builds structured context: top summaries + entities + sentiment + topics
  - Produces 10 × 1000-word reports stored in yearly_summaries table

Logs cost estimates to episodic (cost_gemini, cost_claude).
"""

import json
import time
import os
from datetime import datetime
from collections import defaultdict, Counter

from tqdm import tqdm
import google.generativeai as genai
import anthropic
from dotenv import load_dotenv

from pipeline.database import get_connection

load_dotenv()

# Cost estimates (USD per 1M tokens)
GEMINI_FLASH_INPUT_CPM  = 0.075 / 1000   # $0.075 per 1M input tokens → per 1K
GEMINI_FLASH_OUTPUT_CPM = 0.30 / 1000
CLAUDE_SONNET_INPUT_CPM = 3.0 / 1000
CLAUDE_SONNET_OUTPUT_CPM = 15.0 / 1000

GEMINI_RPM = 15          # free-tier rate limit
GEMINI_DELAY = 60 / GEMINI_RPM  # 4 seconds between calls


def _log(con, video_id: str, action: str, detail: str):
    row = con.execute(
        "SELECT agent_log FROM episodic WHERE video_id = ?", [video_id]
    ).fetchone()
    log = json.loads(row[0]) if row and row[0] else []
    log.append({
        "agent": "narrator",
        "action": action,
        "detail": detail,
        "ts": datetime.utcnow().isoformat(),
    })
    con.execute(
        "UPDATE episodic SET agent_log = ? WHERE video_id = ?",
        [json.dumps(log), video_id],
    )


# ── TIER 2: GEMINI FLASH VIDEO SUMMARIES ─────────────────────────────────────

def _gemini_summarize(title: str, transcript: str, topics: list, model) -> str:
    """Single video summary via Gemini Flash."""
    topic_str = ", ".join(topics[:5]) if topics else "AI/ML"
    # Truncate transcript to ~3000 words to stay within context
    words = transcript.split()
    truncated = " ".join(words[:3000])

    prompt = f"""You are summarizing a video from AIM Media House, an AI/ML media channel.

Video title: {title}
Key topics: {topic_str}

Transcript (may be truncated):
{truncated}

Write a concise 2-3 sentence summary that captures:
1. The main subject or guest discussed
2. The key insight or takeaway
3. Why this matters for the AI/ML community

Be specific. Avoid generic phrases like "this video discusses...". Start directly with the substance."""

    response = model.generate_content(prompt)
    return response.text.strip()


def run_tier2(limit: int = None):
    """Summarize all tier2 ANALYZED videos using Gemini Flash."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not set — skipping Tier 2 summaries")
        return {}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    con = get_connection()
    query = """
        SELECT video_id, title, transcript, topics
        FROM episodic
        WHERE status = 'ANALYZED'
          AND triage_tier = 'tier2'
          AND transcript IS NOT NULL
          AND summary_tier2 IS NULL
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = con.execute(query).fetchall()

    print(f"Narrator Tier2: summarizing {len(rows)} videos via Gemini Flash...")

    stats = {"success": 0, "errors": 0, "total_cost": 0.0}

    for video_id, title, transcript, topics_json in tqdm(rows, desc="Gemini"):
        topics = json.loads(topics_json) if topics_json else []
        retries = 0

        while retries < 3:
            try:
                summary = _gemini_summarize(title or "", transcript, topics, model)

                # Rough token estimate: 4 chars per token
                input_tokens = len(f"{title}{transcript}"[:12000]) / 4
                output_tokens = len(summary) / 4
                cost = (input_tokens * GEMINI_FLASH_INPUT_CPM / 1000 +
                        output_tokens * GEMINI_FLASH_OUTPUT_CPM / 1000)

                con.execute("""
                    UPDATE episodic SET
                        summary_tier2 = ?,
                        cost_gemini   = cost_gemini + ?,
                        status        = 'SUMMARIZED',
                        updated_at    = CURRENT_TIMESTAMP
                    WHERE video_id = ?
                """, [summary, cost, video_id])

                _log(con, video_id, "summarized_tier2", f"cost=${cost:.5f}")
                stats["success"] += 1
                stats["total_cost"] += cost
                break

            except Exception as e:
                retries += 1
                if "429" in str(e) or "quota" in str(e).lower():
                    wait = 60 * retries
                    print(f"\n  Rate limited — waiting {wait}s...")
                    time.sleep(wait)
                else:
                    _log(con, video_id, "gemini_error", str(e)[:100])
                    stats["errors"] += 1
                    break

        time.sleep(GEMINI_DELAY)

    con.close()
    print(f"\nTier 2 complete: {stats['success']} summaries, "
          f"errors={stats['errors']}, cost=${stats['total_cost']:.4f}")
    return stats


# ── TIER 3: CLAUDE SONNET YEARLY SYNTHESIS ───────────────────────────────────

def _build_year_context(year: int, con) -> str:
    """
    Build structured context for a year's worth of videos.
    Uses: top summaries (by view_count) + entity aggregates + sentiment + topics.
    """
    rows = con.execute("""
        SELECT title, view_count, summary_tier2, summary_audited,
               topics, entities_person, entities_org, entities_tech,
               sentiment_label, triage_tier, transcript_len
        FROM episodic
        WHERE year = ?
          AND status IN ('SUMMARIZED', 'ANALYZED', 'AUDITED')
          AND triage_tier != 'skip'
        ORDER BY view_count DESC NULLS LAST
    """, [year]).fetchall()

    if not rows:
        return ""

    total_videos = len(rows)

    # Aggregate entities across the year
    all_persons = Counter()
    all_orgs = Counter()
    all_tech = Counter()
    all_topics = Counter()
    sentiment_counts = Counter()

    summaries_context = []

    for i, (title, views, sum_t2, sum_audit, topics_j,
            persons_j, orgs_j, tech_j, sent_label,
            tier, tlen) in enumerate(rows):

        summary = sum_audit or sum_t2 or ""
        if summary and i < 20:  # top 20 by views for context window
            summaries_context.append(f"- [{title}] (views: {views or 'N/A'}): {summary}")

        if topics_j:
            for t in json.loads(topics_j):
                all_topics[t] += 1
        if persons_j:
            for p in json.loads(persons_j):
                all_persons[p] += 1
        if orgs_j:
            for o in json.loads(orgs_j):
                all_orgs[o] += 1
        if tech_j:
            for t in json.loads(tech_j):
                all_tech[t] += 1
        if sent_label:
            sentiment_counts[sent_label] += 1

    top_persons = [p for p, _ in all_persons.most_common(15)]
    top_orgs    = [o for o, _ in all_orgs.most_common(15)]
    top_tech    = [t for t, _ in all_tech.most_common(20)]
    top_topics  = [t for t, _ in all_topics.most_common(15)]

    dom_sentiment = sentiment_counts.most_common(1)[0][0] if sentiment_counts else "neutral"

    context = f"""YEAR: {year}
Total videos analyzed: {total_videos}
Dominant sentiment: {dom_sentiment} ({dict(sentiment_counts)})

TOP PEOPLE MENTIONED: {', '.join(top_persons)}
TOP ORGANIZATIONS: {', '.join(top_orgs)}
TOP TOOLS & TECHNOLOGIES: {', '.join(top_tech)}
TOP TOPICS: {', '.join(top_topics)}

TOP VIDEOS BY VIEWERSHIP (with summaries):
{chr(10).join(summaries_context[:20])}
"""
    return context, {
        "top_topics": top_topics[:10],
        "top_entities": top_persons[:10] + top_tech[:10],
        "sentiment_avg": (sentiment_counts.get("positive", 0) -
                          sentiment_counts.get("negative", 0)) / max(total_videos, 1),
        "video_count": total_videos,
    }


def _claude_synthesize(year: int, context: str, client: anthropic.Anthropic) -> tuple[str, float]:
    """Generate 1000-word yearly synthesis via Claude Sonnet."""
    prompt = f"""You are writing the annual intelligence report for AIM Media House, one of India's leading AI/ML media companies. Your audience is AIM's editorial team — they want to understand what happened in AI/ML conversations on their channel this year and what it means for their content strategy.

Here is the aggregated data from {year}:

{context}

Write a comprehensive ~1000-word annual synthesis for {year} that covers:

1. **The Year in AI/ML** — What were the dominant themes? What shifted from the previous year?
2. **Key Voices** — Which speakers, researchers, or executives drove the conversation? What were their central arguments?
3. **Technology in Focus** — Which tools, frameworks, and models dominated discussions? Were any rising stars or declining hypes?
4. **Industry Signals** — What do entity mentions (companies, orgs) tell us about where the industry was heading?
5. **Audience Sentiment** — Was the tone of the year optimistic, critical, or uncertain? What drove that?
6. **Editorial Insight** — What does this year's content tell AIM about what its audience cared about? What opportunities or gaps existed?

Be specific. Use numbers where available (view counts, video counts). Avoid generic AI commentary — ground every claim in the data provided. Write in a professional but engaging editorial voice."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    text = message.content[0].text
    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens
    cost = (input_tokens * CLAUDE_SONNET_INPUT_CPM / 1000 +
            output_tokens * CLAUDE_SONNET_OUTPUT_CPM / 1000)

    return text, cost


def run_tier3(years: list = None):
    """Generate yearly syntheses for all years using Claude Sonnet."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set — skipping Tier 3 synthesis")
        return {}

    client = anthropic.Anthropic(api_key=api_key)
    con = get_connection()

    if years is None:
        result = con.execute("""
            SELECT DISTINCT year FROM episodic
            WHERE year IS NOT NULL
              AND status IN ('SUMMARIZED', 'ANALYZED', 'AUDITED')
            ORDER BY year
        """).fetchall()
        years = [r[0] for r in result]

    print(f"Narrator Tier3: synthesizing {len(years)} years via Claude Sonnet...")
    stats = {"success": 0, "errors": 0, "total_cost": 0.0}

    for year in tqdm(years, desc="Claude Yearly"):
        try:
            result = _build_year_context(year, con)
            if not result:
                print(f"  {year}: no data, skipping")
                continue

            context, meta = result
            synthesis, cost = _claude_synthesize(year, context, client)

            # Store in yearly_summaries
            con.execute("""
                INSERT INTO yearly_summaries
                    (year, video_count, summary_draft, top_topics, top_entities,
                     sentiment_avg, cost_claude)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (year) DO UPDATE SET
                    summary_draft = excluded.summary_draft,
                    video_count   = excluded.video_count,
                    top_topics    = excluded.top_topics,
                    top_entities  = excluded.top_entities,
                    sentiment_avg = excluded.sentiment_avg,
                    cost_claude   = excluded.cost_claude
            """, [
                year,
                meta["video_count"],
                synthesis,
                json.dumps(meta["top_topics"]),
                json.dumps(meta["top_entities"]),
                meta["sentiment_avg"],
                cost,
            ])

            stats["success"] += 1
            stats["total_cost"] += cost
            print(f"  {year}: ✓ (cost=${cost:.4f})")

        except Exception as e:
            print(f"  {year}: ERROR — {e}")
            stats["errors"] += 1

    con.close()
    print(f"\nTier 3 complete: {stats['success']} years, cost=${stats['total_cost']:.4f}")
    return stats


def run(limit_tier2: int = None, years: list = None, skip_tier2: bool = False):
    """Run both tiers."""
    if not skip_tier2:
        run_tier2(limit=limit_tier2)
    run_tier3(years=years)


if __name__ == "__main__":
    run()
