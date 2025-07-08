#!/usr/bin/env python3
"""
Header/Detail Schema Upgrade - Split PDF data into proper 1-to-many structure
This creates proper normalized tables: pdf_headers (1) to pdf_line_items (many)
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

def create_header_detail_schema():
    """Create the new header/detail table structure"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("🔄 Creating Header/Detail Schema...")
        print("=" * 60)
        
        # Create PDF Headers table (1 per document)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='pdf_headers' AND xtype='U')
            CREATE TABLE pdf_headers (
                id INT IDENTITY(1,1) PRIMARY KEY,
                
                -- File Information
                filename NVARCHAR(255) NOT NULL,
                upload_date DATETIME DEFAULT GETDATE(),
                file_size BIGINT,
                page_count INT,
                status NVARCHAR(50) DEFAULT 'processed',
                
                -- Document Content
                raw_text NVARCHAR(MAX),
                metadata NVARCHAR(MAX),
                structured_data NVARCHAR(MAX),
                
                -- AI Processing
                ai_extracted_data NVARCHAR(MAX),
                extraction_model NVARCHAR(100),
                ai_extraction_success BIT DEFAULT 0,
                
                -- HEADER-LEVEL BUSINESS FIELDS (document-wide info)
                po_number NVARCHAR(100),              -- Purchase Order Number
                vendor_name NVARCHAR(255),            -- Vendor/Supplier
                customer_name NVARCHAR(255),          -- Customer/Buyer
                invoice_number NVARCHAR(100),         -- Invoice Number
                invoice_date DATE,                    -- Invoice Date
                delivery_date DATE,                   -- Overall delivery date
                payment_terms NVARCHAR(100),         -- Payment Terms
                currency NVARCHAR(10),               -- Currency Code
                tax_rate DECIMAL(5,4),               -- Tax Rate (e.g., 0.0825 for 8.25%)
                tax_amount DECIMAL(18,4),            -- Total Tax Amount
                subtotal DECIMAL(18,4),              -- Subtotal before tax
                total_amount DECIMAL(18,4),          -- Grand Total
                contact_email NVARCHAR(255),         -- Contact Email
                contact_phone NVARCHAR(50),          -- Contact Phone
                shipping_address NVARCHAR(MAX),      -- Shipping Address
                billing_address NVARCHAR(MAX),       -- Billing Address
                
                -- Audit Fields
                created_date DATETIME DEFAULT GETDATE(),
                modified_date DATETIME DEFAULT GETDATE()
            )
        """)
        print("✅ Created pdf_headers table (document-level data)")
        
        # Create PDF Line Items table (many per document)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='pdf_line_items' AND xtype='U')
            CREATE TABLE pdf_line_items (
                id INT IDENTITY(1,1) PRIMARY KEY,
                pdf_header_id INT NOT NULL,           -- Foreign key to pdf_headers
                
                -- LINE ITEM SPECIFIC FIELDS
                line_number INT,                      -- Line number on document
                item_code NVARCHAR(100),             -- Product/Item code
                description NVARCHAR(500),           -- Item description
                quantity DECIMAL(18,4),              -- Quantity ordered
                unit_of_measure NVARCHAR(20),        -- UOM (each, lbs, kg, etc.)
                unit_price DECIMAL(18,4),            -- Price per unit
                line_total DECIMAL(18,4),            -- Quantity * Unit Price
                discount_percent DECIMAL(5,4),       -- Discount percentage
                discount_amount DECIMAL(18,4),       -- Discount amount
                line_delivery_date DATE,             -- Line-specific delivery date
                delivery_date_inherited BIT DEFAULT 0,  -- Track if delivery date inherited from header
                
                -- Optional Manufacturing Fields
                drawing_number NVARCHAR(100),        -- Engineering drawing number
                revision NVARCHAR(20),               -- Drawing revision
                material NVARCHAR(100),              -- Material specification
                finish NVARCHAR(100),                -- Surface finish
                
                -- AI Extraction Meta
                extraction_confidence FLOAT,         -- AI confidence for this line
                extracted_from_text NVARCHAR(1000),  -- Original text this was extracted from
                
                -- Audit Fields
                created_date DATETIME DEFAULT GETDATE(),
                
                -- Foreign Key Constraint
                FOREIGN KEY (pdf_header_id) REFERENCES pdf_headers(id) ON DELETE CASCADE
            )
        """)
        print("✅ Created pdf_line_items table (line item data)")
        
        # Create indexes for performance
        indexes_to_create = [
            ("idx_pdf_headers_po_number", "pdf_headers", "po_number"),
            ("idx_pdf_headers_vendor_name", "pdf_headers", "vendor_name"),
            ("idx_pdf_headers_invoice_date", "pdf_headers", "invoice_date"),
            ("idx_pdf_headers_total_amount", "pdf_headers", "total_amount"),
            ("idx_pdf_line_items_header_id", "pdf_line_items", "pdf_header_id"),
            ("idx_pdf_line_items_item_code", "pdf_line_items", "item_code"),
            ("idx_pdf_line_items_line_number", "pdf_line_items", "line_number")
        ]
        
        for index_name, table_name, column_name in indexes_to_create:
            try:
                cursor.execute(f"CREATE INDEX {index_name} ON {table_name} ({column_name})")
                print(f"✅ Created index: {index_name}")
            except Exception as e:
                if "already exists" not in str(e):
                    print(f"❌ Failed to create index {index_name}: {e}")
        
        # Create views for easy querying
        cursor.execute("""
            IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_pdf_complete')
                DROP VIEW vw_pdf_complete
        """)
        
        cursor.execute("""
            CREATE VIEW vw_pdf_complete AS
            SELECT 
                h.id as header_id,
                h.filename,
                h.po_number,
                h.vendor_name,
                h.customer_name,
                h.invoice_number,
                h.invoice_date,
                h.total_amount,
                h.payment_terms,
                
                -- Line item details
                li.id as line_item_id,
                li.line_number,
                li.item_code,
                li.description,
                li.quantity,
                li.unit_price,
                li.line_total,
                li.unit_of_measure,
                li.line_delivery_date
                
            FROM pdf_headers h
            LEFT JOIN pdf_line_items li ON h.id = li.pdf_header_id
        """)
        print("✅ Created vw_pdf_complete view for easy querying")
        
        conn.commit()
        print(f"\n📊 Header/Detail schema created successfully!")
        print(f"   • pdf_headers: Document-level information")
        print(f"   • pdf_line_items: Line item details")
        print(f"   • 1-to-many relationship established")
        print(f"   • Performance indexes created")
        print(f"   • Complete view created for reporting")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating header/detail schema: {e}")

