#!/usr/bin/env python3
"""
Adaptive AI Extraction Service - Learns from field variations and improves over time
Uses the training database to continuously improve field extraction accuracy
"""

import os
import json
import logging
from datetime import datetime
from anthropic import Anthropic
import pyodbc
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdaptiveAIExtractionService:
    def __init__(self):
        load_dotenv()
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = "claude-3-5-sonnet-20241022"
        
    def get_connection(self):
        """Get database connection"""
        server = os.getenv('DB_SERVER')
        database = os.getenv('DB_DATABASE')
        username = os.getenv('DB_USERNAME')
        password = os.getenv('DB_PASSWORD')

        connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
        return pyodbc.connect(connection_string)
    
    def get_learned_patterns(self):
        """Get learned field patterns from the training database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT standard_field_name, label_variation, pattern_confidence
                FROM field_label_patterns 
                WHERE is_active = 1 
                ORDER BY standard_field_name, pattern_confidence DESC
            """)
            
            patterns = {}
            for row in cursor.fetchall():
                field_name, variation, confidence = row
                if field_name not in patterns:
                    patterns[field_name] = []
                patterns[field_name].append((variation, confidence))
            
            conn.close()
            return patterns
            
        except Exception as e:
            logger.error(f"Error getting learned patterns: {e}")
            return {}
    
    def generate_adaptive_prompt(self, patterns):
        """Generate an AI prompt that adapts based on learned patterns"""
        
        # Build dynamic field instructions
        field_instructions = []
        
        if 'delivery_date' in patterns:
            variations = [p[0] for p in patterns['delivery_date']]
            field_instructions.append(f"""
**DELIVERY DATE** - Look for labels like: {', '.join(variations)}
Extract the date value. Accept various formats: MM/DD/YYYY, DD-MM-YYYY, Month DD YYYY, etc.""")
        
        if 'po_number' in patterns:
            variations = [p[0] for p in patterns['po_number']]
            field_instructions.append(f"""
**PO NUMBER** - Look for labels like: {', '.join(variations)}
Extract the alphanumeric purchase order identifier.""")
        
        if 'vendor_name' in patterns:
            variations = [p[0] for p in patterns['vendor_name']]
            field_instructions.append(f"""
**VENDOR NAME** - Look for labels like: {', '.join(variations)}
Extract the company/supplier name.""")
        
        if 'total_amount' in patterns:
            variations = [p[0] for p in patterns['total_amount']]
            field_instructions.append(f"""
**TOTAL AMOUNT** - Look for labels like: {', '.join(variations)}
Extract the final monetary amount. Remove currency symbols.""")
        
        # Fallback defaults if no patterns learned yet
        if not field_instructions:
            field_instructions = [
                "**DELIVERY DATE** - Look for: Delivery Date, Due Date, Ship Date",
                "**PO NUMBER** - Look for: PO Number, Purchase Order, Order Number",
                "**VENDOR NAME** - Look for: Vendor, Supplier, From",
                "**TOTAL AMOUNT** - Look for: Total, Amount, Total Amount"
            ]
        
        prompt = f"""You are an expert at extracting business information from PDF documents. 

FIELD EXTRACTION GUIDELINES:
{chr(10).join(field_instructions)}

**QUANTITY** - Look for: Qty, Quantity, Amount, Units
**UNIT PRICE** - Look for: Unit Price, Price Each, Rate, Cost
**PAYMENT TERMS** - Look for: Payment Terms, Terms, Net Days
**INVOICE NUMBER** - Look for: Invoice, Invoice #, Inv No

EXTRACTION RULES:
1. Be flexible with label variations - companies use different terminology
2. Look for the VALUE next to or after these labels
3. For dates: Accept any reasonable date format
4. For amounts: Remove currency symbols ($, €, £) and commas
5. If a field is clearly not present, return null
6. Prioritize more specific/complete labels over generic ones

Return a JSON object with these exact field names:
{{
    "po_number": "extracted_value_or_null",
    "delivery_date": "extracted_value_or_null",
    "vendor_name": "extracted_value_or_null", 
    "total_amount": "extracted_value_or_null",
    "qty": "extracted_value_or_null",
    "unit_price": "extracted_value_or_null",
    "payment_terms": "extracted_value_or_null",
    "invoice_number": "extracted_value_or_null",
    "contact_info": {{
        "email": "extracted_email_or_null",
        "phone": "extracted_phone_or_null"
    }}
}}

IMPORTANT: Return ONLY the JSON object, no additional text or explanation."""

        return prompt
    
    def extract_business_data(self, pdf_text):
        """
        Extract business data using adaptive AI with learned patterns
        
        Args:
            pdf_text: Raw text extracted from PDF
            
        Returns:
            Dictionary with extracted data and metadata
        """
        try:
            # Get learned patterns
            patterns = self.get_learned_patterns()
            logger.info(f"Using {len(patterns)} learned field patterns")
            
            # Generate adaptive prompt
            prompt = self.generate_adaptive_prompt(patterns)
            
            # Create the message for Claude
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.1,  # Low temperature for consistent extraction
                messages=[
                    {
                        "role": "user", 
                        "content": f"Extract business information from this document:\n\n{pdf_text}\n\nPrompt:\n{prompt}"
                    }
                ]
            )
            
            response_text = message.content[0].text.strip()
            logger.info(f"AI Response: {response_text}")
            
            # Parse JSON response
            try:
                extracted_data = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from response if there's extra text
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_part = response_text[start_idx:end_idx]
                    extracted_data = json.loads(json_part)
                else:
                    raise ValueError("Could not parse JSON response")
            
            # Calculate extraction success
            success = self._calculate_extraction_success(extracted_data)
            
            return {
                'success': success,
                'ai_extracted_data': extracted_data,
                'extraction_model': self.model,
                'patterns_used': len(patterns),
                'extraction_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'ai_extracted_data': {},
                'extraction_model': self.model,
                'patterns_used': 0,
                'extraction_timestamp': datetime.now().isoformat()
            }
    
    def _calculate_extraction_success(self, extracted_data):
        """Calculate extraction success based on key fields"""
        key_fields = ['po_number', 'vendor_name', 'total_amount']
        extracted_count = 0
        
        for field in key_fields:
            if field in extracted_data and extracted_data[field] and extracted_data[field] != 'null':
                extracted_count += 1
        
        # Consider successful if at least 2 out of 3 key fields are extracted
        return extracted_count >= 2
    
    def add_training_feedback(self, pdf_upload_id, field_name, ai_value, human_value, field_label_found, feedback_type="correction"):
        """Add human feedback to improve future extractions"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Add feedback record
            cursor.execute("""
                INSERT INTO ai_training_feedback 
                (pdf_upload_id, field_name, ai_extracted_value, human_corrected_value, 
                 field_label_found, feedback_type, feedback_date)
                VALUES (?, ?, ?, ?, ?, ?, GETDATE())
            """, (pdf_upload_id, field_name, ai_value, human_value, field_label_found, feedback_type))
            
            # Update or add field pattern
            if field_label_found:
                cursor.execute("""
                    IF EXISTS (SELECT * FROM field_label_patterns 
                              WHERE standard_field_name = ? AND label_variation = ?)
                    BEGIN
                        UPDATE field_label_patterns 
                        SET usage_count = usage_count + 1, 
                            last_seen_date = GETDATE(),
                                                    pattern_confidence = CASE 
                            WHEN ? = 'correction' THEN pattern_confidence * 0.9
                            ELSE CASE WHEN pattern_confidence + 0.1 > 1.0 THEN 1.0 ELSE pattern_confidence + 0.1 END
                        END
                        WHERE standard_field_name = ? AND label_variation = ?
                    END
                    ELSE
                    BEGIN
                        INSERT INTO field_label_patterns 
                        (standard_field_name, label_variation, pattern_confidence, usage_count)
                        VALUES (?, ?, 0.7, 1)
                    END
                """, (field_name, field_label_found, feedback_type, field_name, field_label_found, 
                      field_name, field_label_found))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Training feedback added: {field_name} -> {human_value}")
            if field_label_found:
                logger.info(f"Learned pattern: '{field_label_found}' for {field_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding training feedback: {e}")
            return False
    
    def analyze_field_performance(self):
        """Analyze field extraction performance and suggest improvements"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get field accuracy stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_extractions,
                    SUM(CASE WHEN po_number IS NOT NULL THEN 1 ELSE 0 END) as po_success,
                    SUM(CASE WHEN vendor_name IS NOT NULL THEN 1 ELSE 0 END) as vendor_success,
                    SUM(CASE WHEN total_amount IS NOT NULL THEN 1 ELSE 0 END) as amount_success,
                    SUM(CASE WHEN delivery_date IS NOT NULL THEN 1 ELSE 0 END) as date_success
                FROM pdf_uploads 
                WHERE ai_extraction_success = 1
            """)
            
            stats = cursor.fetchone()
            if stats and stats[0] > 0:
                total = stats[0]
                performance = {
                    'po_number': (stats[1] / total) * 100,
                    'vendor_name': (stats[2] / total) * 100,
                    'total_amount': (stats[3] / total) * 100,
                    'delivery_date': (stats[4] / total) * 100
                }
                
                # Identify fields needing improvement
                improvements_needed = []
                for field, accuracy in performance.items():
                    if accuracy < 90:
                        improvements_needed.append(field)
                
                return {
                    'total_extractions': total,
                    'field_performance': performance,
                    'improvements_needed': improvements_needed
                }
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return None


# Example usage function
def train_on_field_variation():
    """Example of how to train the AI on field variations"""
    service = AdaptiveAIExtractionService()
    
    # Example: Teaching AI that "Promised Date" = delivery_date
    success = service.add_training_feedback(
        pdf_upload_id=7,
        field_name='delivery_date',
        ai_value='2024-02-15',
        human_value='2024-02-15',
        field_label_found='Promised Date',
        feedback_type='confirmation'
    )
    
    if success:
        print("✅ Successfully taught AI that 'Promised Date' = delivery_date")
        
        # The next PDF extraction will now look for "Promised Date" as well
        patterns = service.get_learned_patterns()
        print(f"📚 AI now knows {len(patterns)} field patterns")


if __name__ == "__main__":
    # Example of training the AI
    train_on_field_variation() 