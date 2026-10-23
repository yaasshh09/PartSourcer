"""GET /api/status: how each distributor answered over the past day.

Built from the per-distributor outcome every search and part read already
stores with its cache row, so it reports what real requests met rather than a
synthetic probe, and it costs no extra upstream call or write.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from cache.store import CacheStore
from services.deps import get_cache_store
from services.part_service import ALL_DISTRIBUTORS

router = APIRouter(prefix="/api")

WINDOW_HOURS = 24
MAX_READS = 2000


@router.get("/status")
async def status(response: Response, store: CacheStore = Depends(get_cache_store)):
    since = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    try:
        rows = await store.recent_statuses(since, MAX_READS)
    except Exception as exc:                     # noqa: BLE001
        raise HTTPException(status_code=503,
                            detail="Status is unavailable right now") from exc

    dists = {d: {"distributor": d, "ok": 0, "problems": {}, "disabled": 0,
                 "last_ok_at": None, "last_problem": None} for d in ALL_DISTRIBUTORS}
    for at, statuses in rows:                    # newest first
        for s in statuses:
            d = dists.get(s.get("distributor"))
            if d is None:
                continue
            state = s.get("state")
            if state == "ok":
                d["ok"] += 1
                d["last_ok_at"] = d["last_ok_at"] or at.isoformat()
            elif state == "disabled":
                d["disabled"] += 1
            else:
                d["problems"][state] = d["problems"].get(state, 0) + 1
                d["last_problem"] = d["last_problem"] or {"state": state, "at": at.isoformat()}

    out = []
    for d in dists.values():
        seen = d["ok"] + d["disabled"] + sum(d["problems"].values())
        # None: no request touched it today, so nothing can be said.
        d["configured"] = None if not seen else d["disabled"] < seen
        del d["disabled"]
        out.append(d)
    response.headers["Cache-Control"] = "public, max-age=300"
    return {"window_hours": WINDOW_HOURS, "since": since.isoformat(),
            "reads": len(rows), "distributors": out}
