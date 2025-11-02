"""API routes for folder management"""
from uuid import UUID
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Folder, Document
from app.db.session import get_async_session

router = APIRouter(prefix="/folders", tags=["folders"])


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: UUID | None = None


class FolderUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    parent_id: UUID | None = None


class FolderResponse(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None
    path: str
    document_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class FolderListResponse(BaseModel):
    items: list[FolderResponse]
    total: int


@router.post("", response_model=FolderResponse, status_code=201)
async def create_folder(
    folder_data: FolderCreate,
    session: AsyncSession = Depends(get_async_session)
) -> Any:
    """Create a new folder"""
    
    # Build the path
    path = folder_data.name
    if folder_data.parent_id:
        # Get parent folder
        result = await session.execute(
            select(Folder).where(Folder.id == folder_data.parent_id)
        )
        parent = result.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        path = f"{parent.path}/{folder_data.name}"
    
    # Create folder
    folder = Folder(
        name=folder_data.name,
        parent_id=folder_data.parent_id,
        path=path
    )
    
    session.add(folder)
    await session.commit()
    await session.refresh(folder)
    
    # Count documents in folder
    doc_count_result = await session.execute(
        select(func.count(Document.id)).where(Document.folder_id == folder.id)
    )
    doc_count = doc_count_result.scalar() or 0
    
    return FolderResponse(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        path=folder.path,
        document_count=doc_count,
        created_at=folder.created_at.isoformat(),
        updated_at=folder.updated_at.isoformat()
    )


@router.get("", response_model=FolderListResponse)
async def list_folders(
    session: AsyncSession = Depends(get_async_session)
) -> Any:
    """List all folders with document counts"""
    
    result = await session.execute(
        select(Folder).order_by(Folder.path)
    )
    folders = result.scalars().all()
    
    # Get document counts for all folders
    folder_responses = []
    for folder in folders:
        doc_count_result = await session.execute(
            select(func.count(Document.id)).where(Document.folder_id == folder.id)
        )
        doc_count = doc_count_result.scalar() or 0
        
        folder_responses.append(FolderResponse(
            id=folder.id,
            name=folder.name,
            parent_id=folder.parent_id,
            path=folder.path,
            document_count=doc_count,
            created_at=folder.created_at.isoformat(),
            updated_at=folder.updated_at.isoformat()
        ))
    
    return FolderListResponse(
        items=folder_responses,
        total=len(folder_responses)
    )


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: UUID,
    session: AsyncSession = Depends(get_async_session)
) -> Any:
    """Get a specific folder by ID"""
    
    result = await session.execute(
        select(Folder).where(Folder.id == folder_id)
    )
    folder = result.scalar_one_or_none()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Count documents in folder
    doc_count_result = await session.execute(
        select(func.count(Document.id)).where(Document.folder_id == folder.id)
    )
    doc_count = doc_count_result.scalar() or 0
    
    return FolderResponse(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        path=folder.path,
        document_count=doc_count,
        created_at=folder.created_at.isoformat(),
        updated_at=folder.updated_at.isoformat()
    )


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: UUID,
    folder_data: FolderUpdate,
    session: AsyncSession = Depends(get_async_session)
) -> Any:
    """Update a folder"""
    
    result = await session.execute(
        select(Folder).where(Folder.id == folder_id)
    )
    folder = result.scalar_one_or_none()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Update fields
    if folder_data.name is not None:
        folder.name = folder_data.name
        
        # Rebuild path
        if folder.parent_id:
            parent_result = await session.execute(
                select(Folder).where(Folder.id == folder.parent_id)
            )
            parent = parent_result.scalar_one_or_none()
            if parent:
                folder.path = f"{parent.path}/{folder.name}"
        else:
            folder.path = folder.name
    
    if folder_data.parent_id is not None:
        # Validate parent exists
        if folder_data.parent_id != folder.parent_id:
            parent_result = await session.execute(
                select(Folder).where(Folder.id == folder_data.parent_id)
            )
            parent = parent_result.scalar_one_or_none()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent folder not found")
            
            # Check for circular reference
            if folder_data.parent_id == folder.id:
                raise HTTPException(status_code=400, detail="Folder cannot be its own parent")
            
            folder.parent_id = folder_data.parent_id
            folder.path = f"{parent.path}/{folder.name}"
    
    await session.commit()
    await session.refresh(folder)
    
    # Count documents
    doc_count_result = await session.execute(
        select(func.count(Document.id)).where(Document.folder_id == folder.id)
    )
    doc_count = doc_count_result.scalar() or 0
    
    return FolderResponse(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        path=folder.path,
        document_count=doc_count,
        created_at=folder.created_at.isoformat(),
        updated_at=folder.updated_at.isoformat()
    )


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: UUID,
    session: AsyncSession = Depends(get_async_session)
) -> None:
    """Delete a folder and move its documents to uncategorized"""
    
    result = await session.execute(
        select(Folder).where(Folder.id == folder_id)
    )
    folder = result.scalar_one_or_none()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Move documents to uncategorized (set folder_id to None)
    await session.execute(
        select(Document).where(Document.folder_id == folder_id)
    )
    documents = result.scalars().all()
    for doc in documents:
        doc.folder_id = None
    
    # Delete the folder (children will be cascade deleted)
    await session.delete(folder)
    await session.commit()


@router.post("/{folder_id}/documents/{document_id}", status_code=204)
async def move_document_to_folder(
    folder_id: UUID,
    document_id: UUID,
    session: AsyncSession = Depends(get_async_session)
) -> None:
    """Move a document to a folder"""
    
    # Verify folder exists
    folder_result = await session.execute(
        select(Folder).where(Folder.id == folder_id)
    )
    folder = folder_result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Get document
    doc_result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = doc_result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Move document
    document.folder_id = folder_id
    await session.commit()


@router.delete("/documents/{document_id}/folder", status_code=204)
async def remove_document_from_folder(
    document_id: UUID,
    session: AsyncSession = Depends(get_async_session)
) -> None:
    """Remove a document from its folder (move to uncategorized)"""
    
    # Get document
    doc_result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = doc_result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Remove from folder
    document.folder_id = None
    await session.commit()
