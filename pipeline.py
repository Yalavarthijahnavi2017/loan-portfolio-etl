"""Pipeline orchestrator: extract -> transform -> validate -> load.

Usage:
    python pipeline.py [--refresh] [--backend {sqlite,postgres}]

Exit codes: 0 on success, 1 on data-quality failure, 2 on config/runtime error.
Each stage is timed and logged so a failed run tells you exactly where
(and after how long) it broke.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import load_settings
from src.extract import extract
from src.transform import transform
from src.validate import DataQualityError, validate
from src.load import load

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


def timed(stage: str, fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    log.info("Stage '%s' finished in %.2fs", stage, elapsed)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Loan portfolio ETL pipeline")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-download the raw CSV from the public source instead of using the bundled file",
    )
    parser.add_argument(
        "--backend",
        choices=["sqlite", "postgres"],
        help="Override DB_BACKEND from the environment",
    )
    args = parser.parse_args()

    try:
        settings = load_settings()
    except (ValueError, OSError) as exc:
        log.error("Configuration error: %s", exc)
        return 2

    if args.backend:
        # Rebuild settings with the CLI override (dataclass is frozen).
        import dataclasses

        settings = dataclasses.replace(settings, backend=args.backend)
    if args.refresh:
        import dataclasses

        settings = dataclasses.replace(settings, refresh_source=True)

    log.info("Starting pipeline (backend=%s)", settings.backend)
    try:
        raw = timed("extract", extract, settings)
        clean = timed("transform", transform, raw)
        timed("validate", validate, clean)
        log.info("Validation passed: %d rows clean", len(clean))
        n = timed("load", load, clean, settings)
    except DataQualityError as exc:
        log.error("DATA QUALITY FAILURE\n%s", exc)
        return 1
    except Exception:
        log.exception("Pipeline failed with an unexpected error")
        return 2

    log.info("Pipeline complete: %d rows loaded into '%s'", n, settings.backend)
    return 0


if __name__ == "__main__":
    sys.exit(main())
