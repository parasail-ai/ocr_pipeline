import base64
import logging
from typing import Any, Optional

from openai import OpenAI

from app.core.config import get_settings


class ParasailOCRClient:
    """Thin wrapper around the Parasail-hosted OpenAI-compatible API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        settings = get_settings()
        key = api_key or settings.parasail_api_key
        if not key:
            raise RuntimeError("PARASAIL_API_KEY is not configured.")

        self.default_model = settings.parasail_default_model
        self.client = OpenAI(api_key=key, base_url=base_url or str(settings.parasail_base_url))

        self._logger = logging.getLogger(__name__)

    def extract_text(
        self,
        *,
        model: Optional[str] = None,
        input_text: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Placeholder method to demonstrate Parasail OCR interaction."""
        response = self.client.embeddings.create(model=model or self.default_model, input=input_text, **kwargs)
        return response.to_dict()

    def extract_document(
        self,
        *,
        content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """Attempt to submit a document for OCR; falls back to placeholder payload on failure."""

        model_name = model or self.default_model
        encoded = base64.b64encode(content).decode("utf-8")
        prompt = "Extract raw text from the attached base64 document and return JSON with a `text` key."

        try:
            response = self.client.responses.create(
                model=model_name,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_file",
                                "data": encoded,
                                "name": filename,
                                "media_type": mime_type or "application/octet-stream",
                            },
                        ],
                    }
                ],
            )
            return response.to_dict()
        except Exception as exc:  # pragma: no cover - dependent on Parasail endpoint availability
            self._logger.warning("Parasail OCR request failed: %s", exc)
            return {
                "model": model_name,
                "error": str(exc),
                "message": "Parasail OCR request failed or endpoint not yet available.",
            }
