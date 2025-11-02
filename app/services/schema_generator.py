"""
Auto-generate schemas from OCR output using AI analysis.
"""
import json
import logging
from typing import Any, Optional

from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SchemaGenerator:
    """Generate schemas automatically from OCR text using AI analysis."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        key = api_key or settings.parasail_api_key
        if not key:
            raise RuntimeError("PARASAIL_API_KEY is not configured for schema generation.")
        
        self.client = OpenAI(api_key=key, base_url=str(settings.parasail_base_url))
        self.model = "gpt-4o-mini"  # Use efficient model for schema generation

    def generate_schema_from_text(
        self,
        ocr_text: str,
        document_type: Optional[str] = None,
        existing_schemas: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Analyze OCR text and generate a schema with extracted values.
        
        Args:
            ocr_text: The extracted text from OCR
            document_type: Optional detected document type
            existing_schemas: Optional list of existing schemas for reference
            
        Returns:
            Dict with schema definition and extracted values:
            {
                "schema_name": str,
                "category": str,
                "description": str,
                "fields": [{"key": str, "value_type": str, "description": str}],
                "extracted_values": {key: value}
            }
        """
        logger.info("Generating schema from OCR text (length: %d)", len(ocr_text))
        
        # Build prompt for schema generation
        prompt = self._build_schema_generation_prompt(
            ocr_text, document_type, existing_schemas
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing documents and extracting structured data. "
                                   "Generate JSON schemas and extract key-value pairs from document text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            logger.info("Successfully generated schema: %s", result.get("schema_name"))
            return result
            
        except Exception as exc:
            logger.exception("Failed to generate schema: %s", exc)
            # Return a basic fallback schema
            return self._create_fallback_schema(ocr_text)

    def _build_schema_generation_prompt(
        self,
        ocr_text: str,
        document_type: Optional[str],
        existing_schemas: Optional[list[dict[str, Any]]],
    ) -> str:
        """Build the prompt for schema generation."""
        
        # Truncate text if too long
        max_text_length = 4000
        truncated_text = ocr_text[:max_text_length]
        if len(ocr_text) > max_text_length:
            truncated_text += "\n...(truncated)"
        
        prompt = f"""Analyze this document text and generate a JSON schema with extracted values.

Document Text:
{truncated_text}

"""
        
        if document_type:
            prompt += f"Detected Document Type: {document_type}\n\n"
        
        if existing_schemas:
            schema_names = [s.get("name", "Unknown") for s in existing_schemas[:5]]
            prompt += f"Existing Schema References: {', '.join(schema_names)}\n\n"
        
        prompt += """Generate a JSON response with this structure:
{
  "schema_name": "descriptive name for this document type",
  "category": "document category (invoice, contract, receipt, etc.)",
  "description": "brief description of what this document represents",
  "fields": [
    {
      "key": "field_name_snake_case",
      "value_type": "string|number|date|boolean",
      "description": "what this field represents",
      "required": true|false
    }
  ],
  "extracted_values": {
    "field_name_snake_case": "extracted value from the document"
  }
}

Rules:
1. Extract ALL key-value pairs you can identify in the document
2. Use clear, descriptive field names in snake_case
3. Infer appropriate value_type for each field
4. Mark fields as required if they seem essential to the document type
5. Extract actual values from the text into extracted_values
6. Include common fields like: date, total, vendor, customer, amount, etc.
7. If this looks similar to an existing schema, reuse that schema name
8. For invoices: extract invoice_number, date, total, tax, vendor details
9. For contracts: extract parties, dates, terms, amounts
10. For receipts: extract merchant, date, items, total

Return ONLY valid JSON, no additional text."""

        return prompt

    def _create_fallback_schema(self, ocr_text: str) -> dict[str, Any]:
        """Create a basic fallback schema when AI generation fails."""
        
        # Try to extract some basic key-value pairs with simple heuristics
        lines = ocr_text.split('\n')
        extracted_values = {}
        
        # Look for common patterns
        for line in lines[:50]:  # Check first 50 lines
            line = line.strip()
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower().replace(' ', '_').replace('-', '_')
                    value = parts[1].strip()
                    if key and value and len(key) < 50:
                        extracted_values[key] = value
        
        return {
            "schema_name": "Generic Document",
            "category": "unknown",
            "description": "Auto-generated fallback schema",
            "fields": [
                {
                    "key": key,
                    "value_type": "string",
                    "description": f"Extracted field: {key}",
                    "required": False
                }
                for key in extracted_values.keys()
            ],
            "extracted_values": extracted_values
        }

    def extract_key_value_pairs(self, ocr_text: str) -> dict[str, Any]:
        """
        Quick extraction of key-value pairs without full schema generation.
        Useful for adding to document extractions.
        """
        logger.info("Extracting key-value pairs from text (length: %d)", len(ocr_text))
        
        prompt = f"""Extract key-value pairs from this document text. Return as JSON.

Document Text:
{ocr_text[:3000]}

Return a JSON object with key-value pairs. Use descriptive snake_case keys.
Example: {{"invoice_number": "INV-12345", "date": "2024-01-15", "total": "1250.00"}}

Return ONLY valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Extract key-value pairs from documents and return as JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as exc:
            logger.exception("Failed to extract key-value pairs: %s", exc)
            return {}

    def suggest_similar_schema(
        self,
        ocr_text: str,
        existing_schemas: list[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """
        Analyze if the document matches any existing schema.
        Returns the best matching schema or None.
        """
        if not existing_schemas:
            return None
        
        logger.info("Checking similarity with %d existing schemas", len(existing_schemas))
        
        schema_summaries = []
        for schema in existing_schemas[:10]:  # Limit to 10 for prompt size
            schema_summaries.append({
                "id": schema.get("id"),
                "name": schema.get("name"),
                "category": schema.get("category"),
                "fields": [f.get("key") for f in schema.get("fields", [])]
            })
        
        prompt = f"""Analyze if this document matches any existing schema.

Document Text (first 1000 chars):
{ocr_text[:1000]}

Existing Schemas:
{json.dumps(schema_summaries, indent=2)}

Return JSON:
{{
  "match_found": true|false,
  "matched_schema_id": "uuid or null",
  "confidence": 0.0-1.0,
  "reason": "why this schema matches or doesn't match"
}}

Return ONLY valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Determine if a document matches existing schemas."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            if result.get("match_found") and result.get("confidence", 0) > 0.7:
                matched_id = result.get("matched_schema_id")
                for schema in existing_schemas:
                    if str(schema.get("id")) == str(matched_id):
                        return schema
            
            return None
            
        except Exception as exc:
            logger.exception("Failed to suggest similar schema: %s", exc)
            return None
