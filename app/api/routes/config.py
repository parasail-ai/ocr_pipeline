"""Configuration management API endpoints."""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from openai import OpenAI
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["Configuration"])

# In-memory storage for AI schema generator config
# In production, this should be stored in a database or secure key vault
_ai_config = {
    "api_endpoint": "https://api.parasail.io/v1",
    "model_name": "parasail-glm-46",
    "api_key": None  # Will be loaded from settings initially
}


class AISchemaGeneratorConfig(BaseModel):
    api_endpoint: str
    model_name: str
    api_key: str


class AISchemaGeneratorConfigResponse(BaseModel):
    api_endpoint: str
    model_name: str
    has_api_key: bool
    api_key_preview: str | None = None


class AISchemaGeneratorTestResponse(BaseModel):
    success: bool
    model: str
    message: str


@router.get("/ai-schema-generator", response_model=AISchemaGeneratorConfigResponse)
async def get_ai_schema_generator_config() -> AISchemaGeneratorConfigResponse:
    """Get the current AI schema generator configuration."""
    settings = get_settings()
    
    # Initialize from settings if not set
    if _ai_config["api_key"] is None:
        api_key = getattr(settings, 'parasail_api_key', None)
        if api_key:
            _ai_config["api_key"] = api_key
    
    has_key = _ai_config["api_key"] is not None and len(_ai_config["api_key"]) > 0
    
    return AISchemaGeneratorConfigResponse(
        api_endpoint=_ai_config["api_endpoint"],
        model_name=_ai_config["model_name"],
        has_api_key=has_key,
        api_key_preview=_mask_api_key(_ai_config["api_key"]) if has_key else None
    )


@router.post("/ai-schema-generator", status_code=status.HTTP_200_OK)
async def update_ai_schema_generator_config(config: AISchemaGeneratorConfig) -> dict[str, str]:
    """Update the AI schema generator configuration."""
    try:
        # Validate the configuration by testing it
        test_client = OpenAI(
            base_url=config.api_endpoint,
            api_key=config.api_key
        )
        
        # Quick validation - just check if we can create a client
        # Full validation happens in the test endpoint
        
        # Update the config
        _ai_config["api_endpoint"] = config.api_endpoint
        _ai_config["model_name"] = config.model_name
        _ai_config["api_key"] = config.api_key
        
        logger.info(f"AI schema generator config updated: endpoint={config.api_endpoint}, model={config.model_name}")
        
        return {"message": "Configuration updated successfully"}
        
    except Exception as e:
        logger.error(f"Failed to update AI schema generator config: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid configuration: {str(e)}"
        )


@router.post("/ai-schema-generator/test", response_model=AISchemaGeneratorTestResponse)
async def test_ai_schema_generator_config() -> AISchemaGeneratorTestResponse:
    """Test the current AI schema generator configuration."""
    if not _ai_config["api_key"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key not configured"
        )
    
    try:
        client = OpenAI(
            base_url=_ai_config["api_endpoint"],
            api_key=_ai_config["api_key"]
        )
        
        # Test with a simple completion
        response = client.chat.completions.create(
            model=_ai_config["model_name"],
            messages=[
                {
                    "role": "user",
                    "content": "Hello! Please respond with 'OK' if you receive this message."
                }
            ],
            max_tokens=10,
            temperature=0.0
        )
        
        result = response.choices[0].message.content
        
        logger.info(f"AI schema generator config test successful: {result}")
        
        return AISchemaGeneratorTestResponse(
            success=True,
            model=_ai_config["model_name"],
            message=f"Connection successful! Model responded: {result}"
        )
        
    except Exception as e:
        logger.error(f"AI schema generator config test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration test failed: {str(e)}"
        )


def get_ai_config() -> dict[str, Any]:
    """Get the current AI configuration for use by other services."""
    settings = get_settings()
    
    # Initialize from settings if not set
    if _ai_config["api_key"] is None:
        api_key = getattr(settings, 'parasail_api_key', None)
        if api_key:
            _ai_config["api_key"] = api_key
    
    return _ai_config.copy()


def _mask_api_key(api_key: str | None) -> str:
    """Mask an API key for display."""
    if not api_key or len(api_key) < 8:
        return "****"
    return api_key[:7] + "****" + api_key[-4:]
