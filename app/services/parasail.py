import base64
import logging
import time
from typing import Any, Optional, List

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
        """Simple text extraction using chat completions."""
        model_name = model or self.default_model
        start_time = time.time()
        
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": input_text}],
                **kwargs
            )
            end_time = time.time()
            
            result = response.to_dict() if hasattr(response, 'to_dict') else response.model_dump()
            result['_timing'] = {
                'start_time': start_time,
                'end_time': end_time,
                'duration_ms': int((end_time - start_time) * 1000)
            }
            return result
        except Exception as exc:
            self._logger.exception("Parasail text extraction failed", exc_info=exc)
            raise

    def extract_document(
        self,
        *,
        content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Submit a document for OCR using Parasail API.
        Uses chat.completions endpoint with base64 encoded document.
        """
        model_name = model or self.default_model
        encoded = base64.b64encode(content).decode("utf-8")
        
        # Construct the prompt for OCR extraction
        prompt = """Extract all text content from this document. Return the extracted text in a structured format.
        
Please extract:
1. All visible text from the document
2. Any tables or structured data
3. Key-value pairs if present

Return the results in JSON format with these keys:
- text: The full extracted text
- tables: Array of any tables found
- key_value_pairs: Object of any key-value data found"""

        start_time = time.time()
        
        try:
            # Try using chat.completions with image content
            self._logger.info("Calling Parasail API with model: %s for file: %s", model_name, filename)
            
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type or 'application/pdf'};base64,{encoded}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
            )
            
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            
            self._logger.info("Parasail API call completed in %d ms", duration_ms)
            
            # Convert response to dict
            result = response.to_dict() if hasattr(response, 'to_dict') else response.model_dump()
            
            # Add timing metadata
            result['_timing'] = {
                'start_time': start_time,
                'end_time': end_time,
                'duration_ms': duration_ms
            }
            
            return result
            
        except Exception as exc:
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            
            self._logger.exception("Parasail OCR request failed after %d ms: %s", duration_ms, exc)
            
            # Return error response with timing
            return {
                "model": model_name,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "message": "Parasail OCR request failed. Check API key and model availability.",
                "_timing": {
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_ms": duration_ms
                }
            }

    def extract_multi_page(
        self,
        *,
        page_images: List[bytes],
        filename: str,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Extract text from multiple page images (from a PDF).
        Processes each page individually and combines results.
        
        Args:
            page_images: List of image bytes (one per page)
            filename: Original filename for logging
            model: OCR model to use
            
        Returns:
            Combined results from all pages
        """
        model_name = model or self.default_model
        all_pages_text = []
        all_pages_results = []
        total_start_time = time.time()
        
        self._logger.info(f"Processing {len(page_images)} pages from {filename} with model {model_name}")
        
        for page_num, page_bytes in enumerate(page_images, start=1):
            try:
                # Encode page image
                encoded = base64.b64encode(page_bytes).decode("utf-8")
                
                # Construct prompt for this page
                prompt = f"""Extract all text content from page {page_num} of this document. Return the extracted text in a structured format.

Please extract:
1. All visible text from the page
2. Any tables or structured data
3. Key-value pairs if present

Return the results in JSON format with these keys:
- text: The full extracted text from this page
- tables: Array of any tables found on this page
- key_value_pairs: Object of any key-value data found on this page"""

                page_start_time = time.time()
                
                # Call API for this page
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{encoded}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4096,
                )
                
                page_end_time = time.time()
                page_duration_ms = int((page_end_time - page_start_time) * 1000)
                
                self._logger.info(f"Page {page_num}/{len(page_images)} completed in {page_duration_ms} ms")
                
                # Convert response to dict
                result = response.to_dict() if hasattr(response, 'to_dict') else response.model_dump()
                
                # Extract text from response
                if result.get('choices') and len(result['choices']) > 0:
                    page_text = result['choices'][0].get('message', {}).get('content', '')
                    all_pages_text.append(f"\n\n=== Page {page_num} ===\n\n{page_text}")
                
                # Add page metadata
                result['_page_number'] = page_num
                result['_timing'] = {
                    'start_time': page_start_time,
                    'end_time': page_end_time,
                    'duration_ms': page_duration_ms
                }
                
                all_pages_results.append(result)
                
            except Exception as exc:
                self._logger.exception(f"Failed to process page {page_num}", exc_info=exc)
                
                # Add error result for this page
                all_pages_results.append({
                    "_page_number": page_num,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                })
                all_pages_text.append(f"\n\n=== Page {page_num} ===\n\n[ERROR: {str(exc)}]")
        
        total_end_time = time.time()
        total_duration_ms = int((total_end_time - total_start_time) * 1000)
        
        self._logger.info(f"Processed all {len(page_images)} pages in {total_duration_ms} ms")
        
        # Combine all results
        return {
            "model": model_name,
            "page_count": len(page_images),
            "pages": all_pages_results,
            "combined_text": "\n".join(all_pages_text),
            "_timing": {
                "start_time": total_start_time,
                "end_time": total_end_time,
                "duration_ms": total_duration_ms
            }
        }
