import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user_optional
from app.db.models import SchemaDefinition, User
from app.db.session import get_db
from app.models.schema_definition import SchemaCreate, SchemaList, SchemaRead
from app.services.ai_schema_generator import create_ai_schema_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/schemas", tags=["Schemas"])


class AISchemaGenerateRequest(BaseModel):
    ocr_text: str
    document_type: str | None = None
    schema_name: str | None = None
    save_schema: bool = True


class AISchemaGenerateResponse(BaseModel):
    schema_name: str
    category: str | None = None
    description: str | None = None
    fields: list[dict]
    extracted_values: dict
    schema_id: uuid.UUID | None = None


@router.post("", response_model=SchemaRead, status_code=status.HTTP_201_CREATED)
async def create_schema(
    payload: SchemaCreate, 
    session_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
) -> SchemaRead:
    from app.services.auth import AuthService
    
    exists = await db.scalar(select(SchemaDefinition).where(SchemaDefinition.name == payload.name))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Schema with that name already exists")

    # Get user_id from session
    user_id = None
    if session_token:
        user_data = AuthService.get_user_from_session(session_token)
        if user_data:
            user_id = user_data.get("user_id")
    
    schema = SchemaDefinition(
        name=payload.name,
        category=payload.category,
        description=payload.description,
        fields=[field.model_dump() for field in payload.fields],
        user_id=user_id,
        is_public=False  # Default to private
    )
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    return SchemaRead.model_validate(schema)


@router.get("", response_model=SchemaList)
async def list_schemas(
    category: str | None = None, 
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> SchemaList:
    stmt = select(SchemaDefinition).order_by(SchemaDefinition.created_at.desc())
    
    # Filter out internal ad-hoc schema placeholder
    stmt = stmt.where(SchemaDefinition.name != "__ad_hoc_auto_generated__")
    
    # Apply access control based on user status
    if current_user is None:
        # Guest users: only public schemas
        stmt = stmt.where(SchemaDefinition.is_public == True)
    elif current_user.is_admin:
        # Admin: see all schemas
        pass
    else:
        # Logged-in users: their own schemas + public schemas
        stmt = stmt.where(
            (SchemaDefinition.user_id == current_user.id) | 
            (SchemaDefinition.is_public == True)
        )
    
    if category:
        stmt = stmt.where(SchemaDefinition.category == category)

    result = await db.execute(stmt)
    schemas = list(result.scalars().all())
    return SchemaList(items=[SchemaRead.model_validate(item) for item in schemas])


@router.get("/{schema_id}", response_model=SchemaRead)
async def get_schema(schema_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> SchemaRead:
    schema = await db.get(SchemaDefinition, schema_id)
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    return SchemaRead.model_validate(schema)


@router.patch("/{schema_id}", response_model=SchemaRead)
async def update_schema(
    schema_id: uuid.UUID,
    payload: SchemaCreate,
    db: AsyncSession = Depends(get_db)
) -> SchemaRead:
    """Update an existing schema."""
    schema = await db.get(SchemaDefinition, schema_id)
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    
    # Check if name is being changed and if it conflicts
    if payload.name != schema.name:
        exists = await db.scalar(select(SchemaDefinition).where(SchemaDefinition.name == payload.name))
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Schema with that name already exists")
    
    schema.name = payload.name
    schema.category = payload.category
    schema.description = payload.description
    schema.fields = [field.model_dump() for field in payload.fields]
    schema.version += 1
    
    await db.commit()
    await db.refresh(schema)
    return SchemaRead.model_validate(schema)


@router.patch("/{schema_id}/toggle-public", response_model=SchemaRead)
async def toggle_schema_public(
    schema_id: uuid.UUID,
    session_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
) -> SchemaRead:
    """Toggle schema public visibility (admin only)."""
    from app.services.auth import AuthService
    
    # Check admin permission
    if not AuthService.is_admin(session_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can change schema visibility"
        )
    
    schema = await db.get(SchemaDefinition, schema_id)
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    
    # Toggle is_public
    schema.is_public = not schema.is_public
    await db.commit()
    await db.refresh(schema)
    
    return SchemaRead.model_validate(schema)


@router.delete("/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schema(schema_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a schema."""
    schema = await db.get(SchemaDefinition, schema_id)
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    
    await db.delete(schema)
    await db.commit()


@router.post("/generate-ai", response_model=AISchemaGenerateResponse)
async def generate_schema_with_ai(
    payload: AISchemaGenerateRequest,
    db: AsyncSession = Depends(get_db)
) -> AISchemaGenerateResponse:
    """
    Generate a schema using AI analysis of OCR text.
    
    This endpoint uses the parasail-glm-46 model to:
    1. Analyze the OCR text
    2. Identify important fields
    3. Create extraction queries for each field
    4. Extract values from the text
    5. Optionally save the schema to the database
    """
    try:
        generator = create_ai_schema_generator()
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI schema generator not available: {str(e)}"
        )
    
    try:
        # Generate schema using AI
        result = await asyncio.to_thread(
            generator.generate_schema_from_ocr,
            payload.ocr_text,
            payload.document_type,
            payload.schema_name
        )
        
        schema_id = None
        
        # Save schema to database if requested
        if payload.save_schema:
            # Check if schema with this name already exists
            existing = await db.scalar(
                select(SchemaDefinition).where(SchemaDefinition.name == result['schema_name'])
            )
            
            if existing:
                logger.info(f"Schema '{result['schema_name']}' already exists, skipping save")
                schema_id = existing.id
            else:
                # Create new schema
                schema = SchemaDefinition(
                    name=result['schema_name'],
                    category=result.get('category'),
                    description=result.get('description'),
                    fields=result['fields'],
                )
                db.add(schema)
                await db.commit()
                await db.refresh(schema)
                schema_id = schema.id
                logger.info(f"Saved AI-generated schema: {result['schema_name']}")
        
        return AISchemaGenerateResponse(
            schema_name=result['schema_name'],
            category=result.get('category'),
            description=result.get('description'),
            fields=result['fields'],
            extracted_values=result['extracted_values'],
            schema_id=schema_id
        )
        
    except RuntimeError as e:
        logger.error(f"AI schema generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in AI schema generation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate schema with AI"
        )
