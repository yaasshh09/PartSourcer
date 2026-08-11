"""Walks the watchlist and appends one history row per part.

Bounded concurrency keeps us a polite client of a free community upstream.
One part failing never aborts the run: the summary reports it honestly.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from history.store import HistoryStore, OfferRecord
from services.datasource import PartDataSource, UpstreamError


@dataclass
class RecordSummary:
    recorded: int = 0
    skipped: int = 0
    errors: int = 0


async def record_watchlist(
    ds: PartDataSource,
    store: HistoryStore,
    *,
    batch_size: int,
    concurrency: int,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> RecordSummary:
    entries = await store.get_watchlist(limit=batch_size)
    if not entries:
        return RecordSummary()

    stamp = now()
    summary = RecordSummary()
    records: list[OfferRecord] = []
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()

    async def one(mpn_key: str, lcsc: str | None) -> None:
        if not lcsc:
            async with lock:
                summary.skipped += 1
            return
        async with sem:
            try:
                detail = await ds.get_part(lcsc)
            except UpstreamError:
                async with lock:
                    summary.errors += 1
                return
        async with lock:
            if detail is None:
                summary.skipped += 1
                return
            records.append(OfferRecord(
                mpn_key=mpn_key, lcsc=detail.lcsc, distributor="lcsc",
                sku=detail.lcsc, price_usd=detail.price_usd,
                stock=detail.stock, in_stock=detail.stock > 0,
                currency="USD", recorded_at=stamp))

    await asyncio.gather(*(one(k, v) for k, v in entries))
    summary.recorded = await store.record_offers(records)
    return summary
