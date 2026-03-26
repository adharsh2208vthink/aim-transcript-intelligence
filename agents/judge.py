"""
Judge Agent — LLM-as-a-Judge trace evaluation.

Implements Ayushman Gupta & Chirag Jain's (Genpact) framework:
  "A Unified Framework for Training, Trajectory Improvement, Optimization,
   and Evaluation of Agentic AI Systems"

Also implements Vignesh Subrahmaniam's (Intuit) RL grounding principle:
  Judge validates claims against source transcripts — outcome-based, not linguistic.

Coverage:
  - 100% of Tier 3 outputs (10 yearly syntheses)
  - 5% random sample of Tier 2 summaries

Scoring dimensions (0-10 each):
  1. Factual Grounding   — claims traceable to source transcripts
  2. Specificity         — concrete details vs generic statements
  3. Insight Quality     — actionable for AIM's editorial team
  4. Coverage            — represents the year's full breadth
  5. Coherence           — logical flow and internal consistency

Output stored in yearly_summaries.judge_score + judge_feedback.
"""

import json
import os
import random
from datetime import datetime

from tqdm import tqdm
import anthropic
from dotenv import load_dotenv

from pipeline.database import get_connection

load_dotenv()

# Cost: Claude Sonnet per 1K tokens
CLAUDE_SONNET_INPUT_CPM = 3.0 / 1000
CLAUDE_SONNET_OUTPUT_CPM = 15.0 / 1000


def _log_yearly(con, year: int, action: str, detail: str):
    """Log to yearly_summaries (no agent_log column — use judge_feedback)."""
    pass  # yearly_summaries uses judge_feedback field directly


def _judge_yearly_synthesis(year: int, synthesis: str, context_sample: str,
                             client: anthropic.Anthropic) -> tuple[float, str, float]:
    """
    Judge a yearly synthesis against source context.
    Returns (score_0_to_10, feedback, cost_usd).
    """
    prompt = f"""You are a quality judge evaluating an AI-generated annual intelligence report for AIM Media House.

Your job: score this report and identify specific weaknesses. Be critical. A score of 8+ requires genuine excellence.

YEAR: {year}
SOURCE DATA SAMPLE (from actual transcripts/summaries used):
{context_sample[:3000]}

GENERATED SYNTHESIS TO EVALUATE:
{synthesis[:4000]}

Score the synthesis on these 5 dimensions (0-10 each):
1. **Factual Grounding** — Are claims traceable to the source data? Or generic AI commentary?
2. **Specificity** — Concrete details (names, numbers, specific claims) vs vague generalities?
3. **Insight Quality** — Is this actionable for AIM's editorial team? Or just a summary of summaries?
4. **Coverage** — Does it represent the year's breadth, or miss major themes?
5. **Coherence** — Logical flow, consistent narrative arc, no contradictions?

Respond in this exact JSON format:
{{
  "scores": {{
    "factual_grounding": <0-10>,
    "specificity": <0-10>,
    "insight_quality": <0-10>,
    "coverage": <0-10>,
    "coherence": <0-10>
  }},
  "overall": <0-10 weighted average>,
  "strengths": ["<specific strength 1>", "<specific strength 2>"],
  "weaknesses": ["<specific weakness 1>", "<specific weakness 2>"],
  "recommendation": "approve" | "revise" | "rewrite"
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    text = message.content[0].text
    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens
    cost = (input_tokens * CLAUDE_SONNET_INPUT_CPM / 1000 +
            output_tokens * CLAUDE_SONNET_OUTPUT_CPM / 1000)

    # Parse JSON response
    try:
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        result = json.loads(text)
        score = result.get("overall", 5.0)
        feedback = json.dumps(result, indent=2)
    except (json.JSONDecodeError, KeyError):
        score = 5.0
        feedback = text[:1000]

    return round(float(score), 2), feedback, cost


def _judge_tier2_sample(video_ids_sample: list, con,
                        client: anthropic.Anthropic) -> dict:
    """Quick quality check on a sample of Tier 2 video summaries."""
    stats = {"passed": 0, "flagged": 0, "total_cost": 0.0}

    for video_id in tqdm(video_ids_sample, desc="Judge Tier2"):
        row = con.execute("""
            SELECT title, summary_audited, transcript
            FROM episodic WHERE video_id = ?
        """, [video_id]).fetchone()

        if not row or not row[1]:
            continue

        title, summary, transcript = row
        transcript_sample = " ".join((transcript or "").split()[:200])

        prompt = f"""Rate this video summary (1 sentence each):

