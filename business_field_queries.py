#!/usr/bin/env python3
"""
Business Field Query Tool - Demonstrates the power of individual column storage
This shows how easy it is to query, compare, and analyze business data with separate columns.
"""

import pyodbc
from dotenv import load_dotenv
import os
from decimal import Decimal

def get_connection():
    """Get database connection"""
    load_dotenv()
    
    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_DATABASE')
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')

    connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    return pyodbc.connect(connection_string)

def format_currency(value):
    """Format decimal values as currency"""
    if value is None:
        return "None"
    return f"${value:,.2f}"

def show_all_business_data():
    """Show all business data in a clean tabular format"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, filename, po_number, vendor_name, quantity, unit_price, 
                   total_amount, delivery_date, payment_terms, contact_email
            FROM pdf_uploads 
            WHERE po_number IS NOT NULL OR vendor_name IS NOT NULL
            ORDER BY id DESC
        ''')
        
        print("📊 Business Data Overview")
        print("=" * 120)
        print(f"{'ID':<3} {'PO Number':<15} {'Vendor':<25} {'Qty':<8} {'Unit Price':<12} {'Total':<12} {'Delivery':<12}")
        print("-" * 120)
        
        for row in cursor.fetchall():
            upload_id, filename, po_number, vendor_name, quantity, unit_price, total_amount, delivery_date, payment_terms, contact_email = row
            
            po_display = (po_number or "")[:14]
            vendor_display = (vendor_name or "")[:24]
            qty_display = f"{quantity:.0f}" if quantity else ""
            unit_price_display = format_currency(unit_price)[:11]
            total_display = format_currency(total_amount)[:11]
            delivery_display = str(delivery_date)[:11] if delivery_date else ""
            
            print(f"{upload_id:<3} {po_display:<15} {vendor_display:<25} {qty_display:<8} {unit_price_display:<12} {total_display:<12} {delivery_display:<12}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def query_by_vendor():
    """Show how easy it is to query by vendor"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n🔍 Query: All POs from vendors containing 'Manufacturing'")
        print("=" * 60)
        
        cursor.execute('''
            SELECT po_number, vendor_name, total_amount, delivery_date
            FROM pdf_uploads 
            WHERE vendor_name LIKE '%Manufacturing%'
            ORDER BY total_amount DESC
        ''')
        
        for row in cursor.fetchall():
            po_number, vendor_name, total_amount, delivery_date = row
            print(f"PO: {po_number} | Vendor: {vendor_name} | Amount: {format_currency(total_amount)} | Due: {delivery_date}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def query_by_amount():
    """Show financial analysis queries"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n💰 Financial Analysis")
        print("=" * 50)
        
        # Total value of all POs
        cursor.execute('SELECT SUM(total_amount) as total_value, COUNT(*) as po_count FROM pdf_uploads WHERE total_amount IS NOT NULL')
        total_value, po_count = cursor.fetchone()
        print(f"Total PO Value: {format_currency(total_value)} across {po_count} POs")
        
        # Average PO value
        cursor.execute('SELECT AVG(total_amount) as avg_value FROM pdf_uploads WHERE total_amount IS NOT NULL')
        avg_value = cursor.fetchone()[0]
        print(f"Average PO Value: {format_currency(avg_value)}")
        
        # POs over $1000
        print(f"\n🔍 POs over $1,000:")
        cursor.execute('''
            SELECT po_number, vendor_name, total_amount
            FROM pdf_uploads 
            WHERE total_amount > 1000
            ORDER BY total_amount DESC
        ''')
        
        for row in cursor.fetchall():
            po_number, vendor_name, total_amount = row
            print(f"  • {po_number} | {vendor_name} | {format_currency(total_amount)}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def query_by_delivery_date():
    """Show date-based queries"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n📅 Delivery Date Analysis")
        print("=" * 50)
        
        # POs due in 2024
        cursor.execute('''
            SELECT po_number, vendor_name, delivery_date, total_amount
            FROM pdf_uploads 
            WHERE delivery_date LIKE '2024%'
            ORDER BY delivery_date
        ''')
        
        print("POs due in 2024:")
        for row in cursor.fetchall():
            po_number, vendor_name, delivery_date, total_amount = row
            print(f"  • {delivery_date} | {po_number} | {vendor_name} | {format_currency(total_amount)}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def show_comparison_examples():
    """Show examples of how this would enable easy comparison with ETOSandbox"""
    print("\n🔄 Easy Comparison with ETOSandbox Database")
    print("=" * 60)
    
    print("With individual columns, you can now easily:")
    print()
    
    comparison_queries = [
        ("Find missing POs", """
        SELECT p.po_number, p.vendor_name, p.total_amount
        FROM ETO_PDF.dbo.pdf_uploads p
        LEFT JOIN ETOSandbox.dbo.purchase_orders e ON p.po_number = e.order_number
        WHERE e.order_number IS NULL AND p.po_number IS NOT NULL
        """),
        
        ("Compare amounts", """
        SELECT p.po_number, p.total_amount as pdf_amount, e.total_value as eto_amount,
               ABS(p.total_amount - e.total_value) as difference
        FROM ETO_PDF.dbo.pdf_uploads p
        JOIN ETOSandbox.dbo.purchase_orders e ON p.po_number = e.order_number
        WHERE ABS(p.total_amount - e.total_value) > 0.01
        """),
        
        ("Find vendor discrepancies", """
        SELECT p.po_number, p.vendor_name as pdf_vendor, e.vendor_name as eto_vendor
        FROM ETO_PDF.dbo.pdf_uploads p
        JOIN ETOSandbox.dbo.purchase_orders e ON p.po_number = e.order_number
        WHERE p.vendor_name != e.vendor_name
        """),
        
        ("Delivery date differences", """
        SELECT p.po_number, p.delivery_date as pdf_delivery, e.expected_date as eto_delivery
        FROM ETO_PDF.dbo.pdf_uploads p
        JOIN ETOSandbox.dbo.purchase_orders e ON p.po_number = e.order_number
        WHERE p.delivery_date != e.expected_date
        """)
    ]
    
    for title, query in comparison_queries:
        print(f"📋 {title}:")
        print(f"```sql\n{query.strip()}\n```\n")

def show_ai_training_benefits():
    """Show how individual columns help with AI training"""
    print("\n🤖 AI Training & Validation Benefits")
    print("=" * 50)
    
    print("Individual columns enable:")
    print("✅ Field-level accuracy tracking")
    print("✅ Identify which fields need prompt improvement")
    print("✅ A/B test different AI models per field")
    print("✅ Validate extracted data against business rules")
    print("✅ Generate training datasets for fine-tuning")
    print()
    
    training_queries = [
        ("Track PO Number extraction accuracy", """
        SELECT 
            COUNT(*) as total_docs,
            SUM(CASE WHEN po_number IS NOT NULL THEN 1 ELSE 0 END) as po_extracted,
            (SUM(CASE WHEN po_number IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as accuracy_pct
        FROM pdf_uploads WHERE ai_extraction_success = 1
        """),
        
        ("Find documents where AI missed vendor", """
        SELECT id, filename, raw_text
        FROM pdf_uploads 
        WHERE ai_extraction_success = 1 AND vendor_name IS NULL
        AND raw_text LIKE '%vendor%' OR raw_text LIKE '%supplier%'
        """),
        
        ("Validate amount formats", """
        SELECT po_number, total_amount, ai_extracted_data
        FROM pdf_uploads 
        WHERE total_amount > 0 AND (total_amount < 1 OR total_amount > 1000000)
        """)
    ]
    
    for title, query in training_queries:
        print(f"📊 {title}:")
        print(f"```sql\n{query.strip()}\n```\n")

def main():
    """Run all demonstrations"""
    print("🎯 Business Field Columns - Query Demonstration")
    print("=" * 60)
    
    show_all_business_data()
    query_by_vendor()
    query_by_amount()
    query_by_delivery_date()
    show_comparison_examples()
    show_ai_training_benefits()
    
    print("\n💡 Summary:")
    print("Individual columns provide:")
    print("  ✅ Fast, indexed queries")
    print("  ✅ Easy comparison with other databases")
    print("  ✅ Simple analytics and reporting")
    print("  ✅ Field-level AI training insights")
    print("  ✅ Data validation and quality checks")

if __name__ == "__main__":
    main() 