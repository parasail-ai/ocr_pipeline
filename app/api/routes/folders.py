"""API routes for folder management"""
from uuid import UUID
from typing import Any, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Folder, Document
from app.db.session import get_db
from app.services.auth import AuthService

router = APIRouter(prefix="/folders", tags=["folders"])


# TEMPORARILY DISABLED - is_trash and is_system columns not yet in database
# async def get_or_create_trash_folder(db: AsyncSession) -> Folder:
#     """Get or create the system trash folder."""
#     # Check if trash folder exists
#     stmt = select(Folder).where(Folder.is_trash == True)
#     trash_folder = await db.scalar(stmt)
#     
#     if not trash_folder:
#         # Create trash folder
#         trash_folder = Folder(
#             name="🗑️ Trash",
#             path="/Trash",
#             is_system=True,
#             is_trash=True,
#         )
#         db.add(trash_folder)
#         await db.flush()
#     
#     return trash_folder


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
    is_system: bool = False
    is_trash: bool = False
    is_home: bool = False
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
    session: AsyncSession = Depends(get_db)
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


# TEMPORARILY DISABLED - is_trash and is_system columns not yet in database
# async def get_or_create_trash_folder(session: AsyncSession) -> Folder:
#     """Get or create the trash folder"""
#     result = await session.execute(
#         select(Folder).where(Folder.is_trash == True)
#     )
#     trash_folder = result.scalar_one_or_none()
#     
#     if not trash_folder:
#         trash_folder = Folder(
#             name="🗑️ Trash",
#             path="🗑️ Trash",
#             is_system=True,
#             is_trash=True
#         )
#         session.add(trash_folder)
#         await session.commit()
#         await session.refresh(trash_folder)
#     
#     return trash_folder


async def get_or_create_trash_folder(session: AsyncSession) -> Folder:
    """Get or create the trash folder"""
    try:
        result = await session.execute(
            select(Folder).where(Folder.is_trash == True).limit(1)
        )
        trash_folder = result.scalars().first()
        
        if not trash_folder:
            trash_folder = Folder(
                name="🗑️ Trash",
                path="🗑️ Trash",
                is_system=True,
                is_trash=True
            )
            session.add(trash_folder)
            await session.commit()
            await session.refresh(trash_folder)
        
        return trash_folder
    except Exception as e:
        # If is_trash column doesn't exist yet or any error, rollback and return None
        await session.rollback()
        return None


@router.get("", response_model=FolderListResponse)
async def list_folders(
    request: Request,
    session: AsyncSession = Depends(get_db)
) -> Any:
    """List all folders with document counts"""
    
    # Ensure trash folder exists
    await get_or_create_trash_folder(session)
    
    # Check if user is admin and get current user ID
    session_token = request.cookies.get("session_token")
    is_admin = AuthService.is_admin(session_token)
    current_user_id = None
    
    if session_token:
        user_data = AuthService.get_user_from_session(session_token)
        if user_data and user_data.get("user_id"):
            try:
                from uuid import UUID
                current_user_id = UUID(user_data.get("user_id"))
            except (ValueError, TypeError):
                pass
    
    result = await session.execute(
        select(Folder).order_by(Folder.path)
    )
    folders = result.scalars().all()
    
    # Get document counts for all folders
    folder_responses = []
    for folder in folders:
        # Skip trash folder for non-admin users
        if folder.is_trash and not is_admin:
            continue
        
        # Skip other users' home folders
        if folder.is_home and folder.user_id != current_user_id and not is_admin:
            continue
        
        # Count documents with same user filtering as document list
        if is_admin:
            # Admin sees all documents in folder
            doc_count_query = select(func.count(Document.id)).where(Document.folder_id == folder.id)
        elif current_user_id:
            # Logged-in user: count their docs + guest docs in this folder
            doc_count_query = select(func.count(Document.id)).where(
                Document.folder_id == folder.id,
                (Document.user_id == current_user_id) | (Document.user_id.is_(None))
            )
        else:
            # Guest: count only guest docs in this folder
            doc_count_query = select(func.count(Document.id)).where(
                Document.folder_id == folder.id,
                Document.user_id.is_(None)
            )
        
        doc_count_result = await session.execute(doc_count_query)
        doc_count = doc_count_result.scalar() or 0
        
        folder_responses.append(FolderResponse(
            id=folder.id,
            name=folder.name,
            parent_id=folder.parent_id,
            path=folder.path,
            document_count=doc_count,
            is_system=folder.is_system if hasattr(folder, 'is_system') else False,
            is_trash=folder.is_trash if hasattr(folder, 'is_trash') else False,
            is_home=folder.is_home if hasattr(folder, 'is_home') else False,
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
    session: AsyncSession = Depends(get_db)
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
        # is_system=folder.is_system,  # DISABLED
        # is_trash=folder.is_trash,  # DISABLED
        created_at=folder.created_at.isoformat(),
        updated_at=folder.updated_at.isoformat()
    )


# TEMPORARILY DISABLED - trash folder functionality until migration runs
# @router.post("/init-trash", response_model=FolderResponse, status_code=201)
# async def init_trash_folder(
#     session: AsyncSession = Depends(get_db)
# ) -> Any:
#     """Initialize trash folder if it doesn't exist"""
#     trash_folder = await get_or_create_trash_folder(session)
#     
#     # Count documents in folder
#     doc_count_result = await session.execute(
#         select(func.count(Document.id)).where(Document.folder_id == trash_folder.id)
#     )
#     doc_count = doc_count_result.scalar() or 0
#     
#     return FolderResponse(
#         id=trash_folder.id,
#         name=trash_folder.name,
#         parent_id=trash_folder.parent_id,
#         path=trash_folder.path,
#         document_count=doc_count,
#         is_system=trash_folder.is_system,
#         is_trash=trash_folder.is_trash,
#         created_at=trash_folder.created_at.isoformat(),
#         updated_at=trash_folder.updated_at.isoformat()
#     )


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: UUID,
    folder_data: FolderUpdate,
    session: AsyncSession = Depends(get_db)
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
    session: AsyncSession = Depends(get_db)
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
    session: AsyncSession = Depends(get_db)
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
    session: AsyncSession = Depends(get_db)
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
