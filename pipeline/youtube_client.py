"""
YouTube client — fetches video metadata + transcripts from AIM Media House channel.
Strategy per video:
  1. youtube-transcript-api (fast, free)
  2. yt-dlp subtitle extraction (fallback)
  3. Flag as unavailable (skip)
"""

import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from tqdm import tqdm


CACHE_DIR = Path("data/transcripts")
METADATA_FILE = Path("data/videos_metadata.json")
CHANNEL_HANDLE = "@aimmediahouse"


def fetch_channel_videos(max_videos: int = None) -> list[dict]:
    """Fetch all video metadata from the channel using yt-dlp."""
    if METADATA_FILE.exists():
        print(f"Loading cached metadata from {METADATA_FILE}")
        with open(METADATA_FILE) as f:
            return json.load(f)

    print(f"Fetching video list from {CHANNEL_HANDLE}...")
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
        f"https://www.youtube.com/{CHANNEL_HANDLE}/videos",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")

    data = json.loads(result.stdout)
    entries = data.get("entries", [])

    videos = []
    for entry in entries:
        if not entry:
            continue
        videos.append({
            "video_id": entry.get("id"),
            "title": entry.get("title"),
            "upload_date": entry.get("upload_date"),  # YYYYMMDD
            "duration": entry.get("duration"),
            "view_count": entry.get("view_count"),
            "like_count": entry.get("like_count"),
            "url": f"https://www.youtube.com/watch?v={entry.get('id')}",
        })

    if max_videos:
        videos = videos[:max_videos]

    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(METADATA_FILE, "w") as f:
        json.dump(videos, f, indent=2)

    print(f"Found {len(videos)} videos. Metadata cached to {METADATA_FILE}")
    return videos


def fetch_transcript_api(video_id: str) -> tuple[str, str]:
    """Try youtube-transcript-api. Returns (text, method) or raises."""
    transcript_list = YouTubeTranscriptApi.get_transcript(
        video_id, languages=["en", "en-IN", "en-GB"]
    )
    text = " ".join(entry["text"] for entry in transcript_list)
    return text, "transcript_api"


def fetch_transcript_ytdlp(video_id: str) -> tuple[str, str]:
    """Fallback: yt-dlp subtitle extraction."""
    out_dir = CACHE_DIR / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "yt-dlp",
        "--write-auto-sub",
        "--sub-lang", "en",
        "--sub-format", "vtt",
        "--skip-download",
        "--no-warnings",
        "-o", str(out_dir / "%(id)s.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    vtt_files = list(out_dir.glob(f"{video_id}*.vtt"))
    if not vtt_files:
        raise RuntimeError("No subtitle file generated")

    raw = vtt_files[0].read_text()
    vtt_files[0].unlink()

    # Strip VTT formatting
    lines = []
    for line in raw.splitlines():
        if "-->" in line or line.startswith("WEBVTT") or line.strip().isdigit() or not line.strip():
            continue
        lines.append(line.strip())
    text = " ".join(lines)
    return text, "ytdlp_subtitle"


def fetch_transcript(video: dict) -> dict:
    """
    Archivist decision logic: try each method in order, log the decision.
    Returns enriched video dict with transcript and fetch metadata.
    """
    video_id = video["video_id"]
    cache_file = CACHE_DIR / f"{video_id}.json"

    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    result = {**video, "transcript": None, "fetch_method": None, "fetch_error": None}

    # Method 1: youtube-transcript-api
    try:
        text, method = fetch_transcript_api(video_id)
        result["transcript"] = text
        result["fetch_method"] = method
    except (NoTranscriptFound, TranscriptsDisabled, Exception) as e1:
        # Method 2: yt-dlp
        try:
            text, method = fetch_transcript_ytdlp(video_id)
            result["transcript"] = text
            result["fetch_method"] = method
        except Exception as e2:
            result["fetch_method"] = "unavailable"
            result["fetch_error"] = str(e2)

    # Cache to disk
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(result, f, ensure_ascii=False)

    return result


def fetch_all_transcripts(videos: list[dict], delay: float = 0.5) -> list[dict]:
    """Fetch transcripts for all videos with progress bar."""
    results = []
    for video in tqdm(videos, desc="Fetching transcripts"):
        result = fetch_transcript(video)
        results.append(result)
        time.sleep(delay)

    total = len(results)
    success = sum(1 for v in results if v["transcript"])
    unavailable = total - success
    print(f"\nFetch complete: {success}/{total} transcripts | {unavailable} unavailable")
    return results


def get_year(video: dict) -> int | None:
    """Extract year from upload_date (YYYYMMDD)."""
    date = video.get("upload_date")
    if date and len(date) >= 4:
        return int(date[:4])
    return None


if __name__ == "__main__":
    videos = fetch_channel_videos()
    print(f"Total videos: {len(videos)}")
    year_range = sorted(set(get_year(v) for v in videos if get_year(v)))
    print(f"Year range: {year_range[0]} – {year_range[-1]}")
    print("Starting transcript fetch...")
    results = fetch_all_transcripts(videos)
