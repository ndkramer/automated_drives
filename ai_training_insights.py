#!/usr/bin/env python3
"""
AI Training Insights - Demonstrates how individual columns enable better AI training
Shows field-level accuracy, identifies improvement areas, and validates extraction quality.
"""

import pyodbc
from dotenv import load_dotenv
import os

def get_connection():
    """Get database connection"""
    load_dotenv()
    
    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_DATABASE')
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')

    connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    return pyodbc.connect(connection_string)

def field_extraction_accuracy():
    """Show field-level extraction accuracy metrics"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("🎯 AI Field Extraction Accuracy Analysis")
        print("=" * 60)
        
        # Get counts for each field
        cursor.execute("""
            SELECT 
                COUNT(*) as total_successful_extractions,
                SUM(CASE WHEN po_number IS NOT NULL THEN 1 ELSE 0 END) as po_number_extracted,
                SUM(CASE WHEN vendor_name IS NOT NULL THEN 1 ELSE 0 END) as vendor_extracted,
                SUM(CASE WHEN total_amount IS NOT NULL THEN 1 ELSE 0 END) as amount_extracted,
                SUM(CASE WHEN quantity IS NOT NULL THEN 1 ELSE 0 END) as quantity_extracted,
                SUM(CASE WHEN delivery_date IS NOT NULL THEN 1 ELSE 0 END) as date_extracted,
                SUM(CASE WHEN unit_price IS NOT NULL THEN 1 ELSE 0 END) as unit_price_extracted,
                SUM(CASE WHEN payment_terms IS NOT NULL THEN 1 ELSE 0 END) as payment_terms_extracted,
                SUM(CASE WHEN contact_email IS NOT NULL THEN 1 ELSE 0 END) as email_extracted,
                SUM(CASE WHEN contact_phone IS NOT NULL THEN 1 ELSE 0 END) as phone_extracted
            FROM pdf_uploads 
            WHERE ai_extraction_success = 1
        """)
        
        row = cursor.fetchone()
        if row:
            total = row[0]
            if total > 0:
                fields = [
                    ("PO Number", row[1]),
                    ("Vendor Name", row[2]),
                    ("Total Amount", row[3]),
                    ("Quantity", row[4]),
                    ("Delivery Date", row[5]),
                    ("Unit Price", row[6]),
                    ("Payment Terms", row[7]),
                    ("Contact Email", row[8]),
                    ("Contact Phone", row[9])
                ]
                
                print(f"📊 Analysis of {total} successful AI extractions:")
                print()
                print(f"{'Field':<15} {'Extracted':<10} {'Accuracy':<10} {'Status'}")
                print("-" * 50)
                
                for field_name, extracted_count in fields:
                    accuracy = (extracted_count / total) * 100
                    status = "🟢 Excellent" if accuracy >= 90 else "🟡 Good" if accuracy >= 70 else "🔴 Needs Work"
                    print(f"{field_name:<15} {extracted_count:<10} {accuracy:>6.1f}%    {status}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def identify_problematic_documents():
    """Find documents where AI extraction partially failed"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n🔍 Problematic Document Analysis")
        print("=" * 60)
        
        # Find documents with missing critical fields
        cursor.execute("""
            SELECT id, filename, 
                   CASE WHEN po_number IS NULL THEN 'Missing PO' ELSE '' END +
                   CASE WHEN vendor_name IS NULL THEN ' Missing Vendor' ELSE '' END +
                   CASE WHEN total_amount IS NULL THEN ' Missing Amount' ELSE '' END as issues
            FROM pdf_uploads 
            WHERE ai_extraction_success = 1 
            AND (po_number IS NULL OR vendor_name IS NULL OR total_amount IS NULL)
        """)
        
        print("Documents with missing critical fields:")
        missing_count = 0
        for row in cursor.fetchall():
            upload_id, filename, issues = row
            print(f"  • ID {upload_id}: {filename}")
            print(f"    Issues: {issues.strip()}")
            missing_count += 1
        
        if missing_count == 0:
            print("  ✅ No documents with missing critical fields!")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def data_quality_validation():
    """Validate extracted data quality"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n🔬 Data Quality Validation")
        print("=" * 60)
        
        # Check for suspicious amounts
        cursor.execute("""
            SELECT COUNT(*) as suspicious_amounts
            FROM pdf_uploads 
            WHERE total_amount IS NOT NULL 
            AND (total_amount < 0.01 OR total_amount > 1000000)
        """)
        
        suspicious_amounts = cursor.fetchone()[0]
        print(f"Suspicious amounts (< $0.01 or > $1M): {suspicious_amounts}")
        
        # Check for unusual quantities
        cursor.execute("""
            SELECT COUNT(*) as unusual_quantities
            FROM pdf_uploads 
            WHERE quantity IS NOT NULL 
            AND (quantity < 0 OR quantity > 10000)
        """)
        
        unusual_quantities = cursor.fetchone()[0]
        print(f"Unusual quantities (< 0 or > 10,000): {unusual_quantities}")
        
        # Check date formats
        cursor.execute("""
            SELECT COUNT(*) as docs_with_dates
            FROM pdf_uploads 
            WHERE delivery_date IS NOT NULL
        """)
        
        docs_with_dates = cursor.fetchone()[0]
        print(f"Documents with valid delivery dates: {docs_with_dates}")
        
        # Check for reasonable unit prices
        cursor.execute("""
            SELECT AVG(unit_price) as avg_unit_price, 
                   MIN(unit_price) as min_unit_price,
                   MAX(unit_price) as max_unit_price
            FROM pdf_uploads 
            WHERE unit_price IS NOT NULL AND unit_price > 0
        """)
        
        price_stats = cursor.fetchone()
        if price_stats and price_stats[0]:
            avg_price, min_price, max_price = price_stats
            print(f"Unit price range: ${min_price:.2f} to ${max_price:.2f} (avg: ${avg_price:.2f})")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def vendor_name_analysis():
    """Analyze vendor name extraction patterns"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n🏢 Vendor Name Analysis")
        print("=" * 60)
        
        # List unique vendors
        cursor.execute("""
            SELECT vendor_name, COUNT(*) as document_count, AVG(total_amount) as avg_amount
            FROM pdf_uploads 
            WHERE vendor_name IS NOT NULL
            GROUP BY vendor_name
            ORDER BY document_count DESC
        """)
        
        print("Extracted vendor names:")
        for row in cursor.fetchall():
            vendor_name, doc_count, avg_amount = row
            avg_display = f"${avg_amount:.2f}" if avg_amount else "N/A"
            print(f"  • {vendor_name} ({doc_count} docs, avg: {avg_display})")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def ai_prompt_optimization_suggestions():
    """Provide suggestions for AI prompt optimization"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n💡 AI Prompt Optimization Suggestions")
        print("=" * 60)
        
        # Find patterns in failed extractions
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN po_number IS NULL THEN 1 ELSE 0 END) as missing_po,
                SUM(CASE WHEN vendor_name IS NULL THEN 1 ELSE 0 END) as missing_vendor,
                SUM(CASE WHEN total_amount IS NULL THEN 1 ELSE 0 END) as missing_amount,
                SUM(CASE WHEN unit_price IS NULL THEN 1 ELSE 0 END) as missing_unit_price,
                COUNT(*) as total_docs
            FROM pdf_uploads WHERE ai_extraction_success = 1
        """)
        
        row = cursor.fetchone()
        if row:
            missing_po, missing_vendor, missing_amount, missing_unit_price, total_docs = row
            
            suggestions = []
            
            if missing_po > 0:
                po_rate = (missing_po / total_docs) * 100
                suggestions.append(f"🔸 PO Number missing in {po_rate:.1f}% of docs - Consider adding more PO number patterns to prompt")
            
            if missing_vendor > 0:
                vendor_rate = (missing_vendor / total_docs) * 100
                suggestions.append(f"🔸 Vendor missing in {vendor_rate:.1f}% of docs - Expand vendor identification keywords")
            
            if missing_amount > 0:
                amount_rate = (missing_amount / total_docs) * 100
                suggestions.append(f"🔸 Amount missing in {amount_rate:.1f}% of docs - Improve total amount recognition patterns")
            
            if missing_unit_price > 0:
                price_rate = (missing_unit_price / total_docs) * 100
                suggestions.append(f"🔸 Unit price missing in {price_rate:.1f}% of docs - Add unit price extraction examples")
            
            if suggestions:
                print("Based on extraction patterns, consider these improvements:")
                for suggestion in suggestions:
                    print(f"  {suggestion}")
            else:
                print("✅ Extraction accuracy is excellent across all fields!")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

def main():
    """Run all AI training analyses"""
    print("🤖 AI Training Insights Dashboard")
    print("=" * 60)
    
    field_extraction_accuracy()
    identify_problematic_documents()
    data_quality_validation()
    vendor_name_analysis()
    ai_prompt_optimization_suggestions()
    
    print("\n📈 Key Benefits of Individual Columns for AI Training:")
    print("  ✅ Track accuracy per business field")
    print("  ✅ Identify specific prompt improvement areas")
    print("  ✅ Validate extracted data quality automatically")
    print("  ✅ Monitor AI performance over time")
    print("  ✅ A/B test different extraction strategies")

if __name__ == "__main__":
    main() 