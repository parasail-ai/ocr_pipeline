import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentMetrics
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview")
async def get_analytics_overview(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get analytics overview with key metrics."""
    
    try:
        # Calculate date 30 days ago
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Requests per day for last 30 days
    requests_per_day_query = (
        select(
            func.date(DocumentMetrics.created_at).label('date'),
            func.count(DocumentMetrics.id).label('count')
        )
        .where(DocumentMetrics.created_at >= thirty_days_ago)
        .group_by(func.date(DocumentMetrics.created_at))
        .order_by(func.date(DocumentMetrics.created_at))
    )
    requests_per_day_result = await db.execute(requests_per_day_query)
    requests_per_day = [
        {"date": str(row.date), "count": row.count}
        for row in requests_per_day_result.all()
    ]
    
    # Model usage counts
    model_usage_query = (
        select(
            DocumentMetrics.ocr_model,
            func.count(DocumentMetrics.id).label('count')
        )
        .where(DocumentMetrics.ocr_model.isnot(None))
        .group_by(DocumentMetrics.ocr_model)
        .order_by(func.count(DocumentMetrics.id).desc())
    )
    model_usage_result = await db.execute(model_usage_query)
    model_usage_counts = [
        {"model": row.ocr_model, "count": row.count}
        for row in model_usage_result.all()
    ]
    
    # Total tokens per model
    tokens_per_model_query = (
        select(
            DocumentMetrics.ocr_model,
            func.sum(DocumentMetrics.prompt_tokens).label('prompt_tokens'),
            func.sum(DocumentMetrics.completion_tokens).label('completion_tokens'),
            func.sum(DocumentMetrics.total_tokens).label('total_tokens')
        )
        .where(DocumentMetrics.ocr_model.isnot(None))
        .where(DocumentMetrics.total_tokens.isnot(None))
        .group_by(DocumentMetrics.ocr_model)
        .order_by(func.sum(DocumentMetrics.total_tokens).desc())
    )
    tokens_per_model_result = await db.execute(tokens_per_model_query)
    tokens_per_model = [
        {
            "model": row.ocr_model,
            "prompt_tokens": row.prompt_tokens or 0,
            "completion_tokens": row.completion_tokens or 0,
            "total_tokens": row.total_tokens or 0
        }
        for row in tokens_per_model_result.all()
    ]
    
    # Average duration per model (ms per token)
    performance_query = (
        select(
            DocumentMetrics.ocr_model,
            func.avg(DocumentMetrics.ocr_duration_ms).label('avg_duration_ms'),
            func.avg(DocumentMetrics.total_tokens).label('avg_tokens'),
            func.count(DocumentMetrics.id).label('count')
        )
        .where(DocumentMetrics.ocr_model.isnot(None))
        .where(DocumentMetrics.ocr_duration_ms.isnot(None))
        .where(DocumentMetrics.total_tokens.isnot(None))
        .where(DocumentMetrics.total_tokens > 0)
        .group_by(DocumentMetrics.ocr_model)
    )
    performance_result = await db.execute(performance_query)
    performance_per_model = [
        {
            "model": row.ocr_model,
            "avg_duration_ms": round(row.avg_duration_ms, 2) if row.avg_duration_ms else 0,
            "avg_tokens": round(row.avg_tokens, 2) if row.avg_tokens else 0,
            "ms_per_token": round(row.avg_duration_ms / row.avg_tokens, 4) if row.avg_tokens and row.avg_duration_ms else 0,
            "count": row.count
        }
        for row in performance_result.all()
    ]
    
    # Unique IP addresses with request counts
    ip_counts_query = (
        select(
            DocumentMetrics.ip_address,
            func.count(DocumentMetrics.id).label('count')
        )
        .where(DocumentMetrics.ip_address.isnot(None))
        .group_by(DocumentMetrics.ip_address)
        .order_by(func.count(DocumentMetrics.id).desc())
    )
    ip_counts_result = await db.execute(ip_counts_query)
    ip_addresses = [
        {"ip_address": row.ip_address, "count": row.count}
        for row in ip_counts_result.all()
    ]
    
    # Total unique IPs
    unique_ips_query = select(func.count(func.distinct(DocumentMetrics.ip_address))).where(
        DocumentMetrics.ip_address.isnot(None)
    )
    unique_ips_count = await db.scalar(unique_ips_query) or 0
    
        return {
            "requests_per_day": requests_per_day,
            "model_usage_counts": model_usage_counts,
            "tokens_per_model": tokens_per_model,
            "performance_per_model": performance_per_model,
            "ip_addresses": ip_addresses,
            "unique_ips_count": unique_ips_count,
        }
    except Exception as e:
        logger.exception("Error fetching analytics data", exc_info=e)
        # Return empty data structure if table doesn't exist or other error
        return {
            "requests_per_day": [],
            "model_usage_counts": [],
            "tokens_per_model": [],
            "performance_per_model": [],
            "ip_addresses": [],
            "unique_ips_count": 0,
            "error": "Analytics data unavailable. Database migration may be needed."
        }
