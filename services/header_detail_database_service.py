import pyodbc
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
import os
from typing import Dict, List, Any, Optional

load_dotenv()

logger = logging.getLogger(__name__)

class HeaderDetailDatabaseService:
    """Database service for header/detail table structure"""
    
    def __init__(self):
        # Use SQLite for PDF header/detail storage
        self.db_path = 'ETO_PDF.db'
        
        # Initialize comparison service
        try:
            from .po_comparison_service import POComparisonService
            self.comparison_service = POComparisonService()
            self.comparison_available = True
            logger.info("PO comparison service initialized")
        except Exception as e:
            logger.warning(f"PO comparison service not available: {e}")
            self.comparison_service = None
            self.comparison_available = False
        
        # Initialize database on startup
        self._initialize_database()
        
    def _get_connection(self):
        """Get database connection"""
        import sqlite3
        return sqlite3.connect(self.db_path)
    
    def _initialize_database(self):
        """Ensure header/detail tables exist"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Create pdf_headers table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pdf_headers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT NOT NULL,
                        file_size INTEGER,
                        page_count INTEGER,
                        status TEXT DEFAULT 'pending',
                        upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        raw_text TEXT,
                        metadata TEXT,
                        structured_data TEXT,
                        ai_extracted_data TEXT,
                        extraction_model TEXT,
                        ai_extraction_success BOOLEAN DEFAULT 0,
                        po_number TEXT,
                        vendor_name TEXT,
                        customer_name TEXT,
                        invoice_number TEXT,
                        invoice_date DATE,
                        delivery_date DATE,
                        payment_terms TEXT,
                        currency TEXT,
                        tax_rate DECIMAL(5,4),
                        tax_amount DECIMAL(15,2),
                        subtotal DECIMAL(15,2),
                        total_amount DECIMAL(15,2),
                        contact_email TEXT,
                        contact_phone TEXT,
                        shipping_address TEXT,
                        billing_address TEXT
                    )
                """)
                
                # Create pdf_line_items table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pdf_line_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pdf_header_id INTEGER NOT NULL,
                        line_number INTEGER,
                        item_code TEXT,
                        description TEXT,
                        quantity DECIMAL(15,4),
                        unit_of_measure TEXT,
                        unit_price DECIMAL(15,4),
                        line_total DECIMAL(15,2),
                        discount_percent DECIMAL(5,2),
                        discount_amount DECIMAL(15,2),
                        line_delivery_date DATE,
                        drawing_number TEXT,
                        revision TEXT,
                        material TEXT,
                        finish TEXT,
                        extraction_confidence DECIMAL(3,2),
                        extracted_from_text TEXT,
                        delivery_date_inherited BOOLEAN DEFAULT 0,
                        FOREIGN KEY (pdf_header_id) REFERENCES pdf_headers(id)
                    )
                """)
                
                conn.commit()
                logger.info("Header/detail database schema confirmed")
                    
        except Exception as e:
            logger.error(f"Error checking database schema: {e}")
            raise
    
    def save_header_detail_content(self, filename: str, pdf_data: dict, ai_data: dict = None) -> int:
        """
        Save PDF content to header/detail database structure
        
        Args:
            filename: Name of the uploaded file
            pdf_data: Dictionary containing PDF content and metadata
            ai_data: Optional dictionary containing AI-extracted header and line item data
        Returns:
            Header ID
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Prepare AI data
                ai_extracted_json = None
                extraction_model = None
                ai_success = False
                header_data = {}
                line_items = []
                
                if ai_data and ai_data.get('success'):
                    ai_extracted_json = json.dumps(ai_data.get('raw_ai_response', {}))
                    extraction_model = ai_data.get('extraction_model', 'unknown')
                    ai_success = True
                    header_data = ai_data.get('header_data', {})
                    line_items = ai_data.get('line_items', [])
                
                # Clean and prepare header fields
                header_fields = self._clean_header_data(header_data)
                
                # Insert header record
                cursor.execute("""
                    INSERT INTO pdf_headers 
                    (filename, file_size, page_count, status,
                     raw_text, metadata, structured_data, 
                     ai_extracted_data, extraction_model, ai_extraction_success,
                     po_number, vendor_name, customer_name, invoice_number, 
                     invoice_date, delivery_date, payment_terms, currency,
                     tax_rate, tax_amount, subtotal, total_amount,
                     contact_email, contact_phone, shipping_address, billing_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    filename,
                    pdf_data.get('file_size', 0),
                    pdf_data.get('page_count', 0),
                    'processed',
                    pdf_data.get('raw_text', ''),
                    json.dumps(pdf_data.get('metadata', {})),
                    json.dumps(pdf_data.get('structured_data', {})),
                    ai_extracted_json,
                    extraction_model,
                    ai_success,
                    header_fields.get('po_number'),
                    header_fields.get('vendor_name'),
                    header_fields.get('customer_name'),
                    header_fields.get('invoice_number'),
                    header_fields.get('invoice_date'),
                    header_fields.get('delivery_date'),
                    header_fields.get('payment_terms'),
                    header_fields.get('currency'),
                    header_fields.get('tax_rate'),
                    header_fields.get('tax_amount'),
                    header_fields.get('subtotal'),
                    header_fields.get('total_amount'),
                    header_fields.get('contact_email'),
                    header_fields.get('contact_phone'),
                    header_fields.get('shipping_address'),
                    header_fields.get('billing_address')
                ))
                
                # Get the header ID
                header_id = cursor.lastrowid
                
                # Insert line items
                line_item_count = 0
                for line_item in line_items:
                    line_fields = self._clean_line_item_data(line_item)
                    
                    cursor.execute("""
                        INSERT INTO pdf_line_items 
                        (pdf_header_id, line_number, item_code, description,
                         quantity, unit_of_measure, unit_price, line_total,
                         discount_percent, discount_amount, line_delivery_date,
                         drawing_number, revision, material, finish,
                         extraction_confidence, extracted_from_text)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        header_id,
                        line_fields.get('line_number'),
                        line_fields.get('item_code'),
                        line_fields.get('description'),
                        line_fields.get('quantity'),
                        line_fields.get('unit_of_measure'),
                        line_fields.get('unit_price'),
                        line_fields.get('line_total'),
                        line_fields.get('discount_percent'),
                        line_fields.get('discount_amount'),
                        line_fields.get('line_delivery_date'),
                        line_fields.get('drawing_number'),
                        line_fields.get('revision'),
                        line_fields.get('material'),
                        line_fields.get('finish'),
                        line_fields.get('extraction_confidence'),
                        line_fields.get('extracted_from_text')
                    ))
                    line_item_count += 1
                
                conn.commit()
                logger.info(f"PDF content saved - Header ID: {header_id}, Line items: {line_item_count}")
                return int(header_id)
                
        except Exception as e:
            logger.error(f"Error saving PDF content: {e}")
            raise
    
    def store_pdf_extraction(self, filename: str, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Store extracted PDF data in header/detail structure"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Store header data
            header_data = extraction_result.get('header_data', {})
            
            # Insert into pdf_headers table
            header_query = """
            INSERT INTO pdf_headers (
                filename, po_number, vendor_name, customer_name, invoice_number,
                invoice_date, delivery_date, payment_terms, currency, tax_rate,
                tax_amount, subtotal, total_amount, contact_email, contact_phone,
                shipping_address, billing_address, extraction_model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            header_params = (
                filename,
                header_data.get('po_number'),
                header_data.get('vendor_name'),
                header_data.get('customer_name'),
                header_data.get('invoice_number'),
                self._parse_date(header_data.get('invoice_date')),
                self._parse_date(header_data.get('delivery_date')),
                header_data.get('payment_terms'),
                header_data.get('currency'),
                self._safe_decimal(header_data.get('tax_rate')),
                self._safe_decimal(header_data.get('tax_amount')),
                self._safe_decimal(header_data.get('subtotal')),
                self._safe_decimal(header_data.get('total_amount')),
                header_data.get('contact_email'),
                header_data.get('contact_phone'),
                header_data.get('shipping_address'),
                header_data.get('billing_address'),
                extraction_result.get('extraction_model')
            )
            
            cursor.execute(header_query, header_params)
            header_id = cursor.lastrowid
            
            # Store line items
            line_items = extraction_result.get('line_items', [])
            if line_items:
                
                # Log delivery date processing info
                delivery_processing = extraction_result.get('raw_ai_response', {}).get('delivery_date_processing', {})
                if delivery_processing:
                    logger.info(f"Delivery date processing summary: {delivery_processing}")
                
                line_item_query = """
                INSERT INTO pdf_line_items (
                    pdf_header_id, line_number, item_code, description, quantity,
                    unit_of_measure, unit_price, line_total, discount_percent,
                    discount_amount, line_delivery_date, drawing_number, revision,
                    material, finish, delivery_date_inherited
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                for item in line_items:
                    line_params = (
                        header_id,
                        item.get('line_number'),
                        item.get('item_code'),
                        item.get('description'),
                        self._safe_decimal(item.get('quantity')),
                        item.get('unit_of_measure'),
                        self._safe_decimal(item.get('unit_price')),
                        self._safe_decimal(item.get('line_total')),
                        self._safe_decimal(item.get('discount_percent')),
                        self._safe_decimal(item.get('discount_amount')),
                        self._parse_date(item.get('line_delivery_date')),
                        item.get('drawing_number'),
                        item.get('revision'),
                        item.get('material'),
                        item.get('finish'),
                        item.get('delivery_date_inherited', False)  # Track if date was inherited from header
                    )
                    
                    cursor.execute(line_item_query, line_params)
                    
                    # Log delivery date inheritance for debugging
                    if item.get('delivery_date_inherited'):
                        logger.info(f"Line {item.get('line_number', 'unknown')}: Inherited delivery date {item.get('line_delivery_date')} from header")
                    elif item.get('line_delivery_date'):
                        logger.info(f"Line {item.get('line_number', 'unknown')}: Line-specific delivery date {item.get('line_delivery_date')}")
            
            conn.commit()
            
            return {
                'success': True,
                'header_id': header_id,
                'line_items_count': len(line_items),
                'message': f'Successfully stored PDF data with {len(line_items)} line items'
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database storage failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            if conn:
                conn.close()
    
    def _clean_header_data(self, header_data: dict) -> dict:
        """Clean and validate header data for database storage"""
        
        def clean_text(value, max_length=None):
            if not value or value == 'null' or str(value).strip() == '':
                return None
            text = str(value).strip()
            if max_length and len(text) > max_length:
                text = text[:max_length]
            return text
        
        def clean_numeric(value):
            if not value or value == 'null':
                return None
            try:
                # Remove currency symbols and commas
                clean_val = str(value).replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
                return float(clean_val)
            except:
                return None
        
        def clean_date(value):
            if not value or value == 'null':
                return None
            try:
                # Validate date format
                date_str = str(value).strip()
                if len(date_str) >= 8:  # Basic length check
                    # Try to parse to validate
                    datetime.strptime(date_str, '%Y-%m-%d')
                    return date_str
                return None
            except:
                return None
        
        return {
            'po_number': clean_text(header_data.get('po_number'), 100),
            'vendor_name': clean_text(header_data.get('vendor_name'), 255),
            'customer_name': clean_text(header_data.get('customer_name'), 255),
            'invoice_number': clean_text(header_data.get('invoice_number'), 100),
            'invoice_date': clean_date(header_data.get('invoice_date')),
            'delivery_date': clean_date(header_data.get('delivery_date')),
            'payment_terms': clean_text(header_data.get('payment_terms'), 100),
            'currency': clean_text(header_data.get('currency'), 10),
            'tax_rate': clean_numeric(header_data.get('tax_rate')),
            'tax_amount': clean_numeric(header_data.get('tax_amount')),
            'subtotal': clean_numeric(header_data.get('subtotal')),
            'total_amount': clean_numeric(header_data.get('total_amount')),
            'contact_email': clean_text(header_data.get('contact_email'), 255),
            'contact_phone': clean_text(header_data.get('contact_phone'), 50),
            'shipping_address': clean_text(header_data.get('shipping_address')),
            'billing_address': clean_text(header_data.get('billing_address'))
        }
    
    def _clean_line_item_data(self, line_item: dict) -> dict:
        """Clean and validate line item data for database storage"""
        
        def clean_text(value, max_length=None):
            if not value or value == 'null' or str(value).strip() == '':
                return None
            text = str(value).strip()
            if max_length and len(text) > max_length:
                text = text[:max_length]
            return text
        
        def clean_numeric(value):
            if not value or value == 'null':
                return None
            try:
                clean_val = str(value).replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
                return float(clean_val)
            except:
                return None
        
        def clean_date(value):
            if not value or value == 'null':
                return None
            try:
                date_str = str(value).strip()
                if len(date_str) >= 8:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    return date_str
                return None
            except:
                return None
        
        return {
            'line_number': int(line_item.get('line_number', 0)) if line_item.get('line_number') else None,
            'item_code': clean_text(line_item.get('item_code'), 100),
            'description': clean_text(line_item.get('description'), 500),
            'quantity': clean_numeric(line_item.get('quantity')),
            'unit_of_measure': clean_text(line_item.get('unit_of_measure'), 20),
            'unit_price': clean_numeric(line_item.get('unit_price')),
            'line_total': clean_numeric(line_item.get('line_total')),
            'discount_percent': clean_numeric(line_item.get('discount_percent')),
            'discount_amount': clean_numeric(line_item.get('discount_amount')),
            'line_delivery_date': clean_date(line_item.get('line_delivery_date')),
            'drawing_number': clean_text(line_item.get('drawing_number'), 100),
            'revision': clean_text(line_item.get('revision'), 20),
            'material': clean_text(line_item.get('material'), 100),
            'finish': clean_text(line_item.get('finish'), 100),
            'extraction_confidence': clean_numeric(line_item.get('extraction_confidence')),
            'extracted_from_text': clean_text(line_item.get('extracted_from_text'), 1000)
        }
    
    def get_header_with_line_items(self, header_id: int) -> Dict[str, Any]:
        """Get complete header record with all line items"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get header
                cursor.execute("""
                    SELECT * FROM pdf_headers WHERE id = ?
                """, (header_id,))
                
                header_row = cursor.fetchone()
                if not header_row:
                    return None
                
                # Convert to dict
                columns = [description[0] for description in cursor.description]
                header_data = dict(zip(columns, header_row))
                
                # Get line items
                cursor.execute("""
                    SELECT * FROM pdf_line_items WHERE pdf_header_id = ?
                    ORDER BY line_number
                """, (header_id,))
                
                line_items = []
                for row in cursor.fetchall():
                    columns = [description[0] for description in cursor.description]
                    line_items.append(dict(zip(columns, row)))
                
                header_data['line_items'] = line_items
                return header_data
                
        except Exception as e:
            logger.error(f"Error retrieving header with line items: {e}")
            return None
    
    def get_header_with_line_items_and_comparison(self, header_id: int) -> Dict[str, Any]:
        """
        Get complete header record with all line items AND ETOSandbox comparison data
        
        Args:
            header_id: PDF header ID
            
        Returns:
            Dictionary containing header data, line items, and comparison results
        """
        try:
            # First get the basic header and line items
            document = self.get_header_with_line_items(header_id)
            if not document:
                return None
            
            # Initialize comparison data
            comparison_data = {
                'comparison_available': self.comparison_available,
                'comparison_results': None,
                'comparison_summary': None,
                'po_found_in_eto': False
            }
            
            # If comparison service is available and we have a PO number, get comparison data
            if self.comparison_available and self.comparison_service:
                po_number = document.get('po_number')
                line_items = document.get('line_items', [])
                
                if po_number and line_items:
                    logger.info(f"Getting comparison data for PO {po_number} with {len(line_items)} line items")
                    
                    # Get comparison results from ETOSandbox
                    comparison_results = self.comparison_service.get_po_comparison_data(po_number, line_items)
                    
                    if comparison_results['success']:
                        comparison_data['comparison_results'] = comparison_results
                        comparison_data['po_found_in_eto'] = comparison_results.get('po_found', False)
                        
                        # Generate comparison summary
                        if comparison_results.get('comparisons'):
                            comparison_data['comparison_summary'] = self.comparison_service.get_comparison_summary(
                                comparison_results['comparisons']
                            )
                            
                            logger.info(f"Comparison completed: {comparison_data['comparison_summary']}")
                        else:
                            logger.warning(f"No comparison data found for PO {po_number}")
                    else:
                        logger.error(f"Comparison failed: {comparison_results.get('error')}")
                        comparison_data['comparison_error'] = comparison_results.get('error')
                else:
                    logger.info(f"Skipping comparison - PO number: {po_number}, Line items: {len(line_items)}")
            else:
                logger.info("Comparison service not available")
            
            # Merge comparison data into document
            document['comparison'] = comparison_data
            
            return document
                
        except Exception as e:
            logger.error(f"Error retrieving header with line items and comparison: {e}")
            # Return document without comparison data if comparison fails
            try:
                document = self.get_header_with_line_items(header_id)
                if document:
                    document['comparison'] = {
                        'comparison_available': False,
                        'comparison_error': str(e),
                        'comparison_results': None,
                        'comparison_summary': None,
                        'po_found_in_eto': False
                    }
                return document
            except:
                return None
    
    def get_all_headers_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all headers with line item counts"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT h.id, h.filename, h.upload_date, h.po_number, 
                           h.vendor_name, h.total_amount, h.ai_extraction_success,
                           COUNT(li.id) as line_item_count,
                           SUM(li.line_total) as calculated_total
                    FROM pdf_headers h
                    LEFT JOIN pdf_line_items li ON h.id = li.pdf_header_id
                    GROUP BY h.id, h.filename, h.upload_date, h.po_number, 
                             h.vendor_name, h.total_amount, h.ai_extraction_success
                    ORDER BY h.upload_date DESC
                """)
                
                results = []
                for row in cursor.fetchall():
                    columns = [description[0] for description in cursor.description]
                    results.append(dict(zip(columns, row)))
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting headers summary: {e}")
            return []

    def get_headers_by_date_with_comparison(self, upload_date: str) -> List[Dict[str, Any]]:
        """
        Get all headers uploaded on a specific date with full comparison data
        
        Args:
            upload_date: Date string in YYYY-MM-DD format
            
        Returns:
            List of dictionaries containing header data, line items, and comparison results
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Query headers by date - handle timestamp format
                cursor.execute("""
                    SELECT * FROM pdf_headers 
                    WHERE date(upload_date) = ? OR upload_date LIKE ?
                    ORDER BY upload_date DESC
                """, (upload_date, f"{upload_date}%"))
                
                headers = []
                for row in cursor.fetchall():
                    columns = [description[0] for description in cursor.description]
                    header_data = dict(zip(columns, row))
                    
                    # Get line items for this header using a new cursor to avoid conflicts
                    cursor2 = conn.cursor()
                    cursor2.execute("""
                        SELECT * FROM pdf_line_items 
                        WHERE pdf_header_id = ?
                        ORDER BY line_number
                    """, (header_data['id'],))
                    
                    line_items = []
                    for line_row in cursor2.fetchall():
                        line_columns = [description[0] for description in cursor2.description]
                        line_items.append(dict(zip(line_columns, line_row)))
                    
                    header_data['line_items'] = line_items
                    
                    # Get comparison data if available - use inline processing to avoid nested db calls
                    if self.comparison_available and self.comparison_service and header_data.get('po_number') and line_items:
                        try:
                            po_number = header_data['po_number']
                            logger.info(f"Getting comparison data for PO {po_number} with {len(line_items)} line items")
                            
                            # Get comparison results from ETOSandbox
                            comparison_results = self.comparison_service.get_po_comparison_data(po_number, line_items)
                            
                            if comparison_results and comparison_results.get('success'):
                                comparison_data = {
                                    'comparison_available': True,
                                    'comparison_results': comparison_results,
                                    'comparison_summary': self._build_comparison_summary(comparison_results),
                                    'po_found_in_eto': comparison_results.get('po_found', False)
                                }
                                logger.info(f"Comparison completed for PO {po_number}")
                            else:
                                comparison_data = {
                                    'comparison_available': True,
                                    'comparison_results': None,
                                    'comparison_summary': None,
                                    'po_found_in_eto': False,
                                    'comparison_error': comparison_results.get('error') if comparison_results else 'No results'
                                }
                                logger.warning(f"Comparison failed for PO {po_number}: {comparison_results.get('error') if comparison_results else 'No results'}")
                            
                            header_data['comparison'] = comparison_data
                            
                        except Exception as comp_error:
                            logger.error(f"Comparison error for header {header_data['id']}: {comp_error}")
                            header_data['comparison'] = {
                                'comparison_available': False,
                                'comparison_error': str(comp_error),
                                'comparison_results': None,
                                'comparison_summary': None,
                                'po_found_in_eto': False
                            }
                    else:
                        header_data['comparison'] = None
                        if not header_data.get('po_number'):
                            logger.info(f"Skipping comparison for header {header_data['id']} - no PO number")
                        elif not line_items:
                            logger.info(f"Skipping comparison for header {header_data['id']} - no line items")
                    
                    headers.append(header_data)
                
                logger.info(f"Found {len(headers)} PDFs uploaded on {upload_date}")
                return headers
                
        except Exception as e:
            logger.error(f"Error getting headers by date: {e}")
            return []
    
    def _get_full_comparison_data(self, header_id: int) -> Dict[str, Any]:
        """
        Get full comparison data for a specific header
        
        Args:
            header_id: PDF header ID
            
        Returns:
            Dictionary containing comparison results
        """
        try:
            # Get the header data to extract PO number and line items
            document = self.get_header_with_line_items(header_id)
            if not document or not document.get('po_number'):
                return None
            
            po_number = document['po_number']
            pdf_line_items = document.get('line_items', [])
            
            if not pdf_line_items:
                return None
            
            # Get comparison using the comparison service
            if not self.comparison_service:
                return None
            
            comparison_result = self.comparison_service.get_po_comparison_data(po_number, pdf_line_items)
            
            if comparison_result and comparison_result.get('success'):
                return {
                    'comparison_available': True,
                    'comparison_results': comparison_result,
                    'comparison_summary': self._build_comparison_summary(comparison_result),
                    'po_found_in_eto': comparison_result.get('po_found', False)
                }
            else:
                return {
                    'comparison_available': False,
                    'comparison_results': None,
                    'comparison_summary': None,
                    'po_found_in_eto': False
                }
                
        except Exception as e:
            logger.error(f"Error getting comparison data for header {header_id}: {e}")
            return None 

    def _build_comparison_summary(self, comparison_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a comparison summary from comparison results
        
        Args:
            comparison_result: Dictionary containing comparison data
            
        Returns:
            Dictionary containing summary statistics
        """
        try:
            if not comparison_result or not comparison_result.get('comparisons'):
                return {
                    'total_lines': 0,
                    'perfect_matches': 0,
                    'partial_matches': 0,
                    'no_matches': 0,
                    'overall_score': 0.0,
                    'accuracy_percentage': 0.0
                }
            
            comparisons = comparison_result['comparisons']
            total_lines = len(comparisons)
            perfect_matches = 0
            partial_matches = 0
            no_matches = 0
            total_score = 0.0
            
            for comparison in comparisons:
                match_score = comparison.get('match_score', 0.0)
                total_score += match_score
                
                if match_score >= 1.0:
                    perfect_matches += 1
                elif match_score > 0.0:
                    partial_matches += 1
                else:
                    no_matches += 1
            
            overall_score = total_score / total_lines if total_lines > 0 else 0.0
            accuracy_percentage = (perfect_matches / total_lines * 100) if total_lines > 0 else 0.0
            
            return {
                'total_lines': total_lines,
                'perfect_matches': perfect_matches,
                'partial_matches': partial_matches,
                'no_matches': no_matches,
                'overall_score': overall_score,
                'accuracy_percentage': accuracy_percentage
            }
            
        except Exception as e:
            logger.error(f"Error building comparison summary: {e}")
            return {
                'total_lines': 0,
                'perfect_matches': 0,
                'partial_matches': 0,
                'no_matches': 0,
                'overall_score': 0.0,
                'accuracy_percentage': 0.0
            }

    def _safe_decimal(self, value):
        """Safely convert value to decimal, return None if invalid"""
        if value is None or value == 'null' or str(value).strip() == '':
            return None
        try:
            # Clean currency symbols and commas
            clean_val = str(value).replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
            return float(clean_val)
        except:
            return None
    
    def _parse_date(self, date_value):
        """Parse date string to proper format for database"""
        if not date_value or date_value == 'null':
            return None
        try:
            date_str = str(date_value).strip()
            if len(date_str) >= 8:  # Basic length check
                # Try to parse to validate format
                datetime.strptime(date_str, '%Y-%m-%d')
                return date_str
            return None
        except:
            return None 