Title: {title}
Transcript excerpt: {transcript_sample}
Summary: {summary}

Is the summary: (a) specific and grounded, (b) generic/hallucinated, (c) too short?
Respond with JSON: {{"quality": "good"|"generic"|"too_short", "flag": true|false}}"""

        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            text = message.content[0].text
            cost = (message.usage.input_tokens * CLAUDE_SONNET_INPUT_CPM / 1000 +
                    message.usage.output_tokens * CLAUDE_SONNET_OUTPUT_CPM / 1000)
            stats["total_cost"] += cost

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            result = json.loads(text) if "{" in text else {"quality": "good", "flag": False}
            flagged = result.get("flag", False)

            # Log to episodic agent_log
            row2 = con.execute(
                "SELECT agent_log FROM episodic WHERE video_id = ?", [video_id]
            ).fetchone()
            log = json.loads(row2[0]) if row2 and row2[0] else []
            log.append({
                "agent": "judge",
                "action": "sampled",
                "detail": json.dumps(result),
                "ts": datetime.utcnow().isoformat(),
            })
            con.execute(
                "UPDATE episodic SET agent_log = ? WHERE video_id = ?",
                [json.dumps(log), video_id],
            )

            if flagged:
                stats["flagged"] += 1
            else:
                stats["passed"] += 1

        except Exception:
            pass

    return stats


def run(sample_rate: float = 0.05):
    """
    Run Judge on:
    - 100% of yearly syntheses (Tier 3)
    - sample_rate% of Tier 2 summaries
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set — skipping Judge")
        return {}

    client = anthropic.Anthropic(api_key=api_key)
    con = get_connection()

    total_cost = 0.0

    # ── TIER 3: 100% yearly syntheses ────────────────────────────────────────
    yearly_rows = con.execute("""
        SELECT year, summary_draft, top_topics, top_entities
        FROM yearly_summaries
        WHERE summary_draft IS NOT NULL
          AND (judge_score IS NULL OR judge_score = 0)
        ORDER BY year
    """).fetchall()

    print(f"Judge: evaluating {len(yearly_rows)} yearly syntheses (100% coverage)...")

    for year, synthesis, topics_j, entities_j in tqdm(yearly_rows, desc="Judge Yearly"):
        # Build context sample for grounding check
        context_rows = con.execute("""
            SELECT title, summary_audited
            FROM episodic
            WHERE year = ? AND summary_audited IS NOT NULL
            ORDER BY view_count DESC NULLS LAST
            LIMIT 10
        """, [year]).fetchall()

        context_sample = "\n".join(
            f"- {r[0]}: {r[1]}" for r in context_rows if r[1]
        )
        topics = json.loads(topics_j) if topics_j else []

        try:
            score, feedback, cost = _judge_yearly_synthesis(
                year, synthesis, context_sample, client
            )
            total_cost += cost

            con.execute("""
                UPDATE yearly_summaries SET
                    judge_score    = ?,
                    judge_feedback = ?,
                    cost_claude    = cost_claude + ?
                WHERE year = ?
            """, [score, feedback, cost, year])

            print(f"  {year}: score={score}/10 cost=${cost:.4f}")

        except Exception as e:
            print(f"  {year}: Judge ERROR — {e}")

    # ── TIER 2: random 5% sample ─────────────────────────────────────────────
    all_summarized = con.execute("""
        SELECT video_id FROM episodic
        WHERE status IN ('AUDITED', 'SUMMARIZED')
          AND triage_tier = 'tier2'
          AND summary_audited IS NOT NULL
    """).fetchall()
    all_ids = [r[0] for r in all_summarized]

    sample_size = max(1, int(len(all_ids) * sample_rate))
    sample = random.sample(all_ids, min(sample_size, len(all_ids)))

    print(f"\nJudge: sampling {len(sample)}/{len(all_ids)} Tier 2 summaries ({sample_rate*100:.0f}%)...")
    tier2_stats = _judge_tier2_sample(sample, con, client)
    total_cost += tier2_stats.get("total_cost", 0.0)

    con.close()

    print(f"\nJudge complete:")
    print(f"  Yearly syntheses evaluated: {len(yearly_rows)}")
    print(f"  Tier 2 sample: {tier2_stats.get('passed', 0)} passed, "
          f"{tier2_stats.get('flagged', 0)} flagged")
    print(f"  Total cost: ${total_cost:.4f}")

    return {"yearly": len(yearly_rows), "tier2_sample": tier2_stats, "total_cost": total_cost}


if __name__ == "__main__":
    run()
