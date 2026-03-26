"""
Enrich video metadata with upload_date, view_count using YouTube Data API v3.
Batches 50 videos per request → 3173 videos = ~64 API calls.
Free quota: 10,000 units/day. This uses ~64 units total.
"""

import json
import os
import time
import urllib.request
import urllib.parse
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

METADATA_FILE = Path("data/videos_metadata.json")
ENRICHED_FILE = Path("data/videos_enriched.json")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
BATCH_SIZE = 50


def fetch_batch(video_ids: list[str]) -> dict:
    """Fetch metadata for up to 50 videos in one API call."""
    ids = ",".join(video_ids)
    params = urllib.parse.urlencode({
        "part": "snippet,statistics,contentDetails",
        "id": ids,
        "key": YOUTUBE_API_KEY,
    })
    url = f"https://www.googleapis.com/youtube/v3/videos?{params}"
    resp = urllib.request.urlopen(url, timeout=15)
    data = json.loads(resp.read())

    result = {}
    for item in data.get("items", []):
        vid = item["id"]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        published = snippet.get("publishedAt", "")
        upload_date = published[:10].replace("-", "") if published else None

        result[vid] = {
            "video_id": vid,
            "upload_date": upload_date,
            "view_count": int(stats.get("viewCount", 0)) if stats.get("viewCount") else None,
            "like_count": int(stats.get("likeCount", 0)) if stats.get("likeCount") else None,
            "duration": item.get("contentDetails", {}).get("duration"),
            "title": snippet.get("title", ""),
            "description": (snippet.get("description") or "")[:300],
            "channel_title": snippet.get("channelTitle", ""),
            "tags": snippet.get("tags", [])[:10],
        }
    return result


def enrich_all(videos: list[dict]) -> list[dict]:
    # Load previously enriched
    enriched_map = {}
    if ENRICHED_FILE.exists():
        with open(ENRICHED_FILE) as f:
            for v in json.load(f):
                if v.get("upload_date"):
                    enriched_map[v["video_id"]] = v

    to_fetch = [v for v in videos if v["video_id"] not in enriched_map]
    print(f"Already enriched: {len(enriched_map)} | To fetch: {len(to_fetch)}")

    # Batch into groups of 50
    batches = [
        to_fetch[i:i + BATCH_SIZE]
        for i in range(0, len(to_fetch), BATCH_SIZE)
    ]

    for batch in tqdm(batches, desc="Fetching metadata (YouTube API)"):
        ids = [v["video_id"] for v in batch]
        try:
            results = fetch_batch(ids)
            enriched_map.update(results)
        except Exception as e:
            print(f"Batch error: {e}")
        time.sleep(0.1)  # gentle rate limiting

    _save(videos, enriched_map)
    return _merge(videos, enriched_map)


def _save(videos, enriched_map):
    with open(ENRICHED_FILE, "w") as f:
        json.dump(_merge(videos, enriched_map), f, indent=2)


def _merge(videos, enriched_map):
    result = []
    for v in videos:
        vid = v["video_id"]
        e = enriched_map.get(vid, {})
        result.append({
            **v,
            "upload_date": e.get("upload_date") or v.get("upload_date"),
            "view_count": e.get("view_count") or v.get("view_count"),
            "like_count": e.get("like_count") or v.get("like_count"),
            "duration": e.get("duration") or v.get("duration"),
            "description": e.get("description", ""),
            "tags": e.get("tags", []),
        })
    return result


def get_year(video: dict) -> int | None:
    date = video.get("upload_date")
    if date and len(str(date)) >= 4:
        return int(str(date)[:4])
    return None


if __name__ == "__main__":
    with open(METADATA_FILE) as f:
        videos = json.load(f)

    enriched = enrich_all(videos)

    from collections import Counter
    by_year = Counter(get_year(v) for v in enriched if get_year(v))
    print(f"\nVideos with dates: {sum(by_year.values())} / {len(enriched)}")
    print("By year:")
    for y in sorted(by_year):
        print(f"  {y}: {by_year[y]}")
