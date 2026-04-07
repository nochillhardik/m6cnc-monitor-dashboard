import time
import logging
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import POLL_INTERVAL_SECONDS
from database.db_setup import setup_database
from collector.data_collector import collect_all_machines, setup_logging

# ============================================================
# MAIN ENTRY POINT
# Run this file to start the CNC monitor.
# It will:
#   1. Set up the database
#   2. Poll all machines immediately
#   3. Then poll continuously at POLL_INTERVAL_SECONDS
#
# To start: python run_monitor.py
# To stop:  Press Ctrl+C
# ============================================================

def main():
    setup_logging()
    logging.info("=" * 50)
    logging.info("CNC MONITOR STARTING")
    logging.info(f"Poll interval: {POLL_INTERVAL_SECONDS} seconds")
    logging.info("=" * 50)

    # Set up database tables
    setup_database()

    # Run immediately on start
    collect_all_machines()

    # Then run at fixed intervals (cycle stays close to POLL_INTERVAL_SECONDS).
    logging.info(
        f"Running fixed-interval polling every {POLL_INTERVAL_SECONDS} seconds. "
        "Press Ctrl+C to stop.\n"
    )

    next_run = time.monotonic() + POLL_INTERVAL_SECONDS

    while True:
        try:
            sleep_for = max(0.0, next_run - time.monotonic())
            if sleep_for > 0:
                time.sleep(sleep_for)

            poll_started = time.monotonic()
            collect_all_machines()
            poll_elapsed = time.monotonic() - poll_started

            if poll_elapsed > POLL_INTERVAL_SECONDS:
                logging.warning(
                    f"Poll duration {poll_elapsed:.1f}s exceeded interval "
                    f"{POLL_INTERVAL_SECONDS}s. Next poll starts immediately."
                )

            next_run += POLL_INTERVAL_SECONDS
            if next_run < time.monotonic():
                # If we are far behind (long outage/heavy load), re-sync from now.
                next_run = time.monotonic() + POLL_INTERVAL_SECONDS

        except KeyboardInterrupt:
            logging.info("CNC Monitor stopped by user.")
            sys.exit(0)

        except Exception as e:
            logging.error(f"Unexpected error: {e}. Continuing schedule.")
            next_run = time.monotonic() + POLL_INTERVAL_SECONDS

if __name__ == "__main__":
    main()
