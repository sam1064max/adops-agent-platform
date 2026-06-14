"""AdOps Agent Platform API routes.

All endpoints for the agent pipeline, data queries, health, and metrics.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import Response

from src.agents.analysis_agent import AnalysisAgent
from src.agents.query_agent import QueryAgent
from src.agents.response_agent import ResponseAgent
from src.agents.retrieval_agent import RetrievalAgent
from src.api.dependencies import (
    get_analysis_agent,
    get_db,
    get_embedding_model,
    get_qdrant_client,
    get_query_agent,
    get_retrieval_agent,
    get_response_agent,
    get_settings,
)
from src.api.metrics import query_count, ingest_count
from src.models.database import Campaign, DeliveryLog, InventoryMetadata
from src.models.schemas import (
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# -- Request / Response models for data endpoints --------------------------------


class CampaignResponse(BaseModel):
    campaign_id: str
    name: str
    advertiser: Optional[str] = None
    status: str
    budget: float
    spend: float
    impressions: int
    clicks: int
    conversions: int
    ctr: float = 0.0
    cpa: float = 0.0
    roas: float = 0.0
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class InventoryResponse(BaseModel):
    inventory_id: str
    publisher: str
    domain: Optional[str] = None
    ad_format: str
    floor_price: float
    viewability_rate: float
    brand_safety_score: float
    available_impressions: int


class CampaignListRequest(BaseModel):
    advertiser: Optional[str] = Field(default=None, description="Filter by advertiser")
    status: Optional[str] = Field(default=None, description="Filter by status")
    min_budget: Optional[float] = Field(default=None, description="Minimum budget")
    max_budget: Optional[float] = Field(default=None, description="Maximum budget")
    limit: int = Field(default=50, ge=1, le=500, description="Max results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class DeliveryLogRequest(BaseModel):
    campaign_id: Optional[str] = Field(default=None, description="Filter by campaign")
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)")
    publisher: Optional[str] = Field(default=None, description="Filter by publisher")
    limit: int = Field(default=100, ge=1, le=1000, description="Max results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class DeliveryLogResponse(BaseModel):
    log_id: int
    campaign_id: str
    timestamp: str
    impressions: int
    clicks: int
    spend: float
    publisher: Optional[str] = None
    domain: Optional[str] = None
    geo: Optional[str] = None
    device: Optional[str] = None
    fraud_score: float


# -- Agent pipeline endpoint ----------------------------------------------------


@router.post("/ask", response_model=QueryResponse, status_code=status.HTTP_200_OK)
async def ask(
    request: QueryRequest,
    query_agent: QueryAgent = Depends(get_query_agent),
    retrieval_agent: RetrievalAgent = Depends(get_retrieval_agent),
    analysis_agent: AnalysisAgent = Depends(get_analysis_agent),
    response_agent: ResponseAgent = Depends(get_response_agent),
):
    """Run the full agent pipeline: classify -> retrieve -> analyse -> respond."""
    try:
        classified = query_agent.classify_issue(request.text)

        retrieval_ctx = retrieval_agent.retrieve(
            text=request.text,
            entities=classified.get("entities"),
            time_range=classified.get("time_range"),
        )

        analysis = analysis_agent.analyse(
            issue_type=classified.get("issue_type", "general"),
            entities=classified.get("entities", []),
            retrieval_context=retrieval_ctx,
        )

        response = response_agent.synthesise(
            query_text=request.text,
            classified=classified,
            retrieval_context=retrieval_ctx,
            analysis=analysis,
        )

        query_count.labels(
            issue_type=classified.get("issue_type", "general"),
            status="success",
        ).inc()

        logger.info("Pipeline completed: issue=%s", classified.get("issue_type"))
        return response

    except Exception as exc:
        query_count.labels(issue_type="unknown", status="error").inc()
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent pipeline failed: {exc}",
        )


# -- Ingestion endpoint ---------------------------------------------------------


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_200_OK)
async def ingest(request: IngestRequest):
    """Trigger the ingestion pipeline to load data into the vector store."""
    try:
        from src.ingestion.pipeline import IngestionPipeline
        from src.ingestion.vector_store import VectorStore
        from src.ingestion.embedder import Embedder

        qdrant = get_qdrant_client()
        embedding_model = get_embedding_model()
        settings = get_settings()

        vector_store = VectorStore(
            client=qdrant,
            collection_name=settings.QDRANT_COLLECTION,
        )
        embedder = Embedder(model=embedding_model)
        pipeline = IngestionPipeline(vector_store=vector_store, embedder=embedder)

        docs = []
        for row in request.payload:
            doc = type("Document", (), {
                "content": str(row),
                "metadata": {
                    "data_type": request.data_type,
                    "source": request.source or "api",
                },
            })()
            docs.append(doc)

        rows_embedded = pipeline.ingest_documents(docs) if docs else 0

        ingest_count.labels(
            data_type=request.data_type,
            status="success",
        ).inc()

        logger.info(
            "Ingested %d rows (type=%s)", rows_embedded, request.data_type
        )
        return IngestResponse(
            rows_ingested=rows_embedded,
            message=f"Successfully ingested {rows_embedded} rows",
        )

    except Exception as exc:
        ingest_count.labels(data_type=request.data_type, status="error").inc()
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {exc}",
        )


# -- Campaign endpoints ---------------------------------------------------------


@router.get(
    "/campaign/{campaign_id}",
    response_model=CampaignResponse,
    status_code=status.HTTP_200_OK,
)
async def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
):
    """Return campaign data from the database."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    ctr = (campaign.clicks / campaign.impressions * 100) if campaign.impressions else 0.0
    cpa = (campaign.spend / campaign.conversions) if campaign.conversions else 0.0
    roas = (campaign.spend and campaign.clicks / campaign.spend * 10.0) or 0.0

    return CampaignResponse(
        campaign_id=campaign.id,
        name=campaign.name,
        advertiser=campaign.advertiser,
        status=campaign.status,
        budget=campaign.budget,
        spend=campaign.spend,
        impressions=campaign.impressions,
        clicks=campaign.clicks,
        conversions=campaign.conversions,
        ctr=round(ctr, 4),
        cpa=round(cpa, 2),
        roas=round(roas, 4),
        start_date=campaign.start_date.isoformat() if campaign.start_date else None,
        end_date=campaign.end_date.isoformat() if campaign.end_date else None,
    )


