"""
Triage Agent — Scores transcript quality and routes each video.

Routing logic (mirrors procedural rules in DuckDB):
  skip  — transcript_len < 100 words (noise/unavailable)
  tier1 — triage_score < 0.3       (low quality, local analysis only)
  tier2 — triage_score >= 0.3      (good quality, gets Gemini summary)

Score components:
  - word_count_norm  (50%) — more words = richer content
  - alpha_ratio      (30%) — ratio of real text vs timestamps/noise
  - avg_word_len     (20%) — proxy for coherence (3-10 chars = healthy)

Logs every routing decision to episodic.agent_log.
"""

import json
import re
from datetime import datetime

from tqdm import tqdm

from pipeline.database import get_connection


def _log(con, video_id: str, action: str, detail: str):
    row = con.execute(
        "SELECT agent_log FROM episodic WHERE video_id = ?", [video_id]
    ).fetchone()
    log = json.loads(row[0]) if row and row[0] else []
    log.append({
        "agent": "triage",
        "action": action,
        "detail": detail,
        "ts": datetime.utcnow().isoformat(),
    })
    con.execute(
        "UPDATE episodic SET agent_log = ? WHERE video_id = ?",
        [json.dumps(log), video_id],
    )


def _score(text: str) -> tuple[float, float, str]:
    """
    Returns (triage_score, language_score, tier).
    language_score is a proxy: ratio of ASCII alpha chars to total non-space chars.
    """
    words = text.split()
    word_count = len(words)

    if word_count < 100:
        return 0.0, 0.0, "skip"

    # Word count component (capped at 500 words for normalisation)
    word_count_norm = min(word_count / 500, 1.0)

    # Alpha ratio: how much of the text is actual letters
    non_space = re.sub(r"\s+", "", text)
    alpha_chars = sum(1 for c in non_space if c.isalpha())
    alpha_ratio = alpha_chars / max(len(non_space), 1)

    # Average word length (3–10 chars is healthy English prose)
    avg_len = sum(len(w) for w in words) / max(word_count, 1)
    avg_len_score = 1.0 if 3 <= avg_len <= 10 else 0.5

    triage_score = (
        0.5 * word_count_norm
        + 0.3 * alpha_ratio
        + 0.2 * avg_len_score
    )

    # language_score: simple ASCII proxy (English text is mostly ASCII)
    language_score = alpha_ratio

    tier = "tier2" if triage_score >= 0.3 else "tier1"
    return round(triage_score, 4), round(language_score, 4), tier


def triage_video(video_id: str, text: str, con) -> dict:
    triage_score, language_score, tier = _score(text)
    _log(con, video_id, f"routed_{tier}", f"score={triage_score} lang={language_score}")
    return {
        "triage_score": triage_score,
        "language_score": language_score,
        "triage_tier": tier,
    }


def run(limit: int = None):
    """
    Triage all FETCHED videos.
    Also handles PENDING videos with no transcript → mark skip.
    """
    con = get_connection()

    query = "SELECT video_id, transcript FROM episodic WHERE status = 'FETCHED'"
    if limit:
        query += f" LIMIT {limit}"
    rows = con.execute(query).fetchall()

    print(f"Triage: scoring {len(rows)} FETCHED videos...")

    stats = {"tier1": 0, "tier2": 0, "skip": 0}

    for video_id, transcript in tqdm(rows, desc="Triage"):
        if not transcript:
            tier = "skip"
            triage_score, language_score = 0.0, 0.0
            _log(con, video_id, "routed_skip", "no transcript")
        else:
            result = triage_video(video_id, transcript, con)
            tier = result["triage_tier"]
            triage_score = result["triage_score"]
            language_score = result["language_score"]

        stats[tier] = stats.get(tier, 0) + 1

        con.execute("""
            UPDATE episodic SET
                triage_score   = ?,
                triage_tier    = ?,
                language_score = ?,
                status         = 'TRIAGED',
                updated_at     = CURRENT_TIMESTAMP
            WHERE video_id = ?
        """, [triage_score, tier, language_score, video_id])

    con.close()

    print(f"\nTriage complete:")
    for tier, count in stats.items():
        print(f"  {tier}: {count}")
    return stats


if __name__ == "__main__":
    run()
