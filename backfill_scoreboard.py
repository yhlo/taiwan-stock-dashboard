"""Seed data/scoreboard.json from recent history.

The scoreboard only grows one session per run, so a fresh ledger would show
nothing for weeks. This walks recent trading days in chronological order and
feeds each through the same update_scoreboard() the daily build uses -- no
special-case scoring path, so a backfilled row is produced exactly the way a
live one will be.

Each day's signal is built only from sessions up to that day, and scored
against the following session, so the seeded history carries no look-ahead.

One-off: run manually, then let the daily build extend the ledger.
"""

import argparse
import sys

from build_static_data import (
    calculate_streaks,
    collect_t86_history,
    update_scoreboard,
)


def streak_rows_as_of(date_str, cache_dir, window=20):
    """The streak table exactly as the daily build would have seen it on `date_str`."""
    history, truncated = collect_t86_history(
        date_str, cache_dir, n=window, today_str=None
    )
    if not history or history[0][0] != date_str:
        # No session on that date (holiday, or data unavailable): nothing to sign.
        return None
    if truncated:
        print(f"  note: window truncated at {truncated}", file=sys.stderr)

    df = calculate_streaks([d for _, d in history])
    return [
        {
            "Symbol": r["Symbol"],
            "Name": r["Name"],
            "Foreign_Streak": int(r["Foreign_Streak"]),
            "Trust_Streak": int(r["Trust_Streak"]),
        }
        for _, r in df.iterrows()
    ]


def main():
    parser = argparse.ArgumentParser(description="Backfill the signal scoreboard.")
    parser.add_argument("--days", type=int, default=10,
                        help="How many recent trading days to seed (default 10).")
    parser.add_argument("--end", type=str, required=True,
                        help="Newest trading day to seed, YYYYMMDD.")
    args = parser.parse_args()

    cache_dir = "data/cache"

    # Identify the trading days to replay, oldest first.
    history, _ = collect_t86_history(args.end, cache_dir, n=args.days, today_str=None)
    if not history:
        print("No trading days found to backfill.", file=sys.stderr)
        sys.exit(1)
    dates = [d for d, _ in history][::-1]
    print(f"Backfilling {len(dates)} sessions: {dates[0]} -> {dates[-1]}")

    for date_str in dates:
        rows = streak_rows_as_of(date_str, cache_dir)
        if not rows:
            print(f"{date_str}: skipped (no session)")
            continue
        update_scoreboard(date_str, rows, cache_dir)
        print(f"{date_str}: recorded")

    print("Backfill complete.")


if __name__ == "__main__":
    main()
