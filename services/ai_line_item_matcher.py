#!/usr/bin/env python3
"""
AI-Powered Line Item Matcher
Uses Claude AI to intelligently match PDF line items with ETOSandbox line items
based on content analysis rather than position-based matching.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AILineItemMatcher:
    """AI service for intelligent matching of PDF line items to ETOSandbox line items"""
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = "claude-3-5-sonnet-20241022"
    
    def match_line_items(self, pdf_line_items: List[Dict[str, Any]], eto_line_items: List[Dict[str, Any]], po_number: str) -> Dict[str, Any]:
        """
        Use AI to intelligently match PDF line items with ETO line items
        
        Args:
            pdf_line_items: List of line items extracted from PDF
            eto_line_items: List of line items from ETOSandbox database
            po_number: Purchase Order number for context
            
        Returns:
            Dictionary containing matched pairs and unmatched items
        """
        try:
            if not pdf_line_items or not eto_line_items:
                return {
                    'success': True,
                    'matches': [],
                    'unmatched_pdf': pdf_line_items.copy(),
                    'unmatched_eto': eto_line_items.copy(),
                    'match_method': 'no_items_to_match'
                }
            
            logger.info(f"AI matching {len(pdf_line_items)} PDF items with {len(eto_line_items)} ETO items for PO {po_number}")
            
            # Prepare data for AI analysis
            matching_prompt = self._build_matching_prompt(pdf_line_items, eto_line_items, po_number)
            
            # Get AI analysis
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.1,  # Low temperature for consistent matching
                messages=[{
                    "role": "user", 
                    "content": matching_prompt
                }]
            )
            
            response_text = response.content[0].text
            logger.info(f"AI matching response received ({len(response_text)} chars)")
            
            # Parse AI response
            matches_result = self._parse_matching_response(response_text, pdf_line_items, eto_line_items)
            
            if matches_result['success']:
                logger.info(f"AI matching successful: {len(matches_result['matches'])} matches found")
                return matches_result
            else:
                logger.warning(f"AI matching failed, falling back to position-based: {matches_result.get('error')}")
                return self._fallback_position_matching(pdf_line_items, eto_line_items)
                
        except Exception as e:
            logger.error(f"Error in AI line item matching: {e}")
            return self._fallback_position_matching(pdf_line_items, eto_line_items)
    
    def _build_matching_prompt(self, pdf_items: List[Dict[str, Any]], eto_items: List[Dict[str, Any]], po_number: str) -> str:
        """Build the AI prompt for line item matching"""
        
        prompt = f"""You are a purchase order line item matching expert. Your task is to match line items from a PDF document with corresponding line items from an ETOSandbox database for PO {po_number}.

IMPORTANT: Items should match based on content similarity, NOT position. The same physical item may appear in different positions in the PDF vs database.

## PDF LINE ITEMS:
"""
        
        for i, item in enumerate(pdf_items):
            unit_price = item.get('unit_price') or 0
            line_total = item.get('line_total') or 0
            prompt += f"""
PDF Item {i+1}:
  - Item Code: {item.get('item_code', 'N/A')}
  - Description: {item.get('description', 'N/A')}
  - Quantity: {item.get('quantity', 'N/A')}
  - Unit Price: ${unit_price:.2f}
  - Line Total: ${line_total:.2f}
  - Unit of Measure: {item.get('unit_of_measure', 'N/A')}
"""

        prompt += f"""
## ETO LINE ITEMS:
"""
        
        for i, item in enumerate(eto_items):
            unit_price = item.get('unit_price') or 0
            line_total = item.get('line_total') or 0
            prompt += f"""
ETO Item {i+1}:
  - Detail ID: {item.get('detail_id')}
  - Item ID: {item.get('item_id', 'N/A')}
  - Description: {item.get('description', 'N/A')}
  - Supplier Item: {item.get('supplier_item', 'N/A')}
  - Quantity: {item.get('quantity', 'N/A')}
  - Unit Price: ${unit_price:.2f}
  - Line Total: ${line_total:.2f}
"""

        prompt += """
## MATCHING RULES:

1. **Primary Matching Criteria** (in order of importance):
   - Item codes/part numbers (exact or similar)
   - Product descriptions (semantic similarity)
   - Quantities (exact or close)
   - Unit prices (exact or close)
   - Line totals (calculated correctly)

2. **Matching Logic**:
   - Look for exact item code matches first
   - Then look for similar descriptions (same product, different wording)
   - Consider quantity and price as confirmation
   - Account for minor OCR errors in PDF extraction
   - One PDF item should match one ETO item (1:1 mapping)

3. **Quality Thresholds**:
   - PERFECT: Item codes match exactly AND quantities/prices match
   - GOOD: Descriptions clearly describe same item AND quantities/prices match
   - FAIR: Descriptions similar AND either quantity OR price matches
   - POOR: Only partial similarity in description
   - NO_MATCH: No reasonable similarity found

## OUTPUT FORMAT:

Return a JSON object with this exact structure:

