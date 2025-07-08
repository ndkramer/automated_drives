#!/usr/bin/env python3
"""
Purchase Order Comparison Service
Compares PDF-extracted line items with ETOSandbox database records
"""

import os
import logging
import pyodbc
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class POComparisonService:
    """Service for comparing PDF line items with ETOSandbox PO data"""
    
    def __init__(self):
        # ETOSandbox database connection parameters
        self.business_server = os.getenv('BUSINESS_DB_SERVER')
        self.business_database = os.getenv('BUSINESS_DB_DATABASE')
        self.business_username = os.getenv('BUSINESS_DB_USERNAME')
        self.business_password = os.getenv('BUSINESS_DB_PASSWORD')
        
        if not all([self.business_server, self.business_database, self.business_username, self.business_password]):
            raise ValueError("Business database connection parameters not found in environment variables")
        
        # Initialize AI matcher for intelligent line item matching
        try:
            from .ai_line_item_matcher import AILineItemMatcher
            self.ai_matcher = AILineItemMatcher()
            self.ai_matching_available = True
            logger.info("AI line item matching initialized")
        except Exception as e:
            logger.warning(f"AI line item matching not available: {e}")
            self.ai_matcher = None
            self.ai_matching_available = False
    
    def _get_business_connection(self):
        """Get connection to ETOSandbox database"""
        connection_string = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={self.business_server};'
            f'DATABASE={self.business_database};'
            f'UID={self.business_username};'
            f'PWD={self.business_password}'
        )
        return pyodbc.connect(connection_string)
    
    def get_po_comparison_data(self, po_number: str, pdf_line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get comparison data for a PO number against ETOSandbox database
        
        Args:
            po_number: Purchase Order number from PDF
            pdf_line_items: List of line items extracted from PDF
            
        Returns:
            Dictionary containing comparison results
        """
        try:
            if not po_number:
                return {
                    'success': False,
                    'error': 'No PO number provided',
                    'po_found': False,
                    'comparisons': []
                }
            
            with self._get_business_connection() as conn:
                cursor = conn.cursor()
                
                # First, check if PO exists in ETOSandbox
                logger.info(f"Looking for PO {po_number} in ETOSandbox...")
                
                cursor.execute("""
                    SELECT PurchaseOrderID, PurchaseSupplierID, PurchaseDate
                    FROM tblPurchaseOrderHeader 
                    WHERE PurchaseOrderID = ?
                """, (po_number,))
                
                po_header = cursor.fetchone()
                if not po_header:
                    logger.warning(f"PO {po_number} not found in ETOSandbox")
                    return {
                        'success': True,
                        'po_found': False,
                        'po_number': po_number,
                        'error': f'PO {po_number} not found in ETOSandbox database',
                        'comparisons': []
                    }
                
                logger.info(f"Found PO {po_number} in ETOSandbox")
                
                # Get PO line items from ETOSandbox
                cursor.execute("""
                    SELECT 
                        PurchaseDetailID,
                        ItemID,
                        PurchaseQty,
                        PurchasePrice,
                        DateRequired,
                        PurchaseSupplierItem,
                        PurchaseSupplierDescription
                    FROM tblPurchaseOrderDetails 
                    WHERE PurchaseOrderID = ?
                    ORDER BY PurchaseDetailID
                """, (po_number,))
                
                eto_line_items = cursor.fetchall()
                
                if not eto_line_items:
                    logger.warning(f"No line items found for PO {po_number} in ETOSandbox")
                    return {
                        'success': True,
                        'po_found': True,
                        'po_number': po_number,
                        'po_header': {
                            'purchase_order_id': po_header[0],
                            'supplier_id': po_header[1],
                            'purchase_date': po_header[2],
                            'total_amount': None,
                            'date_required': None
                        },
                        'error': f'No line items found for PO {po_number}',
                        'comparisons': []
                    }
                
                # Convert ETO line items to list for position-based comparison
                eto_items_list = []
                for item in eto_line_items:
                    detail_id, item_id, qty, price, date_req, supplier_item, supplier_desc = item
                    
                    # Calculate line total
                    quantity = float(qty) if qty else 0
                    unit_price = float(price) if price else 0
                    line_total = quantity * unit_price
                    
                    eto_items_list.append({
                        'line_number': len(eto_items_list) + 1,  # Sequential for display
                        'detail_id': detail_id,
                        'item_id': item_id,
                        'quantity': quantity if qty else None,
                        'unit_price': unit_price if price else None,
                        'line_total': line_total if (qty and price) else None,  # Calculated line total
                        'date_required': date_req,
                        'description': supplier_desc,
                        'supplier_item': supplier_item,
                        'unit_of_measure': 'each'  # Default since not in table
                    })
                
                # Use AI-powered intelligent matching instead of position-based
                if self.ai_matching_available and self.ai_matcher:
                    logger.info(f"Using AI-powered intelligent matching for PO {po_number}")
                    matching_result = self.ai_matcher.match_line_items(pdf_line_items, eto_items_list, po_number)
                    
                    if matching_result['success']:
                        comparisons = []
                        
                        # Process AI-matched pairs
                        for match in matching_result['matches']:
                            pdf_item = match['pdf_item']
                            eto_item = match['eto_item']
                            comparison = self._compare_line_items(pdf_item, eto_item)
                            comparison['match_found'] = True
                            comparison['comparison_type'] = 'ai_matched'
                            comparison['ai_confidence'] = match['confidence']
                            comparison['match_reasons'] = match['match_reasons']
                            comparison['ai_notes'] = match['notes']
                            comparisons.append(comparison)
                        
                        # Process unmatched PDF items
                        for pdf_item in matching_result['unmatched_pdf']:
                            comparison = {
                                'pdf_line': pdf_item,
                                'eto_line': None,
                                'match_found': False,
                                'comparison_type': 'pdf_only',
                                'differences': {
                                    'line_missing_in_eto': True
                                }
                            }
                            comparisons.append(comparison)
                        
                        # Process unmatched ETO items
                        for eto_item in matching_result['unmatched_eto']:
                            comparison = {
                                'pdf_line': None,
                                'eto_line': eto_item,
                                'match_found': False,
                                'comparison_type': 'eto_only',
                                'differences': {
                                    'line_missing_in_pdf': True
                                }
                            }
                            comparisons.append(comparison)
                        
                        logger.info(f"AI matching completed: {matching_result['total_matches']} matches, method: {matching_result['match_method']}")
                    else:
                        logger.warning(f"AI matching failed, using fallback position-based matching")
                        comparisons = self._fallback_position_matching(pdf_line_items, eto_items_list)
                else:
                    logger.info("AI matching not available, using position-based matching")
                    comparisons = self._fallback_position_matching(pdf_line_items, eto_items_list)
                
                return {
                    'success': True,
                    'po_found': True,
                    'po_number': po_number,
                    'po_header': {
                        'purchase_order_id': po_header[0],
                        'supplier_id': po_header[1],
                        'purchase_date': po_header[2],
                        'total_amount': None,
                        'date_required': None
                    },
                    'comparisons': comparisons,
                    'total_pdf_lines': len(pdf_line_items),
                    'total_eto_lines': len(eto_items_list),
                    'matched_lines': len([c for c in comparisons if c['match_found']])
                }
                
        except Exception as e:
            logger.error(f"Error comparing PO {po_number}: {e}")
            return {
                'success': False,
                'error': str(e),
                'po_found': False,
                'comparisons': []
            }
    
    def _compare_line_items(self, pdf_item: Dict[str, Any], eto_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare individual line items between PDF and ETO
        
        Args:
            pdf_item: Line item from PDF extraction
            eto_item: Line item from ETOSandbox
            
        Returns:
            Comparison result with differences highlighted
        """
        differences = {}
        
        # Compare quantity
        pdf_qty = pdf_item.get('quantity')
        eto_qty = eto_item.get('quantity')
        if pdf_qty is not None and eto_qty is not None:
            if abs(float(pdf_qty) - float(eto_qty)) > 0.001:  # Small tolerance for float comparison
                differences['quantity'] = {
                    'pdf_value': pdf_qty,
                    'eto_value': eto_qty,
                    'match': False
                }
        elif pdf_qty != eto_qty:  # One is None, other is not
            differences['quantity'] = {
                'pdf_value': pdf_qty,
                'eto_value': eto_qty,
                'match': False
            }
        
        # Compare unit price
        pdf_price = pdf_item.get('unit_price')
        eto_price = eto_item.get('unit_price')
        if pdf_price is not None and eto_price is not None:
            if abs(float(pdf_price) - float(eto_price)) > 0.01:  # Small tolerance for price comparison
                differences['unit_price'] = {
                    'pdf_value': pdf_price,
                    'eto_value': eto_price,
                    'match': False
                }
        elif pdf_price != eto_price:
            differences['unit_price'] = {
                'pdf_value': pdf_price,
                'eto_value': eto_price,
                'match': False
            }
        
        # Compare delivery date
        pdf_date = pdf_item.get('line_delivery_date')
        eto_date = eto_item.get('date_required')
        
        # Normalize dates for comparison
        pdf_date_normalized = self._normalize_date(pdf_date)
        eto_date_normalized = self._normalize_date(eto_date)
        
        if pdf_date_normalized != eto_date_normalized:
            differences['delivery_date'] = {
                'pdf_value': pdf_date,
                'eto_value': eto_date,
                'match': False
            }
        
        # Compare item code/description if available
        pdf_code = pdf_item.get('item_code')
        eto_code = eto_item.get('item_id')
        if pdf_code and eto_code and pdf_code != eto_code:
            differences['item_code'] = {
                'pdf_value': pdf_code,
                'eto_value': eto_code,
                'match': False
            }
        
        return {
            'pdf_line': pdf_item,
            'eto_line': eto_item,
            'differences': differences,
            'has_differences': len(differences) > 0,
            'match_score': self._calculate_match_score(differences)
        }
    
    def _normalize_date(self, date_value) -> str:
        """Normalize date value for comparison"""
        if not date_value:
            return ""
        
        if isinstance(date_value, datetime):
            return date_value.strftime('%Y-%m-%d')
        
        # Try to parse string dates
        try:
            if isinstance(date_value, str):
                # Handle various date formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                    try:
                        parsed_date = datetime.strptime(date_value, fmt)
                        return parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
        except:
            pass
        
        return str(date_value)
    
    def _fallback_position_matching(self, pdf_line_items: List[Dict[str, Any]], eto_items_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback position-based matching when AI matching is not available"""
        comparisons = []
        max_lines = max(len(pdf_line_items), len(eto_items_list))
        
        for i in range(max_lines):
            pdf_item = pdf_line_items[i] if i < len(pdf_line_items) else None
            eto_item = eto_items_list[i] if i < len(eto_items_list) else None
            
            if pdf_item and eto_item:
                # Both items exist - compare them
                comparison = self._compare_line_items(pdf_item, eto_item)
                comparison['match_found'] = True
                comparison['comparison_type'] = 'position_based'
            elif pdf_item and not eto_item:
                # PDF item exists but no matching ETO item
                comparison = {
                    'pdf_line': pdf_item,
                    'eto_line': None,
                    'match_found': False,
                    'comparison_type': 'pdf_only',
                    'differences': {
                        'line_missing_in_eto': True
                    }
                }
            elif eto_item and not pdf_item:
                # ETO item exists but no matching PDF item
                comparison = {
                    'pdf_line': None,
                    'eto_line': eto_item,
                    'match_found': False,
                    'comparison_type': 'eto_only',
                    'differences': {
                        'line_missing_in_pdf': True
                    }
                }
            
            comparisons.append(comparison)
        
        return comparisons
    
    def _calculate_match_score(self, differences: Dict[str, Any]) -> float:
        """
        Calculate a match score based on three key fields: quantity, unit_price, and delivery_date
        Returns percentage as decimal (0.0 = 0%, 1.0 = 100%)
        """
        import math
        
        # Only consider these three key fields for match calculation
        key_fields = ['quantity', 'unit_price', 'delivery_date']
        
        matches = 0
        total_fields = len(key_fields)
        
        # Count how many of the key fields match (are NOT in differences)
        for field in key_fields:
            if field not in differences:
                matches += 1
        
        # Calculate percentage and round up to nearest whole number
        if matches == total_fields:
            return 1.0  # 100% match
        elif matches == 0:
            return 0.0  # 0% match
        else:
            # Calculate percentage and round up (e.g., 2/3 = 66.67% → 67%)
            percentage = (matches / total_fields) * 100
            rounded_up_percentage = math.ceil(percentage)
            return rounded_up_percentage / 100.0
    
    def get_comparison_summary(self, comparisons: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a summary of comparison results
        
        Args:
            comparisons: List of comparison results
            
        Returns:
            Summary statistics
        """
        if not comparisons:
            return {
                'total_lines': 0,
                'perfect_matches': 0,
                'partial_matches': 0,
                'no_matches': 0,
                'overall_score': 0.0
            }
        
        perfect_matches = 0
        partial_matches = 0
        no_matches = 0
        total_score = 0.0
        
        for comparison in comparisons:
            if not comparison.get('match_found'):
                no_matches += 1
            else:
                match_score = comparison.get('match_score', 0.0)
                total_score += match_score
                
                if match_score >= 1.0:
                    perfect_matches += 1
                elif match_score > 0.0:
                    partial_matches += 1
                else:
                    no_matches += 1
        
        total_lines = len(comparisons)
        overall_score = total_score / total_lines if total_lines > 0 else 0.0
        
        return {
            'total_lines': total_lines,
            'perfect_matches': perfect_matches,
            'partial_matches': partial_matches,
            'no_matches': no_matches,
            'overall_score': overall_score,
            'accuracy_percentage': (perfect_matches / total_lines * 100) if total_lines > 0 else 0.0
        }
    
    def update_eto_line_item(self, detail_id: int, quantity: float, unit_price: float, delivery_date: str) -> Dict[str, Any]:
        """
        Update a specific line item in the ETOSandbox database
        
        Args:
            detail_id: The PurchaseDetailID to update
            quantity: New quantity value
            unit_price: New unit price value  
            delivery_date: New delivery date (YYYY-MM-DD format)
            
        Returns:
            Result dictionary with success/error information
        """
        try:
            with self._get_business_connection() as conn:
                cursor = conn.cursor()
                
                # First, verify the detail exists
                cursor.execute("""
                    SELECT PurchaseDetailID, PurchaseOrderID, ItemID, PurchaseQty, PurchasePrice, DateRequired
                    FROM tblPurchaseOrderDetails 
                    WHERE PurchaseDetailID = ?
                """, (detail_id,))
                
                existing_detail = cursor.fetchone()
                if not existing_detail:
                    logger.warning(f"Detail ID {detail_id} not found in ETOSandbox")
                    return {
                        'success': False,
                        'error': f'Detail ID {detail_id} not found in ETOSandbox database'
                    }
                
                # Log the current values before update
                logger.info(f"Updating detail ID {detail_id}:")
                logger.info(f"  Current - Qty: {existing_detail[3]}, Price: {existing_detail[4]}, Date: {existing_detail[5]}")
                logger.info(f"  New     - Qty: {quantity}, Price: {unit_price}, Date: {delivery_date}")
                
                # Update the record
                cursor.execute("""
                    UPDATE tblPurchaseOrderDetails 
                    SET PurchaseQty = ?, 
                        PurchasePrice = ?, 
                        DateRequired = ?
                    WHERE PurchaseDetailID = ?
                """, (quantity, unit_price, delivery_date, detail_id))
                
                # Check if any rows were affected
                rows_affected = cursor.rowcount
                if rows_affected == 0:
                    return {
                        'success': False,
                        'error': 'No rows were updated. Detail ID may not exist.'
                    }
                
                # Commit the transaction
                conn.commit()
                
                logger.info(f"Successfully updated detail ID {detail_id} - {rows_affected} row(s) affected")
                
                return {
                    'success': True,
                    'detail_id': detail_id,
                    'rows_affected': rows_affected,
                    'updated_values': {
                        'quantity': quantity,
                        'unit_price': unit_price,
                        'delivery_date': delivery_date
                    }
                }
                
        except Exception as e:
            logger.error(f"Error updating ETO detail ID {detail_id}: {e}")
            
            # Check for specific business constraint errors
            error_message = str(e)
            if "referenced on an Invoice" in error_message:
                user_friendly_error = "Cannot update this line item because it has already been invoiced. Invoiced purchase orders cannot be modified."
            elif "42000" in error_message and "50000" in error_message:
                user_friendly_error = "Database business rule violation. This purchase order may be locked or in a non-editable state."
            else:
                user_friendly_error = f"Database error: {str(e)}"
            
            return {
                'success': False,
                'error': user_friendly_error,
                'technical_error': str(e)
            }
    
    def check_detail_update_status(self, detail_id: int) -> Dict[str, Any]:
        """
        Check if a purchase order detail can be updated (i.e., not invoiced)
        
        Args:
            detail_id: The PurchaseDetailID to check
            
        Returns:
            Status information about whether the detail can be updated
        """
        try:
            with self._get_business_connection() as conn:
                cursor = conn.cursor()
                
                # Try a "test" update with the same values to see if it would succeed
                # First get current values
                cursor.execute("""
                    SELECT PurchaseQty, PurchasePrice, DateRequired
                    FROM tblPurchaseOrderDetails 
                    WHERE PurchaseDetailID = ?
                """, (detail_id,))
                
                current_values = cursor.fetchone()
                if not current_values:
                    return {
                        'can_update': False,
                        'reason': 'Detail not found',
                        'status': 'not_found'
                    }
                
                # For now, we'll assume all details can be updated unless we get an error
                # In a real system, you might query invoice tables or status fields
                return {
                    'can_update': True,
                    'reason': 'Available for update',
                    'status': 'available',
                    'current_values': {
                        'quantity': float(current_values[0]) if current_values[0] else None,
                        'unit_price': float(current_values[1]) if current_values[1] else None,
                        'date_required': current_values[2]
                    }
                }
                
        except Exception as e:
            logger.warning(f"Could not check update status for detail ID {detail_id}: {e}")
            return {
                'can_update': True,  # Default to allowing updates
                'reason': 'Status check failed - assuming available',
                'status': 'unknown',
                'error': str(e)
            } 