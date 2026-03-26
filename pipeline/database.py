"""
DuckDB Shared Blackboard — implements MathCo's 3-tier memory framework.
All agents read/write to this single store.

Tables:
  episodic  — event log per video (what happened, decisions made)
  semantic  — transcript chunks + embeddings for RAG
  procedural — runbooks, quality thresholds, adaptive rules
"""

import duckdb
import json
from pathlib import Path

DB_PATH = Path("data/channel.duckdb")


def get_connection() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def init_schema():
    con = get_connection()

    # ── EPISODIC MEMORY ──────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS episodic (
            video_id        VARCHAR PRIMARY KEY,
            title           VARCHAR,
            upload_date     VARCHAR,
            year            INTEGER,
            view_count      INTEGER,
            duration        VARCHAR,
            description     VARCHAR,
            tags            VARCHAR,          -- JSON array

            -- Pipeline status
            status          VARCHAR DEFAULT 'PENDING',
            -- PENDING → FETCHED → TRIAGED → ANALYZED → SUMMARIZED → AUDITED

            -- Transcript
            transcript      VARCHAR,
            transcript_len  INTEGER,
            fetch_method    VARCHAR,          -- transcript_api / ytdlp_subtitle / unavailable
            fetch_error     VARCHAR,

            -- Triage
            triage_score    FLOAT,
            triage_tier     VARCHAR,          -- tier1 / tier2 / skip
            language_score  FLOAT,

            -- Analysis outputs
            topics          VARCHAR,          -- JSON array of topic tags
            entities_person VARCHAR,          -- JSON array of PERSON entities
            entities_org    VARCHAR,          -- JSON array of ORG entities
            entities_tech   VARCHAR,          -- JSON array of tech/tool entities
            sentiment_pos   FLOAT,
            sentiment_neg   FLOAT,
            sentiment_neu   FLOAT,
            sentiment_label VARCHAR,          -- positive / neutral / negative

            -- LLM outputs
            summary_tier2   VARCHAR,          -- Gemini 1-paragraph summary
            summary_audited VARCHAR,          -- Auditor-approved final summary

            -- Quality tracking (Millennium Edit Distance KPI)
            rerun_count     INTEGER DEFAULT 0,
            edit_distance   FLOAT,
            agent_log       VARCHAR,          -- JSON array of agent decisions

            -- Cost tracking
            cost_gemini     FLOAT DEFAULT 0.0,
            cost_claude     FLOAT DEFAULT 0.0,

            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── SEMANTIC MEMORY ──────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS semantic (
            chunk_id        VARCHAR PRIMARY KEY,
            video_id        VARCHAR,
            year            INTEGER,
            chunk_index     INTEGER,
            chunk_text      VARCHAR,
            topics          VARCHAR,          -- JSON array
            entities        VARCHAR,          -- JSON array
            FOREIGN KEY (video_id) REFERENCES episodic(video_id)
        )
    """)

    # ── PROCEDURAL MEMORY ────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS procedural (
            rule_id             VARCHAR PRIMARY KEY,
            condition           VARCHAR,
            action              VARCHAR,
            rerun_prompt_mod    VARCHAR,
            source              VARCHAR DEFAULT 'default',
            -- default / mlds_day1 / mlds_day2
            active              BOOLEAN DEFAULT TRUE,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── YEARLY SUMMARIES ─────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE IF NOT EXISTS yearly_summaries (
            year                INTEGER PRIMARY KEY,
            video_count         INTEGER,
            summary_draft       VARCHAR,
            summary_final       VARCHAR,
            judge_score         FLOAT,
            judge_feedback      VARCHAR,
            edit_distance       FLOAT,
            top_topics          VARCHAR,      -- JSON array
            top_entities        VARCHAR,      -- JSON array
            sentiment_avg       FLOAT,
            cost_claude         FLOAT DEFAULT 0.0,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert default procedural rules
    con.execute("""
        INSERT OR IGNORE INTO procedural VALUES
            ('triage_skip',    'transcript_len < 100',        'skip',      NULL, 'default', TRUE, CURRENT_TIMESTAMP),
            ('triage_tier1',   'triage_score < 0.3',          'tier1',     NULL, 'default', TRUE, CURRENT_TIMESTAMP),
            ('triage_tier2',   'triage_score >= 0.3',         'tier2',     NULL, 'default', TRUE, CURRENT_TIMESTAMP),
            ('rerun_limit',    'rerun_count >= 2',            'escalate',  NULL, 'default', TRUE, CURRENT_TIMESTAMP),
            ('audit_strict',   'edit_distance > 0.4',         'rerun',     'Be more concise and factual. Avoid generalisations.', 'default', TRUE, CURRENT_TIMESTAMP)
    """)

    con.close()
    print("Schema initialised: episodic, semantic, procedural, yearly_summaries")


def load_enriched_videos():
    """Load enriched metadata into episodic table."""
    from pipeline.enrich_metadata import get_year

    enriched_file = Path("data/videos_enriched.json")
    if not enriched_file.exists():
        raise FileNotFoundError("Run enrich_metadata.py first")

    with open(enriched_file) as f:
        videos = json.load(f)

    con = get_connection()
    inserted = 0
    skipped = 0

    for v in videos:
        year = get_year(v)
        existing = con.execute(
            "SELECT video_id FROM episodic WHERE video_id = ?", [v["video_id"]]
        ).fetchone()

        if existing:
            skipped += 1
            continue

        con.execute("""
            INSERT INTO episodic (
                video_id, title, upload_date, year, view_count,
                duration, description, tags, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """, [
            v["video_id"],
            v.get("title", ""),
            v.get("upload_date", ""),
            year,
            v.get("view_count"),
            v.get("duration", ""),
            v.get("description", ""),
            json.dumps(v.get("tags", [])),
        ])
        inserted += 1

    con.close()
    print(f"Loaded {inserted} videos into episodic table ({skipped} already existed)")


if __name__ == "__main__":
    init_schema()
    load_enriched_videos()

    con = get_connection()
    count = con.execute("SELECT COUNT(*) FROM episodic").fetchone()[0]
    by_year = con.execute(
        "SELECT year, COUNT(*) as n FROM episodic WHERE year IS NOT NULL GROUP BY year ORDER BY year"
    ).fetchall()
    con.close()

    print(f"\nTotal in episodic: {count}")
    for year, n in by_year:
        print(f"  {year}: {n}")
