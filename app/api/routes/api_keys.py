"""API routes for user API key management."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.models.auth import (
    UserApiKeyCreate,
    UserApiKeyCreated,
    UserApiKeyList,
    UserApiKeyRead,
    UserApiKeyUpdate,
)
from app.services import api_key_service

router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])


@router.post("", response_model=UserApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: UserApiKeyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    Create a new API key for the authenticated user.
    
    The API key will be returned only once. Make sure to store it securely.
    """
    try:
        # Create the API key
        api_key, plain_key = api_key_service.create_api_key(
            db=db,
            user_id=current_user.id,
            name=key_data.name,
            expires_at=key_data.expires_at,
        )
        
        # Convert to response model
        key_info = UserApiKeyRead.model_validate(api_key)
        
        return UserApiKeyCreated(
            key=plain_key,
            key_info=key_info,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}",
        )


@router.get("", response_model=UserApiKeyList)
async def list_api_keys(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """List all API keys for the authenticated user."""
    try:
        api_keys = api_key_service.get_user_api_keys(db, current_user.id)
        
        return UserApiKeyList(
            items=[UserApiKeyRead.model_validate(key) for key in api_keys],
            total=len(api_keys),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}",
        )


@router.patch("/{key_id}", response_model=UserApiKeyRead)
async def update_api_key(
    key_id: uuid.UUID,
    key_data: UserApiKeyUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """Update an API key's name."""
    try:
        updated_key = api_key_service.update_api_key_name(
            db=db,
            key_id=key_id,
            user_id=current_user.id,
            new_name=key_data.name,
        )
        
        if not updated_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )
        
        return UserApiKeyRead.model_validate(updated_key)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update API key: {str(e)}",
        )


@router.post("/{key_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """Revoke (deactivate) an API key."""
    try:
        success = api_key_service.revoke_api_key(db, key_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )
        
        return {"message": "API key revoked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {str(e)}",
        )


@router.delete("/{key_id}", status_code=status.HTTP_200_OK)
async def delete_api_key(
    key_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """Permanently delete an API key."""
    try:
        success = api_key_service.delete_api_key(db, key_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )
        
        return {"message": "API key deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete API key: {str(e)}",
        )
