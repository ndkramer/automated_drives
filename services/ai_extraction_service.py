"""
AI Extraction Service
Uses Anthropic's Claude to extract structured data from PDF text content.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AIExtractionService:
    """Service for AI-powered data extraction from PDF text using Claude"""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-3-5-sonnet-20241022"  # Current Claude 3.5 Sonnet model
        
    def extract_structured_data(self, pdf_text: str, custom_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract structured data from PDF text using Claude
        
        Args:
            pdf_text: Raw text content from PDF
            custom_prompt: Optional custom prompt for specific extraction needs
            
        Returns:
            Dictionary containing extracted structured data
        """
        try:
            # Default prompt for business document extraction
            prompt = custom_prompt or self._get_default_prompt(pdf_text)
            
            logger.info(f"Sending text to Claude for extraction (length: {len(pdf_text)} chars)")
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.1,  # Low temperature for consistent extraction
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            )
            
            # Extract the response text
            response_text = response.content[0].text
            logger.info("Received response from Claude")
            
            # Parse the JSON response
            extracted_data = self._parse_claude_response(response_text)
            
            return {
                "ai_extracted_data": extracted_data,
                "extraction_model": self.model,
                "success": True,
                "raw_response": response_text
            }
            
        except Exception as e:
            logger.error(f"Error in AI extraction: {e}")
            return {
                "ai_extracted_data": {},
                "extraction_model": self.model,
                "success": False,
                "error": str(e)
            }
    
    def _get_default_prompt(self, pdf_text: str) -> str:
        """Generate the default extraction prompt"""
        return f"""You are an expert at extracting structured data from business documents like invoices, purchase orders, delivery receipts, and contracts.

Please analyze the following document text and extract these key fields if present:

**Required Fields:**
- PO Number (Purchase Order Number, Order No, etc.)
- QTY (Quantity, Qty, Amount, Count)
- Price (Total Price, Amount, Cost, Value)
- Delivery Date (Due Date, Ship Date, Expected Date)

**Additional Fields (extract if found):**
- Invoice Number
- Vendor/Supplier Name
- Customer Name
- Description/Item Description
- Unit Price
- Line Items (if multiple products/services)
- Total Amount
- Tax Amount
- Payment Terms
- Contact Information

**Instructions:**
1. Look for these fields using various label formats (e.g., "P.O. No.", "Purchase Order", "Qty:", "Quantity:", etc.)
2. If a field is not found, use null
3. For dates, convert to YYYY-MM-DD format if possible
4. For prices, include currency symbol if present
5. Extract line items as an array if there are multiple products/services

Return ONLY a valid JSON object with the extracted data. Use this exact format:

{{
  "po_number": "value or null",
  "qty": "value or null", 
  "price": "value or null",
  "delivery_date": "value or null",
  "invoice_number": "value or null",
  "vendor_name": "value or null",
  "customer_name": "value or null",
  "description": "value or null",
  "unit_price": "value or null",
  "total_amount": "value or null",
  "tax_amount": "value or null",
  "payment_terms": "value or null",
  "line_items": [],
  "contact_info": {{}}
}}

Document text to analyze:

{pdf_text}

JSON Response:"""

    def _parse_claude_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's response and extract JSON"""
        try:
            # Look for JSON in the response
            import re
            
            # Try to find JSON block
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
            else:
                # If no JSON found, try to parse the entire response
                return json.loads(response_text.strip())
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                "error": "Failed to parse response",
                "raw_response": response_text
            }
    
    def extract_with_feedback(self, pdf_text: str, expected_fields: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract data with feedback about expected values for training/validation
        
        Args:
            pdf_text: Raw text content from PDF
            expected_fields: Dictionary of expected field values for validation
            
        Returns:
            Dictionary containing extracted data and validation results
        """
        extracted = self.extract_structured_data(pdf_text)
        
        if extracted["success"]:
            # Compare with expected values
            ai_data = extracted["ai_extracted_data"]
            validation_results = {}
            
            for field, expected_value in expected_fields.items():
                extracted_value = ai_data.get(field)
                validation_results[field] = {
                    "expected": expected_value,
                    "extracted": extracted_value,
                    "match": str(expected_value).lower().strip() == str(extracted_value).lower().strip() if extracted_value else False
                }
            
            extracted["validation_results"] = validation_results
            
        return extracted 