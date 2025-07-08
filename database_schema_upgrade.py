#!/usr/bin/env python3
"""
Database Schema Upgrade - Add Individual Business Field Columns
This script adds separate columns for common business fields to make querying and comparison easier.
"""

import pyodbc
from dotenv import load_dotenv
import os
import json

def upgrade_database_schema():
    """Upgrade the database to include individual business field columns"""
    
    load_dotenv()
    
    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_DATABASE')
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')

    connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        print("🔄 Upgrading database schema with business field columns...")
        
        # Check existing columns
        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'pdf_uploads' AND COLUMN_NAME IN (
                'po_number', 'quantity', 'unit_price', 'total_amount', 
                'delivery_date', 'vendor_name', 'invoice_number', 'payment_terms'
            )
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        # Define new business field columns
        new_columns = [
            ("po_number", "NVARCHAR(100)", "Purchase Order Number"),
            ("quantity", "DECIMAL(18,4)", "Quantity/Amount"),  
            ("unit_price", "DECIMAL(18,4)", "Unit Price"),
            ("total_amount", "DECIMAL(18,4)", "Total Amount"),
            ("delivery_date", "DATE", "Delivery/Due Date"),
            ("vendor_name", "NVARCHAR(255)", "Vendor/Supplier Name"),
            ("customer_name", "NVARCHAR(255)", "Customer Name"),
            ("invoice_number", "NVARCHAR(100)", "Invoice Number"),
            ("payment_terms", "NVARCHAR(100)", "Payment Terms"),
            ("description", "NVARCHAR(500)", "Item Description"),
            ("currency", "NVARCHAR(10)", "Currency Code"),
            ("tax_amount", "DECIMAL(18,4)", "Tax Amount"),
            ("contact_email", "NVARCHAR(255)", "Contact Email"),
            ("contact_phone", "NVARCHAR(50)", "Contact Phone")
        ]
        
        # Add missing columns
        added_columns = []
        for column_name, data_type, description in new_columns:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE pdf_uploads ADD {column_name} {data_type}")
                    added_columns.append(f"{column_name} ({data_type})")
                    print(f"✅ Added column: {column_name} - {description}")
                except Exception as e:
                    print(f"❌ Failed to add {column_name}: {e}")
        
        # Add indexes for common query fields
        indexes_to_create = [
            ("idx_pdf_uploads_po_number", "po_number"),
            ("idx_pdf_uploads_vendor_name", "vendor_name"),
            ("idx_pdf_uploads_delivery_date", "delivery_date"),
            ("idx_pdf_uploads_total_amount", "total_amount")
        ]
        
        for index_name, column_name in indexes_to_create:
            try:
                cursor.execute(f"CREATE INDEX {index_name} ON pdf_uploads ({column_name})")
                print(f"✅ Created index: {index_name}")
            except Exception as e:
                if "already exists" not in str(e):
                    print(f"❌ Failed to create index {index_name}: {e}")
        
        conn.commit()
        
        if added_columns:
            print(f"\n📊 Schema upgrade completed! Added {len(added_columns)} columns:")
            for col in added_columns:
                print(f"   - {col}")
        else:
            print("📊 Schema is already up to date!")
            
        print(f"\n🔄 Now migrating existing AI data to new columns...")
        migrate_existing_data(cursor, conn)
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error upgrading schema: {e}")

def migrate_existing_data(cursor, conn):
    """Migrate existing AI-extracted data to the new columns"""
    
    try:
        # Get records with AI data
        cursor.execute("""
            SELECT id, ai_extracted_data 
            FROM pdf_uploads 
            WHERE ai_extracted_data IS NOT NULL AND ai_extraction_success = 1
        """)
        
        records = cursor.fetchall()
        migrated_count = 0
        
        for record_id, ai_data_json in records:
            try:
                ai_data = json.loads(ai_data_json)
                
                # Extract and clean values
                def clean_numeric(value):
                    """Clean numeric values for database storage"""
                    if not value or value == 'null':
                        return None
                    # Remove currency symbols and commas
                    clean_val = str(value).replace('$', '').replace(',', '').replace('€', '').replace('£', '')
                    try:
                        return float(clean_val)
                    except:
                        return None
                
                def clean_date(value):
                    """Clean date values for database storage"""
                    if not value or value == 'null':
                        return None
                    # Basic date format validation - could be enhanced
                    return str(value) if len(str(value)) >= 8 else None
                
                def clean_text(value, max_length=None):
                    """Clean text values for database storage"""
                    if not value or value == 'null':
                        return None
                    text = str(value).strip()
                    if max_length and len(text) > max_length:
                        text = text[:max_length]
                    return text if text else None
                
                # Map AI fields to database columns
                field_mappings = {
                    'po_number': clean_text(ai_data.get('po_number'), 100),
                    'quantity': clean_numeric(ai_data.get('qty') or ai_data.get('quantity')),
                    'unit_price': clean_numeric(ai_data.get('unit_price')),
                    'total_amount': clean_numeric(ai_data.get('total_amount') or ai_data.get('price')),
                    'delivery_date': clean_date(ai_data.get('delivery_date')),
                    'vendor_name': clean_text(ai_data.get('vendor_name'), 255),
                    'customer_name': clean_text(ai_data.get('customer_name'), 255),
                    'invoice_number': clean_text(ai_data.get('invoice_number'), 100),
                    'payment_terms': clean_text(ai_data.get('payment_terms'), 100),
                    'description': clean_text(ai_data.get('description'), 500),
                    'tax_amount': clean_numeric(ai_data.get('tax_amount'))
                }
                
                # Extract contact info
                contact_info = ai_data.get('contact_info', {})
                if isinstance(contact_info, dict):
                    field_mappings['contact_email'] = clean_text(contact_info.get('email'), 255)
                    field_mappings['contact_phone'] = clean_text(contact_info.get('phone'), 50)
                
                # Build update query
                set_clauses = []
                params = []
                for field, value in field_mappings.items():
                    if value is not None:
                        set_clauses.append(f"{field} = ?")
                        params.append(value)
                
                if set_clauses:
                    update_query = f"UPDATE pdf_uploads SET {', '.join(set_clauses)} WHERE id = ?"
                    params.append(record_id)
                    
                    cursor.execute(update_query, params)
                    migrated_count += 1
                    print(f"✅ Migrated record {record_id}")
                
            except Exception as e:
                print(f"❌ Failed to migrate record {record_id}: {e}")
        
        conn.commit()
        print(f"\n📊 Migration completed! Updated {migrated_count} records with structured data.")
        
    except Exception as e:
        print(f"❌ Error during data migration: {e}")

if __name__ == "__main__":
    upgrade_database_schema() 