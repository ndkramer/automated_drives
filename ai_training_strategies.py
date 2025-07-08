#!/usr/bin/env python3
"""
AI Training Strategies - Tools for improving AI field extraction through learning
Handles field name variations like "Delivery Date" vs "Promised Date" vs "Delivery On"
"""

import pyodbc
from dotenv import load_dotenv
import os
import json
from datetime import datetime

def get_connection():
    """Get database connection"""
    load_dotenv()
    
    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_DATABASE')
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')

    connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    return pyodbc.connect(connection_string)

def create_training_feedback_table():
    """Create a table to store human feedback for AI training"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create training feedback table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ai_training_feedback' AND xtype='U')
            CREATE TABLE ai_training_feedback (
                id INT IDENTITY(1,1) PRIMARY KEY,
                pdf_upload_id INT NOT NULL,
                field_name NVARCHAR(100) NOT NULL,
                ai_extracted_value NVARCHAR(500),
                human_corrected_value NVARCHAR(500),
                field_label_found NVARCHAR(200),  -- What label was actually in the PDF
                feedback_date DATETIME DEFAULT GETDATE(),
                feedback_type NVARCHAR(50), -- 'correction', 'confirmation', 'new_pattern'
                confidence_score FLOAT,
                notes NVARCHAR(1000),
                FOREIGN KEY (pdf_upload_id) REFERENCES pdf_uploads(id)
            )
        """)
        
        # Create training patterns table for field variations
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='field_label_patterns' AND xtype='U')
            CREATE TABLE field_label_patterns (
                id INT IDENTITY(1,1) PRIMARY KEY,
                standard_field_name NVARCHAR(100) NOT NULL, -- 'delivery_date'
                label_variation NVARCHAR(200) NOT NULL,     -- 'Promised Date', 'Delivery On'
                pattern_confidence FLOAT DEFAULT 1.0,
                usage_count INT DEFAULT 1,
                created_date DATETIME DEFAULT GETDATE(),
                last_seen_date DATETIME DEFAULT GETDATE(),
                is_active BIT DEFAULT 1
            )
        """)
        
        # Insert initial known patterns for delivery date
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM field_label_patterns WHERE standard_field_name = 'delivery_date')
            BEGIN
                INSERT INTO field_label_patterns (standard_field_name, label_variation, pattern_confidence)
                VALUES 
                    ('delivery_date', 'Delivery Date', 1.0),
                    ('delivery_date', 'Promised Date', 0.9),
                    ('delivery_date', 'Delivery On', 0.9),
                    ('delivery_date', 'Due Date', 0.8),
                    ('delivery_date', 'Ship Date', 0.7),
                    ('delivery_date', 'Expected Date', 0.8),
                    ('delivery_date', 'Target Date', 0.7),
                    ('po_number', 'PO Number', 1.0),
                    ('po_number', 'Purchase Order', 0.9),
                    ('po_number', 'Order Number', 0.8),
                    ('po_number', 'PO#', 0.9),
                    ('vendor_name', 'Vendor', 1.0),
                    ('vendor_name', 'Supplier', 0.9),
                    ('vendor_name', 'Company', 0.6),
                    ('vendor_name', 'From', 0.5),
                    ('total_amount', 'Total', 1.0),
                    ('total_amount', 'Amount', 0.9),
                    ('total_amount', 'Total Amount', 1.0),
                    ('total_amount', 'Grand Total', 0.9),
                    ('total_amount', 'Sum', 0.7)
            END
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ Training feedback tables created successfully!")
        print("  • ai_training_feedback - Store human corrections")
        print("  • field_label_patterns - Learn field name variations")
        
    except Exception as e:
        print(f"❌ Error creating training tables: {e}")

def generate_enhanced_ai_prompt():
    """Generate an enhanced AI prompt using learned field patterns"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get field patterns grouped by standard field
        cursor.execute("""
            SELECT standard_field_name, 
                   STRING_AGG(label_variation, '", "') as variations
            FROM field_label_patterns 
            WHERE is_active = 1 
            GROUP BY standard_field_name
            ORDER BY standard_field_name
        """)
        
        field_patterns = {}
        for row in cursor.fetchall():
            standard_field, variations = row
            field_patterns[standard_field] = variations.split('", "')
        
        conn.close()
        
        # Generate enhanced prompt
        enhanced_prompt = f"""
You are an expert at extracting business information from PDF documents. Extract the following fields, being flexible with field label variations:

**DELIVERY DATE** (Look for these labels):
{', '.join(field_patterns.get('delivery_date', ['Delivery Date']))}

**PO NUMBER** (Look for these labels):
{', '.join(field_patterns.get('po_number', ['PO Number']))}

**VENDOR NAME** (Look for these labels):
{', '.join(field_patterns.get('vendor_name', ['Vendor']))}

**TOTAL AMOUNT** (Look for these labels):
{', '.join(field_patterns.get('total_amount', ['Total']))}

Instructions:
1. Look for ANY of the label variations listed above
2. Extract the VALUE associated with each label
3. If multiple variations exist, prioritize the most specific one
4. Return 'null' if the field is not found

Return JSON format:
{{
    "po_number": "extracted_value_or_null",
    "delivery_date": "extracted_value_or_null", 
    "vendor_name": "extracted_value_or_null",
    "total_amount": "extracted_value_or_null",
    "qty": "extracted_value_or_null",
    "unit_price": "extracted_value_or_null",
    "payment_terms": "extracted_value_or_null",
    "invoice_number": "extracted_value_or_null"
}}

IMPORTANT: Be flexible with date formats (MM/DD/YYYY, DD-MM-YYYY, Month DD, YYYY, etc.)
"""
        
        print("🤖 Enhanced AI Prompt with Learned Patterns:")
        print("=" * 60)
        print(enhanced_prompt)
        
        return enhanced_prompt
        
    except Exception as e:
        print(f"❌ Error generating enhanced prompt: {e}")
        return None

