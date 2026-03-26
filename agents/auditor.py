"""
Auditor Agent — Shadow mode validation + Edit Distance logging + rerun signaling.

Implements Vaibhav Jain's (Millennium) "Building Trust in an AI Agent When Stakes Get Real":
  - Shadow mode first: observes without blocking (calibration phase)
  - Reflection mode after: actively critiques and can signal rerun
  - Every action is logged to the immutable agent_log

Edit Distance KPI:
  - Measures how much the Auditor had to change the Narrator's summary
  - Low edit distance = Narrator got it right first time
  - High edit distance = rerun triggered with adjusted prompt

Also implements Alok Shrivastwa's (Microland) principle:
  "No silent failures." Every action is logged with intent.
"""

import json
import os
from datetime import datetime

from tqdm import tqdm
from dotenv import load_dotenv

from pipeline.database import get_connection

load_dotenv()

SHADOW_MODE_THRESHOLD = 100   # First N videos: observe only, don't block
EDIT_DISTANCE_THRESHOLD = 0.4  # From procedural rules: rerun if delta > 0.4


def _log(con, video_id: str, action: str, detail: str):
    row = con.execute(
        "SELECT agent_log FROM episodic WHERE video_id = ?", [video_id]
    ).fetchone()
    log = json.loads(row[0]) if row and row[0] else []
    log.append({
        "agent": "auditor",
        "action": action,
        "detail": detail,
        "ts": datetime.utcnow().isoformat(),
    })
    con.execute(
        "UPDATE episodic SET agent_log = ? WHERE video_id = ?",
        [json.dumps(log), video_id],
    )


def _edit_distance_ratio(s1: str, s2: str) -> float:
    """
    Normalised Levenshtein distance (0 = identical, 1 = completely different).
    Uses word-level diff for efficiency on long summaries.
    """
    if not s1 and not s2:
        return 0.0
    if not s1 or not s2:
        return 1.0

    words1 = s1.lower().split()
    words2 = s2.lower().split()

    # Wagner-Fischer DP (word-level)
    m, n = len(words1), len(words2)
    if m == 0 or n == 0:
        return 1.0

    # Use only 2 rows for memory efficiency
    prev = list(range(n + 1))
    curr = [0] * (n + 1)

    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            if words1[i-1] == words2[j-1]:
                curr[j] = prev[j-1]
            else:
                curr[j] = 1 + min(prev[j], curr[j-1], prev[j-1])
        prev, curr = curr, [0] * (n + 1)

    return round(prev[n] / max(m, n), 4)


def _audit_summary(video_id: str, title: str, summary: str,
                   transcript: str, con) -> dict:
    """
    Audit a single summary. Returns:
      approved: bool
      edit_distance: float
      notes: str
    """
    if not summary:
        return {"approved": False, "edit_distance": 1.0, "notes": "empty summary"}

    issues = []

    # Check 1: Minimum length (summaries < 50 words are too thin)
    word_count = len(summary.split())
    if word_count < 50:
        issues.append(f"too_short:{word_count}_words")

    # Check 2: Summary shouldn't just repeat the title
    title_words = set((title or "").lower().split())
    summary_words = set(summary.lower().split())
    if title_words and len(title_words & summary_words) / max(len(title_words), 1) > 0.8:
        issues.append("summary_too_close_to_title")

    # Check 3: Generic opener detection
    generic_openers = [
        "this video discusses", "in this video", "the video covers",
        "this episode", "the speaker talks about"
    ]
    summary_lower = summary.lower()
    for opener in generic_openers:
        if summary_lower.startswith(opener):
            issues.append(f"generic_opener:{opener}")
            break

    # Check 4: Summary should mention at least one entity from transcript
    # (grounding check — Vignesh Subrahmaniam / RL grounding principle)
    if transcript:
        transcript_lower = transcript[:5000].lower()
        summary_terms = [w for w in summary.lower().split() if len(w) > 5]
        grounded = any(term in transcript_lower for term in summary_terms[:10])
        if not grounded:
            issues.append("ungrounded_from_transcript")

    # Compute edit distance vs a simple extractive reference
    # (first 200 chars of transcript as baseline — measures abstraction quality)
    reference = " ".join(transcript.split()[:40]) if transcript else ""
    edit_dist = _edit_distance_ratio(summary, reference)

    approved = len(issues) == 0

    return {
        "approved": approved,
        "edit_distance": edit_dist,
        "notes": ", ".join(issues) if issues else "ok",
    }


