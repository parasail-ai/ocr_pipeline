import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OcrModel
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/models", tags=["Models"])


class OcrModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., min_length=1, max_length=100)
    endpoint_url: str = Field(..., min_length=1, max_length=1024)
    api_key: str | None = Field(None, description="API key (will be encrypted)")
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)


class OcrModelUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    provider: str | None = Field(None, min_length=1, max_length=100)
    endpoint_url: str | None = Field(None, min_length=1, max_length=1024)
    api_key: str | None = Field(None, description="API key (will be encrypted)")
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class OcrModelResponse(BaseModel):
    model_config = {"from_attributes": True}
    
    id: uuid.UUID
    name: str
    display_name: str
    provider: str
    endpoint_url: str
    api_key_preview: str  # Masked version like "sk-****1234"
    config: dict[str, Any]
    is_active: bool
    created_at: str
    updated_at: str


class OcrModelListResponse(BaseModel):
    items: list[OcrModelResponse]
    total: int


def _mask_api_key(api_key_encrypted: str | None) -> str:
    """Return a masked preview of the API key"""
    if not api_key_encrypted:
        return "Not set"
    
    # For now, just show a masked version
    # In production, you'd decrypt and show first/last few chars
    if len(api_key_encrypted) > 8:
        return f"****{api_key_encrypted[-4:]}"
    return "****"


@router.get("", response_model=OcrModelListResponse)
async def list_models(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db)
) -> OcrModelListResponse:
    """
    List all OCR models
    
    Args:
        include_inactive: Include inactive models in the results
    """
    stmt = select(OcrModel).order_by(OcrModel.created_at.desc())
    
    if not include_inactive:
        stmt = stmt.where(OcrModel.is_active == True)
    
    result = await db.execute(stmt)
    models = list(result.scalars().all())
    
    response_items = [
        OcrModelResponse(
            id=model.id,
            name=model.name,
            display_name=model.display_name,
            provider=model.provider,
            endpoint_url=model.endpoint_url,
            api_key_preview=_mask_api_key(model.api_key_encrypted),
            config=model.model_config or {},
            is_active=model.is_active,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )
        for model in models
    ]
    
    return OcrModelListResponse(items=response_items, total=len(response_items))


@router.get("/{model_id}", response_model=OcrModelResponse)
async def get_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> OcrModelResponse:
    """Get a specific OCR model by ID"""
    model = await db.get(OcrModel, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    return OcrModelResponse(
        id=model.id,
        name=model.name,
        display_name=model.display_name,
        provider=model.provider,
        endpoint_url=model.endpoint_url,
        api_key_preview=_mask_api_key(model.api_key_encrypted),
        config=model.model_config or {},
        is_active=model.is_active,
        created_at=model.created_at.isoformat(),
        updated_at=model.updated_at.isoformat(),
    )


@router.post("", response_model=OcrModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    payload: OcrModelCreate,
    db: AsyncSession = Depends(get_db)
) -> OcrModelResponse:
    """Create a new OCR model"""
    
    # Check if model with this name already exists
    stmt = select(OcrModel).where(OcrModel.name == payload.name)
    existing = await db.scalar(stmt)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model with name '{payload.name}' already exists"
        )
    
    # For now, store API key as-is (in production, encrypt it)
    model = OcrModel(
        name=payload.name,
        display_name=payload.display_name,
        provider=payload.provider,
        endpoint_url=payload.endpoint_url,
        api_key_encrypted=payload.api_key,  # TODO: Encrypt this
        model_config=payload.config,
        is_active=payload.is_active,
    )
    
    db.add(model)
    await db.commit()
    await db.refresh(model)
    
    return OcrModelResponse(
        id=model.id,
        name=model.name,
        display_name=model.display_name,
        provider=model.provider,
        endpoint_url=model.endpoint_url,
        api_key_preview=_mask_api_key(model.api_key_encrypted),
        config=model.model_config or {},
        is_active=model.is_active,
        created_at=model.created_at.isoformat(),
        updated_at=model.updated_at.isoformat(),
    )


@router.patch("/{model_id}", response_model=OcrModelResponse)
async def update_model(
    model_id: uuid.UUID,
    payload: OcrModelUpdate,
    db: AsyncSession = Depends(get_db)
) -> OcrModelResponse:
    """Update an OCR model"""
    model = await db.get(OcrModel, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Update fields if provided
    if payload.display_name is not None:
        model.display_name = payload.display_name
    if payload.provider is not None:
        model.provider = payload.provider
    if payload.endpoint_url is not None:
        model.endpoint_url = payload.endpoint_url
    if payload.api_key is not None:
        model.api_key_encrypted = payload.api_key  # TODO: Encrypt this
    if payload.config is not None:
        model.model_config = payload.config
    if payload.is_active is not None:
        model.is_active = payload.is_active
    
    await db.commit()
    await db.refresh(model)
    
    return OcrModelResponse(
        id=model.id,
        name=model.name,
        display_name=model.display_name,
        provider=model.provider,
        endpoint_url=model.endpoint_url,
        api_key_preview=_mask_api_key(model.api_key_encrypted),
        config=model.model_config or {},
        is_active=model.is_active,
        created_at=model.created_at.isoformat(),
        updated_at=model.updated_at.isoformat(),
    )


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete an OCR model"""
    model = await db.get(OcrModel, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    await db.delete(model)
    await db.commit()