```json
{
  "matches": [
    {
      "pdf_index": 0,
      "eto_index": 1,
      "confidence": "PERFECT|GOOD|FAIR|POOR",
      "match_reasons": ["item_code_exact", "quantity_match", "price_match"],
      "notes": "Brief explanation of why these items match"
    }
  ],
  "unmatched_pdf_indices": [2],
  "unmatched_eto_indices": [0, 2],
  "analysis_summary": "Brief summary of matching results"
}
```

**CRITICAL**: 
- Use 0-based indices (PDF Item 1 = index 0, ETO Item 1 = index 0)
- Each PDF item can match AT MOST one ETO item
- Each ETO item can match AT MOST one PDF item
- Only include matches with confidence FAIR or better
- List unmatched items by their indices

Analyze the items and provide the matching results:"""
        
        return prompt
    
    def _parse_matching_response(self, response_text: str, pdf_items: List[Dict[str, Any]], eto_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse the AI matching response and create match objects"""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                return {'success': False, 'error': 'No JSON found in AI response'}
            
            ai_result = json.loads(json_match.group(0))
            
            # Validate the response structure
            if not isinstance(ai_result.get('matches'), list):
                return {'success': False, 'error': 'Invalid matches format in AI response'}
            
            # Build match results
            matches = []
            matched_pdf_indices = set()
            matched_eto_indices = set()
            
            for match in ai_result.get('matches', []):
                pdf_idx = match.get('pdf_index')
                eto_idx = match.get('eto_index')
                confidence = match.get('confidence', 'FAIR')
                
                # Validate indices
                if (pdf_idx is None or eto_idx is None or 
                    pdf_idx < 0 or pdf_idx >= len(pdf_items) or
                    eto_idx < 0 or eto_idx >= len(eto_items)):
                    logger.warning(f"Invalid indices in AI match: PDF {pdf_idx}, ETO {eto_idx}")
                    continue
                
                # Check for duplicate matches
                if pdf_idx in matched_pdf_indices or eto_idx in matched_eto_indices:
                    logger.warning(f"Duplicate match detected: PDF {pdf_idx}, ETO {eto_idx}")
                    continue
                
                # Create match object
                match_obj = {
                    'pdf_item': pdf_items[pdf_idx],
                    'eto_item': eto_items[eto_idx],
                    'confidence': confidence,
                    'match_reasons': match.get('match_reasons', []),
                    'notes': match.get('notes', ''),
                    'ai_matched': True
                }
                
                matches.append(match_obj)
                matched_pdf_indices.add(pdf_idx)
                matched_eto_indices.add(eto_idx)
            
            # Identify unmatched items
            unmatched_pdf = [pdf_items[i] for i in range(len(pdf_items)) if i not in matched_pdf_indices]
            unmatched_eto = [eto_items[i] for i in range(len(eto_items)) if i not in matched_eto_indices]
            
            return {
                'success': True,
                'matches': matches,
                'unmatched_pdf': unmatched_pdf,
                'unmatched_eto': unmatched_eto,
                'match_method': 'ai_content_based',
                'ai_summary': ai_result.get('analysis_summary', 'AI matching completed'),
                'total_matches': len(matches),
                'match_quality_distribution': self._analyze_match_quality(matches)
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI matching response: {e}")
            return {'success': False, 'error': f'JSON parsing failed: {e}'}
        except Exception as e:
            logger.error(f"Error processing AI matching response: {e}")
            return {'success': False, 'error': f'Response processing failed: {e}'}
    
    def _analyze_match_quality(self, matches: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze the quality distribution of matches"""
        quality_count = {'PERFECT': 0, 'GOOD': 0, 'FAIR': 0, 'POOR': 0}
        
        for match in matches:
            confidence = match.get('confidence', 'FAIR')
            if confidence in quality_count:
                quality_count[confidence] += 1
        
        return quality_count
    
    def _fallback_position_matching(self, pdf_items: List[Dict[str, Any]], eto_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback to position-based matching if AI matching fails"""
        logger.info("Using fallback position-based matching")
        
        matches = []
        unmatched_pdf = []
        unmatched_eto = []
        
        max_items = max(len(pdf_items), len(eto_items))
        
        for i in range(max_items):
            pdf_item = pdf_items[i] if i < len(pdf_items) else None
            eto_item = eto_items[i] if i < len(eto_items) else None
            
            if pdf_item and eto_item:
                matches.append({
                    'pdf_item': pdf_item,
                    'eto_item': eto_item,
                    'confidence': 'FAIR',
                    'match_reasons': ['position_based'],
                    'notes': 'Fallback position-based matching',
                    'ai_matched': False
                })
            elif pdf_item:
                unmatched_pdf.append(pdf_item)
            elif eto_item:
                unmatched_eto.append(eto_item)
        
        return {
            'success': True,
            'matches': matches,
            'unmatched_pdf': unmatched_pdf,
            'unmatched_eto': unmatched_eto,
            'match_method': 'position_based_fallback',
            'total_matches': len(matches),
            'match_quality_distribution': self._analyze_match_quality(matches)
        } 