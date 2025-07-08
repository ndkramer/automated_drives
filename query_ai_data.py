#!/usr/bin/env python3
"""
Query helper for AI-extracted data from PDF uploads
Usage: python query_ai_data.py [field_name]
"""

import pyodbc
from dotenv import load_dotenv
import os
import json
import sys
from typing import Optional

def get_connection():
    """Get database connection"""
    load_dotenv()
    
    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_DATABASE')
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')

    connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    return pyodbc.connect(connection_string)

def query_specific_field(field_name: str):
    """Query for a specific field across all PDFs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, filename, upload_date, ai_extracted_data 
            FROM pdf_uploads 
            WHERE ai_extracted_data IS NOT NULL 
            ORDER BY id DESC
        ''')
        
        print(f"🔍 Searching for field: '{field_name}' in all uploaded PDFs")
        print("=" * 70)
        
        found_count = 0
        for row in cursor.fetchall():
            upload_id, filename, upload_date, ai_data_json = row
            
            if ai_data_json:
                ai_data = json.loads(ai_data_json)
                value = ai_data.get(field_name)
                
                if value and value != 'null':
                    found_count += 1
                    print(f"✅ ID {upload_id} | {filename[:30]:<30} | {field_name}: {value}")
        
        if found_count == 0:
            print(f"❌ No records found with field '{field_name}'")
        else:
            print(f"\n📊 Found {found_count} records with '{field_name}'")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def show_all_data():
    """Show all AI-extracted data"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, filename, upload_date, ai_extraction_success, ai_extracted_data 
            FROM pdf_uploads 
            WHERE ai_extracted_data IS NOT NULL 
            ORDER BY id DESC
        ''')
        
        print("📊 All AI-Extracted Data")
        print("=" * 70)
        
        for row in cursor.fetchall():
            upload_id, filename, upload_date, ai_success, ai_data_json = row
            
            print(f"\n📄 ID {upload_id}: {filename}")
            print(f"   📅 Uploaded: {upload_date}")
            print(f"   🤖 AI Success: {bool(ai_success)}")
            
            if ai_data_json:
                ai_data = json.loads(ai_data_json)
                
                # Show key business fields
                business_fields = {
                    'po_number': 'PO Number',
                    'qty': 'Quantity',
                    'price': 'Price',
                    'delivery_date': 'Delivery Date',
                    'vendor_name': 'Vendor',
                    'total_amount': 'Total Amount'
                }
                
                print("   📋 Key Fields:")
                for field, label in business_fields.items():
                    value = ai_data.get(field)
                    if value and value != 'null':
                        print(f"      ✅ {label}: {value}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def generate_sql_queries():
    """Generate useful SQL queries for AI data"""
    print("📝 Useful SQL Queries for AI-Extracted Data")
    print("=" * 50)
    
    queries = [
        ("Find all PDFs with PO Numbers", 
         "SELECT id, filename, JSON_VALUE(ai_extracted_data, '$.po_number') AS po_number FROM pdf_uploads WHERE JSON_VALUE(ai_extracted_data, '$.po_number') IS NOT NULL;"),
        
        ("Find PDFs with specific vendor",
         "SELECT id, filename, JSON_VALUE(ai_extracted_data, '$.vendor_name') AS vendor FROM pdf_uploads WHERE JSON_VALUE(ai_extracted_data, '$.vendor_name') LIKE '%Manufacturing%';"),
        
        ("Find PDFs by delivery date range",
         "SELECT id, filename, JSON_VALUE(ai_extracted_data, '$.delivery_date') AS delivery_date FROM pdf_uploads WHERE JSON_VALUE(ai_extracted_data, '$.delivery_date') BETWEEN '2024-01-01' AND '2024-12-31';"),
        
        ("Find PDFs with total amount > $1000",
         "SELECT id, filename, JSON_VALUE(ai_extracted_data, '$.total_amount') AS total_amount FROM pdf_uploads WHERE CAST(REPLACE(REPLACE(JSON_VALUE(ai_extracted_data, '$.total_amount'), '$', ''), ',', '') AS FLOAT) > 1000;"),
    ]
    
    for title, query in queries:
        print(f"\n🔍 {title}:")
        print(f"```sql\n{query}\n```")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        field_name = sys.argv[1]
        if field_name == "--sql":
            generate_sql_queries()
        else:
            query_specific_field(field_name)
    else:
        show_all_data()
        print(f"\n💡 Usage:")
        print(f"   python query_ai_data.py po_number    # Search for PO numbers")
        print(f"   python query_ai_data.py vendor_name  # Search for vendor names") 
        print(f"   python query_ai_data.py --sql        # Show SQL query examples") 