def add_training_feedback(pdf_upload_id, field_name, ai_value, human_value, field_label_found, feedback_type="correction"):
    """Add human feedback to improve AI training"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
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
                            ELSE LEAST(pattern_confidence + 0.1, 1.0)
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
        
        print(f"✅ Training feedback added: {field_name} -> {human_value}")
        if field_label_found:
            print(f"   📝 Learned pattern: '{field_label_found}' for {field_name}")
        
    except Exception as e:
        print(f"❌ Error adding training feedback: {e}")

def analyze_extraction_failures():
    """Analyze failed extractions to identify new patterns"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("🔍 Analyzing Extraction Failures for Pattern Discovery")
        print("=" * 60)
        
        # Find documents where key fields are missing
        cursor.execute("""
            SELECT id, filename, raw_text, ai_extracted_data
            FROM pdf_uploads 
            WHERE ai_extraction_success = 1 
            AND (delivery_date IS NULL OR po_number IS NULL OR vendor_name IS NULL)
        """)
        
        missing_fields = []
        for row in cursor.fetchall():
            upload_id, filename, raw_text, ai_data = row
            
            # Simple pattern analysis
            text_lower = raw_text.lower()
            
            patterns_found = []
            
            # Look for date-related patterns
            date_patterns = ['promised date', 'delivery on', 'ship by', 'due on', 'target delivery', 'expected on']
            for pattern in date_patterns:
                if pattern in text_lower:
                    patterns_found.append(('delivery_date', pattern))
            
            # Look for PO patterns
            po_patterns = ['order no', 'po #', 'purchase order #', 'order ref', 'po ref']
            for pattern in po_patterns:
                if pattern in text_lower:
                    patterns_found.append(('po_number', pattern))
            
            # Look for vendor patterns
            vendor_patterns = ['supplier:', 'from:', 'vendor:', 'company:', 'sold by']
            for pattern in vendor_patterns:
                if pattern in text_lower:
                    patterns_found.append(('vendor_name', pattern))
            
            if patterns_found:
                print(f"\n📄 Document {upload_id}: {filename}")
                print("   🔍 Potential missed patterns:")
                for field, pattern in patterns_found:
                    print(f"     • {field}: '{pattern}'")
                missing_fields.extend(patterns_found)
        
        # Suggest new patterns to add
        if missing_fields:
            print(f"\n💡 Suggested Pattern Additions:")
            unique_patterns = list(set(missing_fields))
            for field, pattern in unique_patterns:
                print(f"   • Add '{pattern}' as variation for {field}")
        else:
            print("\n✅ No obvious missed patterns found!")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error analyzing failures: {e}")

