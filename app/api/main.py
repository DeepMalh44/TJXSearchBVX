"""FastAPI entrypoint serving the API and compiled SPA from one process."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import require_search_service, require_user
from app.api.models import SearchRequest, SearchResponse, SkillRequest, SkillResponse, SkillResult
from app.api.services import AzureServices, get_services, safe_blob_name
from app.api.settings import get_settings

app = FastAPI(title="TJX Retail Search", docs_url=None, redoc_url=None)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def public_config() -> dict[str, str]:
    settings = get_settings()
    return {
        "tenantId": settings.azure_tenant_id,
        "clientId": settings.azure_ad_client_id,
        "apiScope": f"{settings.entra_api_audience}/Search.Access",
    }


@app.get("/readyz")
def readiness(services: Annotated[AzureServices, Depends(get_services)]) -> dict[str, str]:
    try:
        services.ready()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Search dependency is unavailable") from exc
    return {"status": "ready"}


@app.post("/api/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    _user: Annotated[dict[str, Any], Depends(require_user)],
    services: Annotated[AzureServices, Depends(get_services)],
) -> SearchResponse:
    return services.search_products(request)


@app.post("/api/skills/product-enrichment", response_model=SkillResponse)
def enrich_products(
    request: SkillRequest,
    _search: Annotated[dict[str, Any], Depends(require_search_service)],
    services: Annotated[AzureServices, Depends(get_services)],
) -> SkillResponse:
    results: list[SkillResult] = []
    for record in request.values:
        try:
            output = services.enrich_product(
                record.data.imageUrl, record.data.name, record.data.category
            )
            results.append(SkillResult(recordId=record.recordId, data=output))
        except Exception:
            results.append(
                SkillResult(
                    recordId=record.recordId,
                    errors=[{"message": "Product enrichment failed"}],
                )
            )
    return SkillResponse(values=results)


@app.get("/api/images/{blob_name}")
def image(
    blob_name: str,
    _user: Annotated[dict[str, Any], Depends(require_user)],
    services: Annotated[AzureServices, Depends(get_services)],
) -> StreamingResponse:
    try:
        chunks, content_type = services.download_image(safe_blob_name(blob_name))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamingResponse(
        chunks,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = STATIC_DIR / path
        return FileResponse(candidate if candidate.is_file() else STATIC_DIR / "index.html")
