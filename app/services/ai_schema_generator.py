"""AI-powered schema generation using Parasail GLM-46 model."""
import json
import logging
from typing import Any

from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AISchemaGenerator:
    """Generate schemas using AI analysis of OCR text."""
    
    def __init__(self):
        """Initialize the AI schema generator."""
        # Get API key from settings
        api_key = getattr(settings, 'parasail_api_key', None)
        if not api_key:
            raise RuntimeError("PARASAIL_API_KEY not configured in settings")
        
        self.client = OpenAI(
            base_url="https://api.parasail.io/v1",
            api_key=api_key
        )
        self.model = "parasail-glm-46"
    
    def generate_schema_from_ocr(
        self,
        ocr_text: str,
        document_type: str | None = None,
        schema_name: str | None = None
    ) -> dict[str, Any]:
        """
        Generate a schema by analyzing OCR text with AI.
        
        Args:
            ocr_text: The OCR text to analyze
            document_type: Optional document type hint
            schema_name: Optional name for the schema
            
        Returns:
            Dictionary containing:
            - schema_name: Name of the generated schema
            - category: Document category
            - description: Description of the schema
            - fields: List of field definitions with key, query, and description
            - extracted_values: Dictionary of key-value pairs extracted from the text
        """
        prompt = self._build_schema_generation_prompt(ocr_text, document_type, schema_name)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing documents and creating structured data extraction schemas. You identify important fields in documents and create queries to extract their values."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent output
            )
            
            content = response.choices[0].message.content
            logger.info(f"AI schema generation response: {content[:200]}...")
            
            # Strip any thinking tags or markdown formatting
            content = content.strip()
            
            # Remove <think> tags if present
            if '<think>' in content and '</think>' in content:
                # Extract content between think tags and after
                parts = content.split('</think>')
                if len(parts) > 1:
                    content = parts[1].strip()
            
            # Remove markdown code blocks if present
            if content.startswith('```'):
                lines = content.split('\n')
                # Remove first line (```json or ```)
                if lines[0].strip().startswith('```'):
                    lines = lines[1:]
                # Remove last line if it's ```
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()
            
            logger.info(f"Cleaned content for JSON parsing: {content[:200]}...")
            
            # Parse the JSON response
            result = json.loads(content)
            
            # Validate the response has required fields
            if not all(key in result for key in ['schema_name', 'fields', 'extracted_values']):
                raise ValueError("AI response missing required fields")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Response content: {content}")
            raise RuntimeError(f"AI returned invalid JSON: {str(e)}")
        except Exception as e:
            logger.error(f"AI schema generation failed: {e}")
            raise RuntimeError(f"Failed to generate schema: {str(e)}")
    
    def extract_field_value(
        self,
        ocr_text: str,
        field_key: str,
        field_query: str,
        field_description: str | None = None
    ) -> str:
        """
        Extract a single field value from OCR text using the field's query.
        
        Args:
            ocr_text: The OCR text to extract from
            field_key: The field key/name
            field_query: The query to extract this field
            field_description: Optional field description
            
        Returns:
            The extracted value as a string
        """
        prompt = f"""Given the following document text, extract the value for: {field_key}

Query/Instruction: {field_query}

{f"Description: {field_description}" if field_description else ""}

Document Text:
{ocr_text}

Return ONLY the extracted value, nothing else. If the value cannot be found, return "Not found"."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise data extraction assistant. Extract the requested information from the document text exactly as it appears."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Very low temperature for precise extraction
            )
            
            value = response.choices[0].message.content.strip()
            logger.info(f"Extracted {field_key}: {value}")
            return value
            
        except Exception as e:
            logger.error(f"Field extraction failed for {field_key}: {e}")
            return "Error extracting value"
    
    def _build_schema_generation_prompt(
        self,
        ocr_text: str,
        document_type: str | None = None,
        schema_name: str | None = None
    ) -> str:
        """Build the prompt for schema generation."""
        type_hint = f"\nDocument Type: {document_type}" if document_type else ""
        name_hint = f"\nSchema Name: {schema_name}" if schema_name else ""
        
        return f"""Analyze the following OCR text from a document and create a data extraction schema.{type_hint}{name_hint}

Your task:
1. Identify all important fields/data points in this document
2. For each field, create a key (field name) and a query (instruction to extract its value)
3. Extract the actual values for each field from the text
4. Return a JSON object with the schema definition and extracted values

OCR Text:
{ocr_text}

Return a JSON object with this EXACT structure (no additional text):
{{
  "schema_name": "Descriptive name for this document type",
  "category": "Document category (e.g., invoice, receipt, contract, form)",
  "description": "Brief description of what this document contains",
  "fields": [
    {{
      "key": "field_name",
      "query": "Specific instruction to extract this field (e.g., 'Extract the invoice number', 'Find the total amount')",
      "description": "What this field represents",
      "value_type": "string",
      "required": true
    }}
  ],
  "extracted_values": {{
    "field_name": "actual extracted value from the text"
  }}
}}

Important:
- Make the queries specific and actionable (e.g., "Extract the invoice number from the top right", "Find the total amount paid")
- Include all important fields (names, dates, amounts, IDs, addresses, etc.)
- The extracted_values should contain the actual values found in the OCR text
- Return ONLY valid JSON, no markdown formatting or additional text"""


def create_ai_schema_generator() -> AISchemaGenerator:
    """Factory function to create an AI schema generator."""
    try:
        return AISchemaGenerator()
    except RuntimeError as e:
        logger.warning(f"AI schema generator not available: {e}")
        raise
