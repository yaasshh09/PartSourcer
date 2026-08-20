"""Bounds on what a caller may put in a query string or a path.

Not sanitising, bounding. Nothing here is interpolated into SQL, a shell or
markup, so there is no dangerous character to strip; the risk is cost. An
unbounded `q` becomes an unbounded upstream URL, and an unbounded `page` walks
a free community API as deep as anyone cares to ask. These are the ceilings
that make one request cost a known amount.
"""

from fastapi import HTTPException

#: Longer than any real manufacturer part number or spec phrase. The longest
#: MPN in the sample catalogues is under 40 characters.
MAX_QUERY_LEN = 200

#: Upstream results thin out long before this. Deep paging is a crawler, not a
#: person looking for a part.
MAX_PAGE = 50

#: Real MPNs reach the mid thirties with a package suffix. 128 leaves room for
#: an unusual one and still refuses a payload wearing a part number's clothes.
MAX_KEY_LEN = 128


def check_key_length(raw: str) -> None:
    """Reject an over-long part key before it reaches the cache or upstream.

    422 rather than 404: 404 would claim the part was looked for and missing,
    which is not what happened.
    """
    if len(raw) > MAX_KEY_LEN:
        raise HTTPException(
            status_code=422,
            detail=f"mpn_key: at most {MAX_KEY_LEN} characters")