def signal_rerun(con, video_id: str, reason: str, prompt_adjustment: str = None):
    """
    Signal Orchestrator to rerun Narrator for this video.
    Increments rerun_count. Orchestrator polls for status = 'RERUN_REQUESTED'.
    """
    row = con.execute(
        "SELECT rerun_count FROM episodic WHERE video_id = ?", [video_id]
    ).fetchone()
    rerun_count = (row[0] or 0) + 1

    # Check procedural rule: max 2 reruns
    if rerun_count > 2:
        _log(con, video_id, "rerun_skipped", f"max_reruns_reached reason={reason}")
        return False

    _log(con, video_id, "signal_rerun",
         f"rerun#{rerun_count} reason={reason} adjustment={prompt_adjustment}")

    con.execute("""
        UPDATE episodic SET
            rerun_count = ?,
            status      = 'RERUN_REQUESTED',
            updated_at  = CURRENT_TIMESTAMP
        WHERE video_id = ?
    """, [rerun_count, video_id])

    return True


def run(shadow_only: bool = False, limit: int = None):
    """
    Audit all SUMMARIZED videos.

    shadow_only: if True, log observations but never signal rerun (calibration mode).
    After first SHADOW_MODE_THRESHOLD videos, auto-switches to full reflection mode.
    """
    con = get_connection()

    query = """
        SELECT video_id, title, transcript, summary_tier2
        FROM episodic
        WHERE status = 'SUMMARIZED'
          AND summary_tier2 IS NOT NULL
        ORDER BY rowid
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = con.execute(query).fetchall()

    print(f"Auditor: reviewing {len(rows)} summaries "
          f"({'shadow mode only' if shadow_only else 'shadow + reflection'})...")

    stats = {
        "approved": 0,
        "rerun_signaled": 0,
        "shadow_observed": 0,
        "errors": 0,
    }

    for i, (video_id, title, transcript, summary) in enumerate(
        tqdm(rows, desc="Auditor")
    ):
        in_shadow = shadow_only or i < SHADOW_MODE_THRESHOLD

        try:
            result = _audit_summary(video_id, title or "", summary or "",
                                    transcript or "", con)

            edit_dist = result["edit_distance"]
            approved = result["approved"]
            notes = result["notes"]

            # Log observation
            mode = "shadow" if in_shadow else "reflection"
            _log(con, video_id, f"audit_{mode}",
                 f"approved={approved} edit_dist={edit_dist} notes={notes}")

            if in_shadow:
                # Shadow mode: observe but don't block
                con.execute("""
                    UPDATE episodic SET
                        summary_audited = summary_tier2,
                        edit_distance   = ?,
                        status          = 'AUDITED',
                        updated_at      = CURRENT_TIMESTAMP
                    WHERE video_id = ?
                """, [edit_dist, video_id])
                stats["shadow_observed"] += 1

            elif approved:
                # Reflection mode: approved
                con.execute("""
                    UPDATE episodic SET
                        summary_audited = summary_tier2,
                        edit_distance   = ?,
                        status          = 'AUDITED',
                        updated_at      = CURRENT_TIMESTAMP
                    WHERE video_id = ?
                """, [edit_dist, video_id])
                stats["approved"] += 1

            else:
                # Reflection mode: quality issue detected
                # Check if edit distance exceeds threshold → signal rerun
                if edit_dist > EDIT_DISTANCE_THRESHOLD:
                    # Look up prompt adjustment from procedural rules
                    rule = con.execute("""
                        SELECT rerun_prompt_mod FROM procedural
                        WHERE rule_id = 'audit_strict' AND active = TRUE
                    """).fetchone()
                    adjustment = rule[0] if rule else None

                    signaled = signal_rerun(con, video_id, notes, adjustment)
                    if signaled:
                        stats["rerun_signaled"] += 1
                    else:
                        # Max reruns reached — approve as-is
                        con.execute("""
                            UPDATE episodic SET
                                summary_audited = summary_tier2,
                                edit_distance   = ?,
                                status          = 'AUDITED',
                                updated_at      = CURRENT_TIMESTAMP
                            WHERE video_id = ?
                        """, [edit_dist, video_id])
                        stats["approved"] += 1
                else:
                    # Issues found but not severe enough to rerun
                    con.execute("""
                        UPDATE episodic SET
                            summary_audited = summary_tier2,
                            edit_distance   = ?,
                            status          = 'AUDITED',
                            updated_at      = CURRENT_TIMESTAMP
                        WHERE video_id = ?
                    """, [edit_dist, video_id])
                    stats["approved"] += 1

        except Exception as e:
            _log(con, video_id, "audit_error", str(e)[:100])
            stats["errors"] += 1

    con.close()
    print(f"\nAuditor complete:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    return stats


if __name__ == "__main__":
    run()
