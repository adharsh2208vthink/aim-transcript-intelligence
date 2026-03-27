"""
Archivist Agent — Fetches transcripts for all videos.

Decision logic per video:
  1. Check cache (never re-fetch)
  2. Try youtube-transcript-api (fast, free)
  3. Try yt-dlp subtitle extraction (fallback)
  4. Try YouTube Data API v3 description + tags (for no-caption videos)
  5. Mark unavailable (skip gracefully)

Logs every decision to the episodic blackboard.
"""

import json
import os
import time
import subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import duckdb
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
)
from tqdm import tqdm

from pipeline.database import get_connection, DB_PATH

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

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
    subprocess.run(cmd, capture_output=True, timeout=10)
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


def _fetch_and_save(video_id: str, upload_date: str = "", duration_s: int = 0) -> dict:
    """
    Fetch transcript for a single video — no DB access, file-based only.

    Year-Based Heuristic (Agentic Innovation):
      - Pre-2021 + transcript API fails → skip yt-dlp, go straight to description API.
      - < 2 min duration → skip yt-dlp (likely music/text overlay, no speech).
    This avoids 10s timeouts on videos that will never have captions.
    """
    cache_file = TRANSCRIPT_CACHE / f"{video_id}.txt"
    if cache_file.exists() and cache_file.stat().st_size > 50:
        return {"video_id": video_id, "method": "cache", "text": cache_file.read_text(), "error": None}

    year = int(upload_date[:4]) if upload_date and len(upload_date) >= 4 else 2026
    skip_ytdlp = year < 2021 or duration_s < 120

    # Method 1: youtube-transcript-api
    try:
        transcript = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["en", "en-IN", "en-GB", "en-US"]
        )
        text = " ".join(e["text"] for e in transcript)
        cache_file.write_text(text)
        return {"video_id": video_id, "method": "transcript_api", "text": text, "error": None}
    except (NoTranscriptFound, TranscriptsDisabled):
        pass
    except Exception:
        pass

    # Method 2: yt-dlp — SKIP for pre-2021 or short videos (year-based heuristic)
    if not skip_ytdlp:
        try:
            text = _fetch_via_ytdlp(video_id)
            cache_file.write_text(text)
            return {"video_id": video_id, "method": "ytdlp_subtitle", "text": text, "error": None}
        except Exception:
            pass

    # Method 3: YouTube Data API v3 — description + tags fallback
    if YOUTUBE_API_KEY:
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "snippet", "id": video_id, "key": YOUTUBE_API_KEY},
                timeout=10,
            )
            item = resp.json().get("items", [{}])[0]
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            description = snippet.get("description", "").strip()
            tags = " ".join(snippet.get("tags", []))
            text = f"{title}\n\n{description}\n\nTags: {tags}".strip()
            if len(text) > 50:
                cache_file.write_text(text)
                return {"video_id": video_id, "method": "description_api", "text": text, "error": None}
        except Exception:
            pass

    return {"video_id": video_id, "method": "unavailable", "text": None, "error": "no caption or description"}


def run(limit: int = None, delay: float = 0.0, workers: int = 5):
    """
    Fetch transcripts concurrently. Prioritises oldest years first.
    limit: process only N videos (for --sprint-demo mode)
    workers: concurrent threads (default 5)
    """
    import json as _json
    import glob

    # Determine missing videos from file cache (DB may be locked)
    fetched = set(
        Path(f).stem for f in glob.glob("data/transcripts/*.txt")
        if Path(f).stat().st_size > 50
    )
    all_videos = _json.load(open("data/videos_enriched.json"))
    missing = [v for v in all_videos if v["video_id"] not in fetched]

    # Sort oldest first so early years are fetched before newer ones
    missing.sort(key=lambda v: v.get("upload_date", ""))

    if limit:
        missing = missing[:limit]

    print(f"Archivist: {len(fetched)} already fetched, {len(missing)} remaining (oldest-first, {workers} workers)...")

    # Parse duration to seconds for heuristic
    import re
    def _dur_s(d):
        if not d or not isinstance(d, str): return 0
        m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d)
        if not m: return 0
        return int(m.group(1) or 0)*3600 + int(m.group(2) or 0)*60 + int(m.group(3) or 0)

    stats = {"cache": 0, "transcript_api": 0, "ytdlp_subtitle": 0, "description_api": 0, "unavailable": 0}

    # Phase 1: Fetch all transcripts concurrently (file-based, no DB)
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _fetch_and_save,
                v["video_id"],
                str(v.get("upload_date", "")),
                _dur_s(v.get("duration", ""))
            ): v["video_id"]
            for v in missing
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="Archivist (fetch)"):
            try:
                result = future.result()
                results.append(result)
                stats[result["method"]] = stats.get(result["method"], 0) + 1
            except Exception as e:
                print(f"Worker error: {e}")

    # Phase 2: Batch DB updates (single-threaded, no lock contention)
    print(f"Writing {len(results)} results to DuckDB...")
    con = get_connection()
    for result in tqdm(results, desc="Archivist (db)"):
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
            result["method"],
            result["error"],
            result["video_id"],
        ])
    con.close()
    print(f"\nArchivist complete:")
    for method, count in stats.items():
        print(f"  {method}: {count}")
    return stats


if __name__ == "__main__":
    run()