def create_training_dataset():
    """Create a training dataset from successful extractions"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("📚 Creating Training Dataset")
        print("=" * 40)
        
        cursor.execute("""
            SELECT filename, raw_text, ai_extracted_data,
                   po_number, vendor_name, total_amount, delivery_date,
                   quantity, unit_price, payment_terms
            FROM pdf_uploads 
            WHERE ai_extraction_success = 1
        """)
        
        training_examples = []
        
        for row in cursor.fetchall():
            (filename, raw_text, ai_data, po_number, vendor_name, total_amount, 
             delivery_date, quantity, unit_price, payment_terms) = row
            
            # Create training example
            example = {
                "input": raw_text[:2000],  # Truncate for training
                "expected_output": {
                    "po_number": po_number,
                    "vendor_name": vendor_name,
                    "total_amount": float(total_amount) if total_amount else None,
                    "delivery_date": str(delivery_date) if delivery_date else None,
                    "quantity": float(quantity) if quantity else None,
                    "unit_price": float(unit_price) if unit_price else None,
                    "payment_terms": payment_terms
                },
                "source_file": filename
            }
            training_examples.append(example)
        
        # Save training dataset
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        training_file = f"training_dataset_{timestamp}.json"
        
        with open(training_file, 'w') as f:
            json.dump(training_examples, f, indent=2, default=str)
        
        print(f"✅ Training dataset saved: {training_file}")
        print(f"   📊 {len(training_examples)} training examples")
        print(f"   🎯 Use this dataset to fine-tune AI models")
        
        conn.close()
        
        return training_file
        
    except Exception as e:
        print(f"❌ Error creating training dataset: {e}")
        return None

def interactive_training_session():
    """Interactive session to provide feedback on AI extractions"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("🎓 Interactive AI Training Session")
        print("=" * 50)
        print("Help improve AI by reviewing and correcting extractions")
        print()
        
        # Get recent uploads for review
        cursor.execute("""
            SELECT TOP 5 id, filename, po_number, vendor_name, delivery_date, total_amount
            FROM pdf_uploads 
            WHERE ai_extraction_success = 1
            ORDER BY id DESC
        """)
        
        uploads = cursor.fetchall()
        
        for upload_id, filename, po_number, vendor_name, delivery_date, total_amount in uploads:
            print(f"📄 Document {upload_id}: {filename}")
            print(f"   AI Extracted:")
            print(f"     PO Number: {po_number}")
            print(f"     Vendor: {vendor_name}")
            print(f"     Delivery Date: {delivery_date}")
            print(f"     Total Amount: ${total_amount}" if total_amount else "     Total Amount: None")
            print()
            
            # In a real implementation, you would:
            # 1. Show the original PDF text
            # 2. Ask user to confirm or correct each field
            # 3. Ask what label was actually used in the PDF
            # 4. Store feedback using add_training_feedback()
            
            print("   💡 To provide feedback, use:")
            print(f"     add_training_feedback({upload_id}, 'delivery_date', '{delivery_date}', 'corrected_value', 'Promised Date')")
            print()
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error in training session: {e}")

def main():
    """Main training strategy menu"""
    print("🤖 AI Training Strategies for Field Variations")
    print("=" * 60)
    print()
    
    strategies = [
        ("1. Create Training Tables", create_training_feedback_table),
        ("2. Generate Enhanced AI Prompt", generate_enhanced_ai_prompt),
        ("3. Analyze Extraction Failures", analyze_extraction_failures),
        ("4. Create Training Dataset", create_training_dataset),
        ("5. Interactive Training Session", interactive_training_session)
    ]
    
    for description, func in strategies:
        print(f"🔸 {description}")
        print()
        try:
            func()
        except Exception as e:
            print(f"❌ Error in {description}: {e}")
        print("\n" + "─" * 60 + "\n")
    
    print("💡 Quick Example: Teaching AI about 'Promised Date'")
    print("=" * 50)
    print("# After finding 'Promised Date' in a PDF:")
    print("add_training_feedback(7, 'delivery_date', '2024-02-15', '2024-02-15', 'Promised Date', 'confirmation')")
    print()
    print("# This teaches the AI that 'Promised Date' = delivery_date field")

if __name__ == "__main__":
    main() 