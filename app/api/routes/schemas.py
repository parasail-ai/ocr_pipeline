import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SchemaDefinition
from app.db.session import get_db
from app.models.schema_definition import SchemaCreate, SchemaList, SchemaRead

router = APIRouter(prefix="/schemas", tags=["Schemas"])


@router.post("", response_model=SchemaRead, status_code=status.HTTP_201_CREATED)
async def create_schema(payload: SchemaCreate, db: AsyncSession = Depends(get_db)) -> SchemaRead:
    exists = await db.scalar(select(SchemaDefinition).where(SchemaDefinition.name == payload.name))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Schema with that name already exists")

    schema = SchemaDefinition(
        name=payload.name,
        category=payload.category,
        description=payload.description,
        fields=[field.model_dump() for field in payload.fields],
    )
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    return SchemaRead.model_validate(schema)


@router.get("", response_model=SchemaList)
async def list_schemas(category: str | None = None, db: AsyncSession = Depends(get_db)) -> SchemaList:
    stmt = select(SchemaDefinition).order_by(SchemaDefinition.created_at.desc())
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
