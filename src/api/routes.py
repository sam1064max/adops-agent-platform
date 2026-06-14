"""AdOps Copilot API routes — investigation-driven pipeline."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import Response

from src.api.dependencies import (
    get_db,
    get_qdrant_client,
    get_settings,
)
from src.api.metrics import query_count, ingest_count
from src.models.database import Campaign, DeliveryLog, InventoryMetadata
from src.models.schemas import (
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# -- Investigation response model -------------------------------------------------


class InvestigationResponse(BaseModel):
    summary: str
    primary_cause: str
    confidence: float
    evidence: List[dict] = Field(default_factory=list)
    supporting_factors: List[str] = Field(default_factory=list)
    recommendations: List[dict] = Field(default_factory=list)
    risk_level: str = "low"


# -- Data response models ---------------------------------------------------------


class CampaignResponse(BaseModel):
    campaign_id: str
    name: str
    advertiser: Optional[str] = None
    status: str
    budget: float
    spend: float
    impressions: int
    clicks: int
    ctr: float = 0.0
    pacing_ratio: float = 0.0
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class InventoryResponse(BaseModel):
    inventory_id: str
    publisher: str
    channel: str = ""
    region: str = ""
    device_type: str = ""
    content_category: str = ""
    status: str = "active"
    health_score: float = 0.0


class CampaignListRequest(BaseModel):
    advertiser: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    min_budget: Optional[float] = Field(default=None)
    max_budget: Optional[float] = Field(default=None)
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class DeliveryLogRequest(BaseModel):
    campaign_id: Optional[str] = Field(default=None)
    start_date: Optional[str] = Field(default=None)
    end_date: Optional[str] = Field(default=None)
    publisher: Optional[str] = Field(default=None)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class DeliveryLogResponse(BaseModel):
    log_id: int
    campaign_id: str
    timestamp: str
    impressions: int
    clicks: int
    spend: float
    publisher: Optional[str] = None
    geo: Optional[str] = None
    device: Optional[str] = None


# -- Investigation endpoint (primary) ---------------------------------------------


@router.post(
    "/ask",
    response_model=InvestigationResponse,
    status_code=status.HTTP_200_OK,
)
async def ask(request: QueryRequest):
    """Run full investigation pipeline: plan -> collect evidence -> hypothesize -> rank -> root cause -> recommend."""

    try:
        from src.investigation.orchestrator import InvestigationOrchestrator

        orchestrator = InvestigationOrchestrator()
        report = orchestrator.investigate(request.text)

        query_count.labels(
            issue_type=report.get("primary_cause", "general"),
            status="success",
        ).inc()

        return InvestigationResponse(
            summary=report.get("summary", "Investigation complete."),
            primary_cause=report.get("primary_cause", "No primary cause identified."),
            confidence=report.get("confidence", 0.0),
            evidence=report.get("evidence", []),
            supporting_factors=report.get("supporting_factors", []),
            recommendations=report.get("recommendations", []),
            risk_level=report.get("risk_level", "low"),
        )

    except Exception as exc:
        query_count.labels(issue_type="unknown", status="error").inc()
        logger.error("Investigation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation pipeline failed: {exc}",
        )


# -- Ingestion endpoint -----------------------------------------------------------


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_200_OK)
async def ingest(request: IngestRequest):
    """Trigger the RAG ingestion pipeline."""
    try:
        from src.ingestion.pipeline import IngestionPipeline
        from src.ingestion.vector_store import VectorStore

        qdrant = get_qdrant_client()
        settings = get_settings()

        vector_store = VectorStore(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            collection_name=settings.QDRANT_COLLECTION,
        )
        pipeline = IngestionPipeline(vector_store=vector_store, embedder=None)

        docs = []
        for row in request.payload:
            doc = type("Document", (), {
                "content": str(row),
                "metadata": {"data_type": request.data_type, "source": request.source or "api"},
            })()
            docs.append(doc)

        rows_embedded = pipeline.ingest_documents(docs) if docs else 0
        ingest_count.labels(data_type=request.data_type, status="success").inc()

        return IngestResponse(
            rows_ingested=rows_embedded,
            message=f"Successfully ingested {rows_embedded} rows",
        )
    except Exception as exc:
        ingest_count.labels(data_type=request.data_type, status="error").inc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {exc}")


# -- Investigation convenience endpoints ------------------------------------------


@router.post("/investigate", response_model=InvestigationResponse, status_code=status.HTTP_200_OK)
async def investigate(request: QueryRequest):
    """Alias for /ask — runs investigation pipeline."""
    return await ask(request)


@router.get("/campaign/{campaign_id}/investigate", response_model=InvestigationResponse, status_code=status.HTTP_200_OK)
async def investigate_campaign(campaign_id: str):
    """Investigate why a specific campaign is underperforming."""
    return await ask(QueryRequest(text=f"Investigate campaign {campaign_id} delivery performance"))


# -- Campaign endpoints -----------------------------------------------------------


@router.get("/campaign/{campaign_id}", response_model=CampaignResponse, status_code=status.HTTP_200_OK)
async def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Campaign {campaign_id} not found")

    pacing = 0.0
    if campaign.impressions and campaign.impressions > 0:
        pacing = round(min(campaign.impressions / max(campaign.target_impressions if hasattr(campaign, 'target_impressions') and campaign.target_impressions else campaign.impressions, 1) * 100, 100), 1)

    ctr = (campaign.clicks / campaign.impressions * 100) if campaign.impressions else 0.0
    return CampaignResponse(
        campaign_id=campaign.id,
        name=getattr(campaign, 'name', ''),
        advertiser=campaign.advertiser,
        status=campaign.status,
        budget=campaign.budget,
        spend=campaign.spend,
        impressions=campaign.impressions,
        clicks=campaign.clicks,
        ctr=round(ctr, 4),
        pacing_ratio=pacing,
        start_date=campaign.start_date.isoformat() if campaign.start_date else None,
        end_date=campaign.end_date.isoformat() if campaign.end_date else None,
    )


@router.post("/campaigns", response_model=List[CampaignResponse], status_code=status.HTTP_200_OK)
async def list_campaigns(request: CampaignListRequest, db: Session = Depends(get_db)):
    q = db.query(Campaign)
    if request.advertiser:
        q = q.filter(Campaign.advertiser.ilike(f"%{request.advertiser}%"))
    if request.status:
        q = q.filter(Campaign.status == request.status)
    if request.min_budget is not None:
        q = q.filter(Campaign.budget >= request.min_budget)
    if request.max_budget is not None:
        q = q.filter(Campaign.budget <= request.max_budget)

    results = []
    for c in q.offset(request.offset).limit(request.limit).all():
        ctr = (c.clicks / c.impressions * 100) if c.impressions else 0.0
        results.append(CampaignResponse(
            campaign_id=c.id, name=getattr(c, 'name', ''),
            advertiser=c.advertiser, status=c.status,
            budget=c.budget, spend=c.spend,
            impressions=c.impressions, clicks=c.clicks,
            ctr=round(ctr, 4), pacing_ratio=0.0,
            start_date=c.start_date.isoformat() if c.start_date else None,
            end_date=c.end_date.isoformat() if c.end_date else None,
        ))
    return results


# -- Inventory endpoint -----------------------------------------------------------


@router.get("/inventory/{inventory_id}", response_model=InventoryResponse, status_code=status.HTTP_200_OK)
async def get_inventory(inventory_id: str, db: Session = Depends(get_db)):
    item = db.query(InventoryMetadata).filter(InventoryMetadata.id == inventory_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Inventory {inventory_id} not found")

    return InventoryResponse(
        inventory_id=item.id,
        publisher=item.publisher,
        channel=getattr(item, 'channel', ''),
        region=getattr(item, 'region', ''),
        device_type=getattr(item, 'device_type', ''),
        content_category=getattr(item, 'content_category', ''),
        status=getattr(item, 'status', 'active'),
        health_score=getattr(item, 'viewability_rate', 0.0) * 100,
    )


# -- Delivery logs endpoint -------------------------------------------------------


@router.post("/delivery-logs", response_model=List[DeliveryLogResponse], status_code=status.HTTP_200_OK)
async def query_delivery_logs(request: DeliveryLogRequest, db: Session = Depends(get_db)):
    q = db.query(DeliveryLog)
    if request.campaign_id:
        q = q.filter(DeliveryLog.campaign_id == request.campaign_id)
    if request.publisher:
        q = q.filter(DeliveryLog.publisher.ilike(f"%{request.publisher}%"))
    if request.start_date:
        q = q.filter(DeliveryLog.timestamp >= request.start_date)
    if request.end_date:
        q = q.filter(DeliveryLog.timestamp <= request.end_date)

    return [
        DeliveryLogResponse(
            log_id=log.id, campaign_id=log.campaign_id,
            timestamp=log.timestamp.isoformat() if log.timestamp else "",
            impressions=log.impressions, clicks=log.clicks,
            spend=log.spend, publisher=log.publisher,
            geo=log.geo, device=log.device,
        )
        for log in q.order_by(DeliveryLog.timestamp.desc()).offset(request.offset).limit(request.limit).all()
    ]


# -- Health endpoint --------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    health = HealthResponse(version="0.1.0")
    try:
        qdrant = get_qdrant_client()
        qdrant.get_collections()
        health.qdrant = "ok"
    except Exception as exc:
        health.qdrant = f"error: {exc}"
        health.status = "degraded"
    try:
        from src.models.database import engine
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        health.postgres = "ok"
    except Exception as exc:
        health.postgres = f"error: {exc}"
        health.status = "degraded"
    return health


# -- Metrics endpoint -------------------------------------------------------------


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