@router.post(
    "/campaigns",
    response_model=List[CampaignResponse],
    status_code=status.HTTP_200_OK,
)
async def list_campaigns(
    request: CampaignListRequest,
    db: Session = Depends(get_db),
):
    """List campaigns with optional filters."""
    query = db.query(Campaign)

    if request.advertiser:
        query = query.filter(Campaign.advertiser.ilike(f"%{request.advertiser}%"))
    if request.status:
        query = query.filter(Campaign.status == request.status)
    if request.min_budget is not None:
        query = query.filter(Campaign.budget >= request.min_budget)
    if request.max_budget is not None:
        query = query.filter(Campaign.budget <= request.max_budget)

    campaigns = query.offset(request.offset).limit(request.limit).all()

    results = []
    for c in campaigns:
        ctr = (c.clicks / c.impressions * 100) if c.impressions else 0.0
        cpa = (c.spend / c.conversions) if c.conversions else 0.0
        roas = (c.spend and c.clicks / c.spend * 10.0) or 0.0

        results.append(CampaignResponse(
            campaign_id=c.id,
            name=c.name,
            advertiser=c.advertiser,
            status=c.status,
            budget=c.budget,
            spend=c.spend,
            impressions=c.impressions,
            clicks=c.clicks,
            conversions=c.conversions,
            ctr=round(ctr, 4),
            cpa=round(cpa, 2),
            roas=round(roas, 4),
            start_date=c.start_date.isoformat() if c.start_date else None,
            end_date=c.end_date.isoformat() if c.end_date else None,
        ))

    return results


# -- Inventory endpoint ----------------------------------------------------------


@router.get(
    "/inventory/{inventory_id}",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_inventory(
    inventory_id: str,
    db: Session = Depends(get_db),
):
    """Return inventory metadata from the database."""
    item = (
        db.query(InventoryMetadata)
        .filter(InventoryMetadata.id == inventory_id)
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory {inventory_id} not found",
        )

    return InventoryResponse(
        inventory_id=item.id,
        publisher=item.publisher,
        domain=item.domain,
        ad_format=item.ad_format,
        floor_price=item.floor_price,
        viewability_rate=item.viewability_rate,
        brand_safety_score=item.brand_safety_score,
        available_impressions=item.available_impressions,
    )


# -- Delivery logs endpoint -----------------------------------------------------


@router.post(
    "/delivery-logs",
    response_model=List[DeliveryLogResponse],
    status_code=status.HTTP_200_OK,
)
async def query_delivery_logs(
    request: DeliveryLogRequest,
    db: Session = Depends(get_db),
):
    """Query delivery logs with filters."""
    query = db.query(DeliveryLog)

    if request.campaign_id:
        query = query.filter(DeliveryLog.campaign_id == request.campaign_id)
    if request.publisher:
        query = query.filter(DeliveryLog.publisher.ilike(f"%{request.publisher}%"))
    if request.start_date:
        query = query.filter(DeliveryLog.timestamp >= request.start_date)
    if request.end_date:
        query = query.filter(DeliveryLog.timestamp <= request.end_date)

    logs = query.order_by(DeliveryLog.timestamp.desc()).offset(request.offset).limit(request.limit).all()

    results = []
    for log in logs:
        results.append(DeliveryLogResponse(
            log_id=log.id,
            campaign_id=log.campaign_id,
            timestamp=log.timestamp.isoformat() if log.timestamp else "",
            impressions=log.impressions,
            clicks=log.clicks,
            spend=log.spend,
            publisher=log.publisher,
            domain=log.domain,
            geo=log.geo,
            device=log.device,
            fraud_score=log.fraud_score,
        ))

    return results


# -- Health endpoint -------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """Health check with Qdrant and DB status."""
    settings = get_settings()
    health = HealthResponse(version="0.1.0")

    # Check Qdrant
    try:
        qdrant = get_qdrant_client()
        qdrant.get_collections()
        health.qdrant = "ok"
    except Exception as exc:
        health.qdrant = f"error: {exc}"
        health.status = "degraded"

    # Check PostgreSQL
    try:
        from src.models.database import engine
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        health.postgres = "ok"
    except Exception as exc:
        health.postgres = f"error: {exc}"
        health.status = "degraded"

    return health


# -- Metrics endpoint -----------------------------------------------------------


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def metrics():
    """Return Prometheus metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
