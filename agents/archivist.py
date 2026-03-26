"""
Archivist Agent — Fetches transcripts for all videos.

Decision logic per video:
  1. Check cache (never re-fetch)
  2. Try youtube-transcript-api (fast, free)
  3. Try yt-dlp subtitle extraction (fallback)
  4. Mark unavailable (skip gracefully)

Logs every decision to the episodic blackboard.
"""

import json
import time
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

import duckdb
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
)
from tqdm import tqdm

from pipeline.database import get_connection, DB_PATH

TRANSCRIPT_CACHE = Path("data/transcripts")
TRANSCRIPT_CACHE.mkdir(parents=True, exist_ok=True)


def _log(con, video_id: str, action: str, detail: str):
    """Append an entry to episodic.agent_log."""
    row = con.execute(
        "SELECT agent_log FROM episodic WHERE video_id = ?", [video_id]
    ).fetchone()
    log = json.loads(row[0]) if row and row[0] else []
    log.append({
        "agent": "archivist",
        "action": action,
        "detail": detail,
        "ts": datetime.utcnow().isoformat(),
    })
    con.execute(
        "UPDATE episodic SET agent_log = ? WHERE video_id = ?",
        [json.dumps(log), video_id],
    )


def _fetch_via_api(video_id: str) -> str:
    transcript = YouTubeTranscriptApi.get_transcript(
        video_id, languages=["en", "en-IN", "en-GB", "en-US"]
    )
    return " ".join(e["text"] for e in transcript)


def _fetch_via_ytdlp(video_id: str) -> str:
    tmp = TRANSCRIPT_CACHE / "tmp"
    tmp.mkdir(exist_ok=True)
    cmd = [
        "yt-dlp", "--write-auto-sub", "--sub-lang", "en",
        "--sub-format", "vtt", "--skip-download", "--no-warnings",
        "-o", str(tmp / "%(id)s.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)
    vtts = list(tmp.glob(f"{video_id}*.vtt"))
    if not vtts:
        raise FileNotFoundError("No subtitle file generated")
    raw = vtts[0].read_text()
    vtts[0].unlink()
    lines = [
        l.strip() for l in raw.splitlines()
        if l.strip() and "-->" not in l
        and not l.strip().startswith("WEBVTT")
        and not l.strip().isdigit()
    ]
    return " ".join(lines)


def fetch_transcript(video_id: str, con) -> dict:
    """Archivist decision: try each method, log outcome, return result dict."""
    cache_file = TRANSCRIPT_CACHE / f"{video_id}.txt"

    # Cache hit
    if cache_file.exists():
        text = cache_file.read_text()
        _log(con, video_id, "cache_hit", f"len={len(text)}")
        return {"method": "cache", "text": text, "error": None}

    # Method 1: youtube-transcript-api
    try:
        text = _fetch_via_api(video_id)
        cache_file.write_text(text)
        _log(con, video_id, "fetch_api", f"len={len(text)}")
        return {"method": "transcript_api", "text": text, "error": None}
    except (NoTranscriptFound, TranscriptsDisabled) as e:
        _log(con, video_id, "api_fail", str(e)[:100])
    except Exception as e:
        _log(con, video_id, "api_error", str(e)[:100])

    # Method 2: yt-dlp
    try:
        text = _fetch_via_ytdlp(video_id)
        cache_file.write_text(text)
        _log(con, video_id, "fetch_ytdlp", f"len={len(text)}")
        return {"method": "ytdlp_subtitle", "text": text, "error": None}
    except Exception as e:
        _log(con, video_id, "ytdlp_fail", str(e)[:100])
        return {"method": "unavailable", "text": None, "error": str(e)[:200]}


def run(limit: int = None, delay: float = 0.3):
    """
    Fetch transcripts for all PENDING videos.
    limit: process only N videos (for --sprint-demo mode)
    """
    con = get_connection()

    query = "SELECT video_id FROM episodic WHERE status = 'PENDING'"
    if limit:
        query += f" LIMIT {limit}"
    videos = con.execute(query).fetchall()
    video_ids = [r[0] for r in videos]

    print(f"Archivist: fetching transcripts for {len(video_ids)} videos...")

    stats = {"cache": 0, "transcript_api": 0, "ytdlp_subtitle": 0, "unavailable": 0}

    for vid in tqdm(video_ids, desc="Archivist"):
        result = fetch_transcript(vid, con)
        method = result["method"]
        stats[method] = stats.get(method, 0) + 1

        con.execute("""
            UPDATE episodic SET
                transcript     = ?,
                transcript_len = ?,
                fetch_method   = ?,
                fetch_error    = ?,
                status         = 'FETCHED',
                updated_at     = CURRENT_TIMESTAMP
            WHERE video_id = ?
        """, [
            result["text"],
            len(result["text"]) if result["text"] else 0,
            method,
            result["error"],
            vid,
        ])

        time.sleep(delay)

    con.close()

    print(f"\nArchivist complete:")
    for method, count in stats.items():
        print(f"  {method}: {count}")
    return stats


if __name__ == "__main__":
    run()
