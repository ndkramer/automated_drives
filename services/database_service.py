"""
Database Service
Handles connections and operations for the ETO_PDF database.
"""

import os
import logging
import pyodbc
import json

logger = logging.getLogger(__name__)

class DatabaseService:
    """Service for managing database connections and operations"""
    
    def __init__(self):
        self.config = {
            'server': os.environ.get('DB_SERVER', 'localhost'),
            'database': os.environ.get('DB_DATABASE', 'ETO_PDF'),
            'username': os.environ.get('DB_USERNAME', 'sa'),
            'password': os.environ.get('DB_PASSWORD', ''),
            'driver': os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        }
        self._initialize_database()

    def _get_connection(self):
        """Get database connection"""
        return pyodbc.connect(
            f"DRIVER={{{self.config['driver']}}};"
            f"SERVER={self.config['server']};"
            f"DATABASE={self.config['database']};"
            f"UID={self.config['username']};"
            f"PWD={self.config['password']};"
        )

    def _initialize_database(self):
        """Create pdf_uploads table if it doesn't exist"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='pdf_uploads' AND xtype='U')
                    CREATE TABLE pdf_uploads (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        filename NVARCHAR(255) NOT NULL,
                        upload_date DATETIME DEFAULT GETDATE(),
                        file_size BIGINT,
                        page_count INT,
                        status NVARCHAR(50) DEFAULT 'processed',
                        metadata NVARCHAR(MAX),
                        raw_text NVARCHAR(MAX),
                        structured_data NVARCHAR(MAX),
                        ai_extracted_data NVARCHAR(MAX),
                        extraction_model NVARCHAR(100),
                        ai_extraction_success BIT DEFAULT 0
                    )
                """)
                conn.commit()
                logger.info("pdf_uploads table ensured in ETO_PDF database")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def save_pdf_content(self, filename: str, pdf_data: dict, ai_data: dict = None) -> int:
        """
        Save PDF content to ETO_PDF database
        Args:
            filename: Name of the uploaded file
            pdf_data: Dictionary containing PDF content and metadata
            ai_data: Optional dictionary containing AI-extracted data
        Returns:
            Upload ID
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Prepare AI data for storage
                ai_extracted_json = None
                extraction_model = None
                ai_success = False
                
                # Extract individual business fields from AI data
                business_fields = {}
                
                if ai_data:
                    ai_extracted_json = json.dumps(ai_data.get('ai_extracted_data', {}))
                    extraction_model = ai_data.get('extraction_model', 'unknown')
                    ai_success = ai_data.get('success', False)
                    
                    # Extract business fields to individual columns
                    if ai_success and 'ai_extracted_data' in ai_data:
                        ai_fields = ai_data['ai_extracted_data']
                        business_fields = self._extract_business_fields(ai_fields)
                
                cursor.execute("""
                    INSERT INTO pdf_uploads 
                    (filename, file_size, page_count, metadata, raw_text, structured_data, 
                     ai_extracted_data, extraction_model, ai_extraction_success,
                     po_number, quantity, unit_price, total_amount, delivery_date, 
                     vendor_name, customer_name, invoice_number, payment_terms, 
                     description, tax_amount, contact_email, contact_phone)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    filename,
                    pdf_data.get('file_size', 0),
                    pdf_data.get('page_count', 0),
                    json.dumps(pdf_data.get('metadata', {})),
                    pdf_data.get('raw_text', ''),
                    json.dumps(pdf_data.get('structured_data', {})),
                    ai_extracted_json,
                    extraction_model,
                    ai_success,
                    business_fields.get('po_number'),
                    business_fields.get('quantity'),
                    business_fields.get('unit_price'),
                    business_fields.get('total_amount'),
                    business_fields.get('delivery_date'),
                    business_fields.get('vendor_name'),
                    business_fields.get('customer_name'),
                    business_fields.get('invoice_number'),
                    business_fields.get('payment_terms'),
                    business_fields.get('description'),
                    business_fields.get('tax_amount'),
                    business_fields.get('contact_email'),
                    business_fields.get('contact_phone')
                ))
                # Get the last inserted ID
                cursor.execute("SELECT @@IDENTITY")
                upload_id = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"PDF content saved with upload ID: {upload_id}")
                return int(upload_id)
        except Exception as e:
            logger.error(f"Error saving PDF content: {e}")
            raise
    
    def _extract_business_fields(self, ai_fields: dict) -> dict:
        """
        Extract and clean business fields from AI data for individual column storage
        
        Args:
            ai_fields: AI extracted data dictionary
            
        Returns:
            Dictionary with cleaned business field values
        """
        def clean_numeric(value):
            """Clean numeric values for database storage"""
            if not value or value == 'null' or value is None:
                return None
            # Remove currency symbols and commas
            clean_val = str(value).replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
            try:
                return float(clean_val)
            except:
                return None
        
        def clean_date(value):
            """Clean date values for database storage"""
            if not value or value == 'null' or value is None:
                return None
            # Basic date format validation - could be enhanced with proper date parsing
            date_str = str(value).strip()
            return date_str if len(date_str) >= 8 else None
        
        def clean_text(value, max_length=None):
            """Clean text values for database storage"""
            if not value or value == 'null' or value is None:
                return None
            text = str(value).strip()
            if max_length and len(text) > max_length:
                text = text[:max_length]
            return text if text else None
        
        # Extract and clean fields
        business_fields = {
            'po_number': clean_text(ai_fields.get('po_number'), 100),
            'quantity': clean_numeric(ai_fields.get('qty') or ai_fields.get('quantity')),
            'unit_price': clean_numeric(ai_fields.get('unit_price')),
            'total_amount': clean_numeric(ai_fields.get('total_amount') or ai_fields.get('price')),
            'delivery_date': clean_date(ai_fields.get('delivery_date')),
            'vendor_name': clean_text(ai_fields.get('vendor_name'), 255),
            'customer_name': clean_text(ai_fields.get('customer_name'), 255),
            'invoice_number': clean_text(ai_fields.get('invoice_number'), 100),
            'payment_terms': clean_text(ai_fields.get('payment_terms'), 100),
            'description': clean_text(ai_fields.get('description'), 500),
            'tax_amount': clean_numeric(ai_fields.get('tax_amount'))
        }
        
        # Extract contact information
        contact_info = ai_fields.get('contact_info', {})
        if isinstance(contact_info, dict):
            business_fields['contact_email'] = clean_text(contact_info.get('email'), 255)
            business_fields['contact_phone'] = clean_text(contact_info.get('phone'), 50)
        
        return business_fields 