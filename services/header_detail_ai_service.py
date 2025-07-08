import json
import logging
from anthropic import Anthropic
from dotenv import load_dotenv
import os
from typing import Dict, List, Any

load_dotenv()

logger = logging.getLogger(__name__)

class HeaderDetailAIService:
    """AI service for extracting header and line item data from PDF text"""
    
    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
    
    def extract_header_detail_data(self, pdf_text: str) -> Dict[str, Any]:
        """
        Extract both header (document-level) and detail (line item) data from PDF text
        
        Args:
            pdf_text: Raw text extracted from PDF
            
        Returns:
            Dictionary with 'header' and 'line_items' sections
        """
        try:
            prompt = self._build_extraction_prompt(pdf_text)
            
            logger.info(f"Sending extraction request to Claude - PDF text length: {len(pdf_text)} chars")
            logger.debug(f"Prompt length: {len(prompt)} chars")
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            logger.info(f"Received response from Claude - Response type: {type(response.content)}")
            if hasattr(response, 'content') and response.content:
                logger.info(f"Response content length: {len(response.content[0].text) if response.content else 0} chars")
            
            # Parse the JSON response
            response_text = response.content[0].text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:-3]
            elif response_text.startswith('```'):
                response_text = response_text[3:-3]
                
            extracted_data = json.loads(response_text)
            
            # Post-process delivery dates - handle inheritance from header to line items
            processed_data = self._process_delivery_dates(extracted_data)
            
            logger.info(f"AI extraction successful - Header fields: {len(processed_data.get('header', {}))}, Line items: {len(processed_data.get('line_items', []))}")
            
            return {
                'success': True,
                'extraction_model': self.model,
                'header_data': processed_data.get('header', {}),
                'line_items': processed_data.get('line_items', []),
                'raw_ai_response': processed_data
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Raw AI response text: '{response_text}'")
            logger.error(f"Response length: {len(response_text)}")
            
            # Try to extract JSON from a more complex response
            try:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    logger.info(f"Attempting to parse extracted JSON: {json_str[:200]}...")
                    extracted_data = json.loads(json_str)
                    processed_data = self._process_delivery_dates(extracted_data)
                    
                    return {
                        'success': True,
                        'extraction_model': self.model,
                        'header_data': processed_data.get('header', {}),
                        'line_items': processed_data.get('line_items', []),
                        'raw_ai_response': processed_data,
                        'parsing_note': 'JSON extracted from complex response'
                    }
            except:
                pass
            
            return {
                'success': False,
                'error': f"JSON parsing error: {str(e)}",
                'extraction_model': self.model,
                'raw_response': response_text[:500] if response_text else "Empty response"
            }
        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'extraction_model': self.model
            }
    
    def _process_delivery_dates(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process delivery dates with proper inheritance logic:
        - If delivery date appears at header level only, copy to each line item
        - If delivery dates appear at line level, keep them there
        - If both exist, keep both (line-specific dates override header date)
        """
        header = extracted_data.get('header', {})
        line_items = extracted_data.get('line_items', [])
        
        header_delivery_date = header.get('delivery_date')
        
        # Check if any line items have line-specific delivery dates
        line_items_with_dates = [item for item in line_items if item.get('line_delivery_date')]
        line_items_without_dates = [item for item in line_items if not item.get('line_delivery_date')]
        
        logger.info(f"Delivery date processing: Header date: {header_delivery_date}, "
                   f"Line items with dates: {len(line_items_with_dates)}, "
                   f"Line items without dates: {len(line_items_without_dates)}")
        
        # If header has delivery date and some/all line items don't have dates, inherit from header
        if header_delivery_date and line_items_without_dates:
            logger.info(f"Inheriting header delivery date '{header_delivery_date}' to {len(line_items_without_dates)} line items")
            
            for item in line_items_without_dates:
                item['line_delivery_date'] = header_delivery_date
                # Add metadata to track inheritance
                item['delivery_date_inherited'] = True
        
        # Mark line items that have their own dates
        for item in line_items_with_dates:
            item['delivery_date_inherited'] = False
        
        return {
            'header': header,
            'line_items': line_items,
            'extraction_confidence': extracted_data.get('extraction_confidence', {}),
            'delivery_date_processing': {
                'header_delivery_date': header_delivery_date,
                'line_items_with_specific_dates': len(line_items_with_dates),
                'line_items_inherited_date': len(line_items_without_dates) if header_delivery_date else 0
            }
        }
    
    def _build_extraction_prompt(self, pdf_text: str) -> str:
        """Build the extraction prompt for header/detail structure"""
        
        return f"""
You are a business document AI that extracts structured data from purchase orders, invoices, and similar documents.

Extract data into TWO sections:
1. HEADER (document-level information that appears once)
2. LINE_ITEMS (array of individual items/products)

**INPUT PDF TEXT:**
{pdf_text[:8000]}  

**EXTRACTION RULES:**

**HEADER SECTION** (document-level fields):
- po_number: Purchase order number (PO-xxxx, Order #, etc.)
- vendor_name: Company supplying goods/services
- customer_name: Company receiving goods/services  
- invoice_number: Invoice number if present
- invoice_date: Date document was created
- delivery_date: Overall delivery date for order (ONLY if it applies to the entire document)
- payment_terms: Payment terms (Net 30, etc.)
- currency: Currency code (USD, EUR, etc.)
- tax_rate: Tax percentage as decimal (0.0825 for 8.25%)
- tax_amount: Total tax amount
- subtotal: Subtotal before tax
- total_amount: Grand total amount
- contact_email: Contact email address
- contact_phone: Contact phone number
- shipping_address: Full shipping address
- billing_address: Full billing address

**LINE_ITEMS SECTION** (array of items):
Each line item should have:
- line_number: Line number on document (1, 2, 3...)
- item_code: Product/part number
- description: Item description
- quantity: Quantity ordered
- unit_of_measure: Units (each, lbs, ft, etc.)
- unit_price: Price per unit
- line_total: Total for this line (qty × unit_price)
- discount_percent: Discount percentage if any
- discount_amount: Discount amount if any
- line_delivery_date: Line-specific delivery date (ONLY if different from header or specifically mentioned for this line)
- drawing_number: Engineering drawing number if applicable
- revision: Drawing revision if applicable
- material: Material specification
- finish: Surface finish specification

**CRITICAL DELIVERY DATE LOGIC:**
- If delivery date appears at document level (e.g., "Delivery Date: March 15") → put in header.delivery_date, leave line_delivery_date as null
- If delivery dates appear for specific line items (e.g., "Item 1: deliver Jan 15, Item 2: deliver Feb 20") → put in each line_delivery_date
- If both exist, capture both appropriately
- DO NOT duplicate the same date in both header and line items unless truly line-specific

**OUTPUT FORMAT:**
Return ONLY valid JSON in this exact structure:

```json
{{
    "header": {{
        "po_number": "string or null",
        "vendor_name": "string or null",
        "customer_name": "string or null",
        "invoice_number": "string or null", 
        "invoice_date": "YYYY-MM-DD or null",
        "delivery_date": "YYYY-MM-DD or null",
        "payment_terms": "string or null",
        "currency": "string or null",
        "tax_rate": number or null,
        "tax_amount": number or null,
        "subtotal": number or null,
        "total_amount": number or null,
        "contact_email": "string or null",
        "contact_phone": "string or null",
        "shipping_address": "string or null",
        "billing_address": "string or null"
    }},
    "line_items": [
        {{
            "line_number": number,
            "item_code": "string or null",
            "description": "string or null",
            "quantity": number or null,
            "unit_of_measure": "string or null",
            "unit_price": number or null,
            "line_total": number or null,
            "discount_percent": number or null,
            "discount_amount": number or null,
            "line_delivery_date": "YYYY-MM-DD or null",
            "drawing_number": "string or null",
            "revision": "string or null",
            "material": "string or null",
            "finish": "string or null"
        }}
    ],
    "extraction_confidence": {{
        "header_confidence": 0.95,
        "line_items_confidence": 0.90,
        "overall_confidence": 0.92
    }}
}}
```

**IMPORTANT:**
- Return null for missing values, NOT empty strings
- Extract ALL line items, not just the first one
- For numbers, return actual numeric values (not strings)
- Dates must be in YYYY-MM-DD format
- Be very accurate with quantities and prices
- If multiple line items exist, extract each one separately
- Look for tables, itemized lists, or repeated patterns for line items
- Pay careful attention to delivery date context (document-wide vs line-specific)
"""

    def test_extraction(self):
        """Test the extraction with sample business document text"""
        sample_text = """
        PURCHASE ORDER
        
        PO Number: PO-2024-7890
        Date: February 20, 2024
        
        Vendor: Advanced Manufacturing Inc.
        123 Industrial Blvd
        Detroit, MI 48201
        Phone: (313) 555-0123
        Email: orders@advancedmfg.com
        
        Ship To: Tech Solutions Corp
        456 Business Park Dr
        Austin, TX 78701
        
        Payment Terms: Net 30
        Delivery Date: March 15, 2024
        
        Line Items:
        1. Widget Assembly A-100    Qty: 50    Unit Price: $25.00    Total: $1,250.00
        2. Bracket Set B-200       Qty: 25    Unit Price: $15.50    Total: $387.50
        3. Fastener Kit C-300      Qty: 100   Unit Price: $2.75     Total: $275.00
        
        Subtotal: $1,912.50
        Tax (8.25%): $157.78
        Total: $2,070.28
        """
        
        return self.extract_header_detail_data(sample_text) 