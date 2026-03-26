"""
AIM Transcript Intelligence — Entry Point

Usage:
  python run.py --sprint-demo          # ~5 min, top 5 videos/year (~55 total)
  python run.py --complete-deep-dive   # full run, all 3173 videos

The sprint-demo mode is designed so judges can re-run the entire pipeline
live during evaluation and see results in ~5 minutes.
"""

import argparse
import sys

from pipeline.database import init_schema, load_enriched_videos, get_connection
from agents.orchestrator import run as orchestrator_run


def check_prerequisites():
    """Verify data layer is ready before running pipeline."""
    con = get_connection()
    count = con.execute("SELECT COUNT(*) FROM episodic").fetchone()[0]
    con.close()

    if count == 0:
        print("No videos in database. Running setup...")
        init_schema()
        load_enriched_videos()
        con = get_connection()
        count = con.execute("SELECT COUNT(*) FROM episodic").fetchone()[0]
        con.close()
        print(f"Setup complete: {count} videos loaded.")
    else:
        print(f"Database ready: {count} videos in episodic table.")


def main():
    parser = argparse.ArgumentParser(
        description="AIM Transcript Intelligence Pipeline"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--sprint-demo",
        action="store_true",
        help="Run on top 5 videos/year (~55 total). ~5 min. For live judge demo.",
    )
    group.add_argument(
        "--complete-deep-dive",
        action="store_true",
        help="Run on all 3173 videos. Multi-hour. Full analysis.",
    )
    parser.add_argument(
        "--skip-prereq-check",
        action="store_true",
        help="Skip database prerequisite check (if already set up).",
    )

    args = parser.parse_args()

    if not args.skip_prereq_check:
        check_prerequisites()

    mode = "sprint-demo" if args.sprint_demo else "complete-deep-dive"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║     AIM Transcript Intelligence — Content Intelligence Layer  ║
║     10 years · 3173 videos · Under $1                        ║
╚══════════════════════════════════════════════════════════════╝

Mode: {mode}
""")

    result = orchestrator_run(mode=mode)

    print(f"""
Pipeline complete.
  Mode:       {result['mode']}
  Time:       {result['elapsed_s']:.0f}s
  Total cost: ${result['total_cost']:.4f}

Next steps:
  streamlit run dashboard/app.py    # View interactive dashboard
  python report/generator.py        # Generate PDF report
""")


if __name__ == "__main__":
    main()
