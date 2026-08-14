"""RawListing to and from a JSON-safe dict.

One module owns this conversion because the cache's central property depends
on it: a listing read back must equal the listing that went in, so merging
cached rows produces exactly what merging live rows would.
"""

from dataclasses import asdict, fields
from datetime import datetime

from services.adapters.base import RawListing

_FIELD_NAMES = {f.name for f in fields(RawListing)}


def listing_to_dict(listing: RawListing) -> dict:
    data = asdict(listing)
    data["as_of"] = listing.as_of.isoformat()
    return data


def listing_from_dict(data: dict) -> RawListing:
    # Unknown keys are dropped rather than raising, so a row written by an
    # older build cannot break a read. A missing key still raises, because a
    # silently defaulted field would be an invented fact about a real listing.
    known = {k: v for k, v in data.items() if k in _FIELD_NAMES}
    known["as_of"] = datetime.fromisoformat(known["as_of"])
    return RawListing(**known)
