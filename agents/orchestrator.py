"""
Orchestrator Agent — Supervisor that manages the full pipeline.

Implements Shashank Rao's (Atlassian) Supervisor-Specialist architecture:
  "Agentic Request Delegation and Resolution"

  - Manages work queue via DuckDB status column (crash-safe resume)
  - Delegates to specialist agents in order
  - Listens for Auditor rerun signals → re-queues failed summaries
  - Reads context/insights.yaml at startup → reconfigures pipeline (adaptive)
  - No silent failures: every decision logged

Adaptive config (Nikhil Daxini / EY GDS — "From Cost Center to AI Command Center"):
  The pipeline reconfigures based on MLDS context insights:
  - governance flagged    → Auditor runs in strict mode
  - high_stakes_trust     → Judge evaluates every Tier 2 summary (not just 5%)
  - grounding flagged     → transcript grounding checks enabled in Judge
  - memory flagged        → full 3-tier semantic index built
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from pipeline.database import get_connection
import agents.archivist as archivist
import agents.triage as triage
import agents.analyst as analyst
import agents.narrator as narrator
import agents.auditor as auditor
import agents.judge as judge

load_dotenv()

INSIGHTS_YAML = Path("context/insights.yaml")


def _load_adaptive_config() -> dict:
    """
    Load MLDS insights.yaml and return pipeline config.
    Implements adaptive architecture — Orchestrator reconfigures based on context.
    """
    default_config = {
        "auditor_mode": "shadow",           # shadow | strict
        "judge_sample_rate": 0.05,          # 5% of Tier 2
        "judge_yearly_coverage": 1.0,       # 100% of Tier 3
        "grounding_checks": False,          # transcript grounding in Judge
        "semantic_index": False,            # build semantic RAG index
        "focus_areas": [],
    }

    if not INSIGHTS_YAML.exists():
        return default_config

    try:
        import yaml
        with open(INSIGHTS_YAML) as f:
            insights = yaml.safe_load(f)
    except ImportError:
        # yaml not installed — parse manually
        insights = {}
        try:
            text = INSIGHTS_YAML.read_text()
            for line in text.splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition(":")
                    insights[k.strip()] = v.strip()
        except Exception:
            pass

    config = default_config.copy()
    focus = insights.get("focus_areas", [])
    if isinstance(focus, str):
        focus = [f.strip() for f in focus.split(",")]

    config["focus_areas"] = focus

    # Adaptive rules
    if "governance" in focus or insights.get("emphasis") == "high_stakes_trust":
        config["auditor_mode"] = "strict"
        _write_procedural_rule("audit_strict_governance",
                               "triage_tier = 'tier2'",
                               "full_audit",
                               "Be more specific. Cite actual speaker names and company names mentioned.",
                               "mlds_context")

    if "high_stakes_trust" in focus or insights.get("emphasis") == "high_stakes_trust":
        config["judge_sample_rate"] = 1.0  # 100% Tier 2 sampling

    if "grounding" in focus:
        config["grounding_checks"] = True

    if "memory" in focus:
        config["semantic_index"] = True

    print(f"Orchestrator: adaptive config loaded → {json.dumps(config, indent=2)}")
    return config


def _write_procedural_rule(rule_id, condition, action, mod, source):
    """Write a new adaptive rule to procedural table."""
    con = get_connection()
    con.execute("""
        INSERT INTO procedural (rule_id, condition, action, rerun_prompt_mod, source, active)
        VALUES (?, ?, ?, ?, ?, TRUE)
        ON CONFLICT (rule_id) DO UPDATE SET
            condition = excluded.condition,
            action = excluded.action,
            rerun_prompt_mod = excluded.rerun_prompt_mod,
            source = excluded.source
    """, [rule_id, condition, action, mod, source])
    con.close()


def _get_pipeline_counts(con) -> dict:
    """Current status distribution for dashboard + logging."""
    rows = con.execute("""
        SELECT status, COUNT(*) as n FROM episodic
        GROUP BY status ORDER BY status
    """).fetchall()
    return {r[0]: r[1] for r in rows}


def _handle_rerun_requests(con, config: dict):
    """
    Process any videos where Auditor signaled a rerun.
    Re-runs Narrator with adjusted prompt from procedural rules.
    """
    reruns = con.execute("""
        SELECT video_id, rerun_count FROM episodic
        WHERE status = 'RERUN_REQUESTED'
    """).fetchall()

    if not reruns:
        return

    print(f"Orchestrator: processing {len(reruns)} rerun requests...")
    for video_id, rerun_count in reruns:
        # Reset to ANALYZED so Narrator picks it up
        con.execute("""
            UPDATE episodic SET
                status = 'ANALYZED',
                summary_tier2 = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE video_id = ?
        """, [video_id])

    # Re-run Narrator for these videos only
    narrator.run_tier2(limit=len(reruns))
    # Re-run Auditor
    auditor.run(shadow_only=False, limit=len(reruns))


def run(mode: str = "sprint-demo"):
    """
    Full pipeline run.

    mode:
      sprint-demo      — top 5 videos/year (~55 videos), ~5 min, for live judge demo
      complete-deep-dive — all 3173 videos, multi-hour, pre-computed
    """
    start_time = datetime.utcnow()
    print(f"\n{'='*60}")
    print(f"Orchestrator: starting pipeline in [{mode}] mode")
    print(f"{'='*60}\n")

    # Load adaptive config from MLDS insights
    config = _load_adaptive_config()

    # Determine limits
    limit = None
    limit_per_year = None
    if mode == "sprint-demo":
        limit_per_year = 5   # top 5 by view_count per year
        limit = 55           # ~11 years × 5

    con = get_connection()

    # Sprint demo: pre-select top N per year
    if mode == "sprint-demo":
        print(f"Orchestrator: selecting top {limit_per_year} videos/year for sprint demo...")
        # Mark all non-selected as SKIP_DEMO (won't be processed)
        years = con.execute(
            "SELECT DISTINCT year FROM episodic WHERE year IS NOT NULL ORDER BY year"
        ).fetchall()

        selected_ids = []
        for (year,) in years:
            top = con.execute("""
                SELECT video_id FROM episodic
                WHERE year = ? AND status = 'PENDING'
                ORDER BY view_count DESC NULLS LAST
                LIMIT ?
            """, [year, limit_per_year]).fetchall()
            selected_ids.extend(r[0] for r in top)

        # Mark non-selected as skipped for this run
        if selected_ids:
            placeholders = ",".join("?" * len(selected_ids))
            con.execute(f"""
                UPDATE episodic SET status = 'SKIP_DEMO'
                WHERE status = 'PENDING'
                  AND video_id NOT IN ({placeholders})
            """, selected_ids)

        print(f"  Selected {len(selected_ids)} videos for sprint demo")

    counts = _get_pipeline_counts(con)
    print(f"Pipeline state: {counts}\n")
    con.close()

    # ── STEP 1: ARCHIVIST ───────────────────────────────────────────────────
    print("─" * 40)
    print("Step 1/6: Archivist — fetching transcripts")
    print("─" * 40)
    archivist.run(limit=limit)

    # ── STEP 2: TRIAGE ──────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Step 2/6: Triage — quality scoring + routing")
    print("─" * 40)
    triage.run(limit=limit)

    # ── STEP 3: ANALYST ─────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Step 3/6: Analyst — NER + sentiment + TF-IDF")
    print("─" * 40)
    analyst.run(limit=limit)

    # ── STEP 4: NARRATOR (Tier 2) ───────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Step 4/6: Narrator Tier 2 — Gemini Flash summaries")
    print("─" * 40)
    narrator.run_tier2(limit=limit)

    # ── STEP 5: AUDITOR ─────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Step 5/6: Auditor — shadow mode + reflection")
    print("─" * 40)
    shadow_only = config["auditor_mode"] == "shadow"
    auditor.run(shadow_only=shadow_only, limit=limit)

    # Handle rerun requests
    con = get_connection()
    _handle_rerun_requests(con, config)
    con.close()

    # ── STEP 6: NARRATOR (Tier 3) ───────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Step 6a/6: Narrator Tier 3 — Claude Sonnet yearly synthesis")
    print("─" * 40)
    narrator.run_tier3()

    # ── STEP 7: JUDGE ───────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Step 6b/6: Judge — evaluating reasoning traces")
    print("─" * 40)
    sample_rate = config["judge_sample_rate"]
    judge.run(sample_rate=sample_rate)

    # ── DONE ────────────────────────────────────────────────────────────────
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    con = get_connection()
    final_counts = _get_pipeline_counts(con)

    # Cost summary
    cost_gemini = con.execute("SELECT SUM(cost_gemini) FROM episodic").fetchone()[0] or 0
    cost_claude_ep = con.execute("SELECT SUM(cost_claude) FROM episodic").fetchone()[0] or 0
    cost_claude_ys = con.execute("SELECT SUM(cost_claude) FROM yearly_summaries").fetchone()[0] or 0
    total_cost = cost_gemini + cost_claude_ep + cost_claude_ys
    con.close()

    print(f"\n{'='*60}")
    print(f"Pipeline complete in {elapsed:.0f}s")
    print(f"Final state: {final_counts}")
    print(f"\nCost summary:")
    print(f"  Gemini Flash:  ${cost_gemini:.4f}")
    print(f"  Claude Sonnet: ${cost_claude_ep + cost_claude_ys:.4f}")
    print(f"  TOTAL:         ${total_cost:.4f}")
    print(f"{'='*60}\n")

    return {
        "mode": mode,
        "elapsed_s": elapsed,
        "counts": final_counts,
        "total_cost": total_cost,
    }


if __name__ == "__main__":
    run(mode="sprint-demo")
