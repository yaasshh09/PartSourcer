"""GET /api/browse and /api/browse/{slug}: spec-first finding, no prices."""

from fastapi import APIRouter, Depends, HTTPException, Request

from models.browse import BrowseResponse, CategoriesResponse
from services.browse import BadFilter, BrowseService, UnknownCategory, catalog
from services.datasource import UPSTREAM_STATUS, UpstreamError
from services.deps import get_browse_service

router = APIRouter(prefix="/api")


@router.get("/browse", response_model=CategoriesResponse)
async def categories() -> CategoriesResponse:
    return catalog()


@router.get("/browse/{slug}", response_model=BrowseResponse)
async def browse(slug: str, request: Request,
                 service: BrowseService = Depends(get_browse_service)
                 ) -> BrowseResponse:
    try:
        return await service.browse(slug, request.query_params.multi_items())
    except UnknownCategory:
        raise HTTPException(status_code=404,
                            detail=f"No category called '{slug[:40]}'.")
    except BadFilter as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=UPSTREAM_STATUS[exc.kind],
                            detail=str(exc)) from exc
