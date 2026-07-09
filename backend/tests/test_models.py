from datetime import datetime, timezone

from models.search import SearchResult, SearchResponse


def make_result(**over):
    base = dict(
        lcsc="C8734", mpn="STM32F103C8T6", brand=None, package="LQFP-48(7x7)",
        description="", stock=214596, price_usd=1.0371, datasheet_url=None,
        as_of=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    base.update(over)
    return SearchResult(**base)


def test_result_accepts_null_brand_and_datasheet():
    r = make_result()
    assert r.brand is None and r.datasheet_url is None


def test_response_shape():
    resp = SearchResponse(page=1, results=[make_result()])
    data = resp.model_dump(mode="json")
    assert data["page"] == 1
    assert set(data["results"][0].keys()) == {
        "lcsc", "mpn", "brand", "package", "description",
        "stock", "price_usd", "datasheet_url", "as_of",
    }
