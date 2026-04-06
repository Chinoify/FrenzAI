"""
audiobook_batch_catalog.py
===========================
Runs audiobook_pocket_tts.py across your ENTIRE book catalog.
One voice WAV per pen name, one manuscript per book.

Configure the CATALOG dict below, then run:
    python audiobook_batch_catalog.py

Or run a single pen name:
    python audiobook_batch_catalog.py --pen_name "Grace Ifeoma Ezedinma"

Or a single book by title:
    python audiobook_batch_catalog.py --title "Leave and Cleave"
"""

import argparse
import subprocess
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# CATALOG CONFIGURATION
# Edit this dict to match your actual files and pen names.
# ═══════════════════════════════════════════════════════════════════════════════

CATALOG = [
    # ── FamilyHaven / Christian ──────────────────────────────────────────────
    {
        "pen_name":   "Grace Ifeoma Ezedinma",
        "voice_wav":  "./voices/grace_ifeoma.wav",       # your 10-20 sec WAV clip
        "books": [
            {
                "title":      "Leave and Cleave",
                "manuscript": "./manuscripts/leave_and_cleave.txt",
                "output_dir": "./audiobooks/grace_ifeoma/leave_and_cleave",
            },
            {
                "title":      "The Husband-Man",
                "manuscript": "./manuscripts/the_husband_man.txt",
                "output_dir": "./audiobooks/grace_ifeoma/the_husband_man",
            },
        ],
    },

    # ── Dark Academia / Romance ──────────────────────────────────────────────
    {
        "pen_name":   "Pen Name 2",                      # replace with your actual pen name
        "voice_wav":  "./voices/pen_name_2.wav",
        "books": [
            {
                "title":      "Commencement",
                "manuscript": "./manuscripts/commencement.txt",
                "output_dir": "./audiobooks/pen_name_2/commencement",
            },
            {
                "title":      "The Masquerade",
                "manuscript": "./manuscripts/the_masquerade.txt",
                "output_dir": "./audiobooks/pen_name_2/the_masquerade",
            },
        ],
    },

    # ── Cozy Mystery ────────────────────────────────────────────────────────
    {
        "pen_name":   "Pen Name 3",
        "voice_wav":  "./voices/pen_name_3.wav",
        "books": [
            {
                "title":      "Shelf Life",
                "manuscript": "./manuscripts/shelf_life.txt",
                "output_dir": "./audiobooks/pen_name_3/shelf_life",
            },
            {
                "title":      "The Plot Thickens",
                "manuscript": "./manuscripts/the_plot_thickens.txt",
                "output_dir": "./audiobooks/pen_name_3/the_plot_thickens",
            },
        ],
    },

    # ── Thriller ────────────────────────────────────────────────────────────
    {
        "pen_name":   "Pen Name 4",
        "voice_wav":  "./voices/pen_name_4.wav",
        "books": [
            {
                "title":      "The Handler",
                "manuscript": "./manuscripts/the_handler.txt",
                "output_dir": "./audiobooks/pen_name_4/the_handler",
            },
        ],
    },

    # Add more pen names / books following the same pattern…
]


# ═══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT = str(Path(__file__).parent / "audiobook_pocket_tts.py")
LOG_DIR = Path("./audiobook_logs")
LOG_DIR.mkdir(exist_ok=True)

RESULTS_FILE = str(LOG_DIR / "batch_results.json")


def load_results() -> dict:
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return {}


def save_results(results: dict):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


def run_book(pen_name: str, voice_wav: str, book: dict, dry_run: bool = False) -> bool:
    title      = book["title"]
    manuscript = book["manuscript"]
    output_dir = book["output_dir"]
    key        = f"{pen_name}|{title}"

    # Skip missing files gracefully
    if not os.path.exists(manuscript):
        print(f"  ⚠ SKIP — manuscript not found: {manuscript}")
        return False
    if not os.path.exists(voice_wav):
        print(f"  ⚠ SKIP — voice WAV not found: {voice_wav}")
        return False

    cmd = [
        sys.executable, SCRIPT,
        "--text",        manuscript,
        "--voice",       voice_wav,
        "--output_dir",  output_dir,
        "--title",       title,
        "--pen_name",    pen_name,
        "--concat",
    ]

    print(f"\n  ▶ '{title}'")
    print(f"    Voice  : {voice_wav}")
    print(f"    Output : {output_dir}")

    if dry_run:
        print(f"    [DRY RUN] Command: {' '.join(cmd)}")
        return True

    log_file = str(LOG_DIR / f"{key.replace('|','_').replace(' ','_')}.log")
    t0 = time.time()

    try:
        with open(log_file, "w") as lf:
            result = subprocess.run(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True,
            )
        elapsed = time.time() - t0
        success = result.returncode == 0

        status = "✅ DONE" if success else "❌ FAILED"
        print(f"    {status}  ({elapsed:.0f}s)  Log: {log_file}")
        return success

    except Exception as e:
        print(f"    ❌ ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Batch audiobook generation across catalog")
    parser.add_argument("--pen_name", help="Only process this pen name")
    parser.add_argument("--title",    help="Only process this book title")
    parser.add_argument("--dry_run",  action="store_true", help="Print commands without running")
    parser.add_argument("--skip_done", action="store_true", help="Skip books already completed")
    args = parser.parse_args()

    results = load_results()
    total = done = failed = skipped = 0

    print("=" * 60)
    print("  AUDIOBOOK BATCH GENERATOR — Pocket TTS")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    for entry in CATALOG:
        pen  = entry["pen_name"]
        wav  = entry["voice_wav"]
        books = entry["books"]

        # Filter by pen name if specified
        if args.pen_name and pen.lower() != args.pen_name.lower():
            continue

        print(f"\n{'─'*55}")
        print(f"  PEN NAME: {pen}")
        print(f"  VOICE   : {wav}")
        print(f"  BOOKS   : {len(books)}")

        for book in books:
            title = book["title"]

            # Filter by title if specified
            if args.title and title.lower() != args.title.lower():
                continue

            key = f"{pen}|{title}"
            total += 1

            # Skip already done
            if args.skip_done and results.get(key) == "done":
                print(f"\n  ↷ SKIP (already done): '{title}'")
                skipped += 1
                continue

            success = run_book(pen, wav, book, dry_run=args.dry_run)

            if not args.dry_run:
                results[key] = "done" if success else "failed"
                save_results(results)

            if success:
                done += 1
            else:
                failed += 1

    print(f"\n{'='*55}")
    print(f"  BATCH COMPLETE")
    print(f"  Total : {total}  |  Done : {done}  |  Failed : {failed}  |  Skipped : {skipped}")
    print(f"  Results log: {RESULTS_FILE}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
