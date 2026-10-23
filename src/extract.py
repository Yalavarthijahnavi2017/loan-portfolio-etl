"""Extract stage.

Job: get the raw loan CSV onto local disk and hand the pipeline a DataFrame.

Why download-on-refresh instead of always downloading: the source is a stable
public file, but a pipeline should be reproducible. The bundled
data/raw/loans.csv is the pinned input; --refresh re-pulls it when you
explicitly want fresh data. Nothing here invents or mutates data — extract
is a byte-for-byte copy from source to disk, then a read.
"""
from __future__ import annotations

import logging
import urllib.request

import pandas as pd

from .config import Settings

log = logging.getLogger(__name__)


def extract(settings: Settings) -> pd.DataFrame:
    raw_path = settings.raw_csv_path

    if settings.refresh_source or not raw_path.exists():
        log.info("Downloading raw data from %s", settings.source_url)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        # nosec: URL is a fixed project constant, not user input.
        urllib.request.urlretrieve(settings.source_url, raw_path)
        log.info("Saved raw data to %s", raw_path)
    else:
        log.info("Using bundled raw data at %s", raw_path)

    df = pd.read_csv(raw_path)
    log.info("Extracted %d rows x %d columns", *df.shape)
    return df