def migrate_existing_data():
    """Migrate data from old pdf_uploads table to new header/detail structure"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n🔄 Migrating existing data to header/detail structure...")
        print("=" * 60)
        
        # Check if old table exists
        cursor.execute("""
            SELECT COUNT(*) FROM sysobjects WHERE name='pdf_uploads' AND xtype='U'
        """)
        
        if cursor.fetchone()[0] == 0:
            print("📋 No pdf_uploads table found - starting fresh!")
            return
        
        # Get existing data
        cursor.execute("""
            SELECT id, filename, upload_date, file_size, page_count, status,
                   metadata, raw_text, structured_data, ai_extracted_data,
                   extraction_model, ai_extraction_success,
                   po_number, quantity, unit_price, total_amount, delivery_date,
                   vendor_name, customer_name, invoice_number, payment_terms,
                   description, tax_amount, contact_email, contact_phone
            FROM pdf_uploads
        """)
        
        old_records = cursor.fetchall()
        migrated_headers = 0
        migrated_line_items = 0
        
        for record in old_records:
            try:
                (old_id, filename, upload_date, file_size, page_count, status,
                 metadata, raw_text, structured_data, ai_extracted_data,
                 extraction_model, ai_extraction_success,
                 po_number, quantity, unit_price, total_amount, delivery_date,
                 vendor_name, customer_name, invoice_number, payment_terms,
                 description, tax_amount, contact_email, contact_phone) = record
                
                # Insert header record
                cursor.execute("""
                    INSERT INTO pdf_headers 
                    (filename, upload_date, file_size, page_count, status,
                     raw_text, metadata, structured_data, ai_extracted_data,
                     extraction_model, ai_extraction_success,
                     po_number, vendor_name, customer_name, invoice_number,
                     delivery_date, payment_terms, tax_amount, total_amount,
                     contact_email, contact_phone)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (filename, upload_date, file_size, page_count, status,
                      raw_text, metadata, structured_data, ai_extracted_data,
                      extraction_model, ai_extraction_success,
                      po_number, vendor_name, customer_name, invoice_number,
                      delivery_date, payment_terms, tax_amount, total_amount,
                      contact_email, contact_phone))
                
                # Get the new header ID
                cursor.execute("SELECT @@IDENTITY")
                header_id = cursor.fetchone()[0]
                migrated_headers += 1
                
                # Create line item if we have line-level data
                if quantity or unit_price or description:
                    cursor.execute("""
                        INSERT INTO pdf_line_items 
                        (pdf_header_id, line_number, description, quantity, unit_price, line_total)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (header_id, 1, description, quantity, unit_price, 
                          (quantity or 0) * (unit_price or 0) if quantity and unit_price else None))
                    migrated_line_items += 1
                
                print(f"✅ Migrated record {old_id}: {filename}")
                
            except Exception as e:
                print(f"❌ Failed to migrate record {old_id}: {e}")
        
        conn.commit()
        print(f"\n📊 Migration completed!")
        print(f"   • Headers migrated: {migrated_headers}")
        print(f"   • Line items created: {migrated_line_items}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")

def demonstrate_new_structure():
    """Show examples of how to use the new header/detail structure"""
    print("\n💡 How to Use the New Header/Detail Structure")
    print("=" * 60)
    
    print("\n📋 Example Queries:")
    
    queries = [
        ("Get all POs with line items", """
        SELECT h.po_number, h.vendor_name, h.total_amount,
               li.line_number, li.description, li.quantity, li.unit_price
        FROM pdf_headers h
        JOIN pdf_line_items li ON h.id = li.pdf_header_id
        WHERE h.po_number IS NOT NULL
        ORDER BY h.po_number, li.line_number
        """),
        
        ("Find POs over $1000 with item details", """
        SELECT h.po_number, h.vendor_name, h.total_amount,
               COUNT(li.id) as line_item_count,
               SUM(li.line_total) as calculated_total
        FROM pdf_headers h
        LEFT JOIN pdf_line_items li ON h.id = li.pdf_header_id
        WHERE h.total_amount > 1000
        GROUP BY h.id, h.po_number, h.vendor_name, h.total_amount
        """),
        
        ("Compare header total vs sum of line items", """
        SELECT h.po_number, 
               h.total_amount as header_total,
               SUM(li.line_total) as line_items_total,
               h.total_amount - SUM(li.line_total) as difference
        FROM pdf_headers h
        LEFT JOIN pdf_line_items li ON h.id = li.pdf_header_id
        GROUP BY h.id, h.po_number, h.total_amount
        HAVING ABS(h.total_amount - SUM(li.line_total)) > 0.01
        """),
        
        ("ETOSandbox comparison with line items", """
        SELECT p.po_number, p.vendor_name, p.total_amount as pdf_total,
               e.total_value as eto_total,
               li.description, li.quantity, li.unit_price
        FROM pdf_headers p
        LEFT JOIN ETOSandbox.dbo.purchase_orders e ON p.po_number = e.order_number
        LEFT JOIN pdf_line_items li ON p.id = li.pdf_header_id
        WHERE e.order_number IS NULL  -- Missing from ETOSandbox
        """)
    ]
    
    for title, query in queries:
        print(f"\n🔍 {title}:")
        print(f"```sql\n{query.strip()}\n```")

def main():
    """Run the complete header/detail schema upgrade"""
    print("🎯 PDF Header/Detail Schema Upgrade")
    print("=" * 60)
    print("Converting single table to normalized header (1) + line items (many)")
    print()
    
    # Create new schema
    create_header_detail_schema()
    
    # Migrate existing data
    migrate_existing_data()
    
    # Show usage examples
    demonstrate_new_structure()
    
    print("\n🚀 Next Steps:")
    print("1. Update AI extraction to populate both header and line item fields")
    print("2. Update database service to use new table structure")
    print("3. Update queries to use vw_pdf_complete view")
    print("4. Test with multi-line item PDFs")

if __name__ == "__main__":
    main() 