import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from services.pdf_processor import PDFProcessor
from services.header_detail_database_service import HeaderDetailDatabaseService
from services.header_detail_ai_service import HeaderDetailAIService
from dotenv import load_dotenv

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

pdf_processor = PDFProcessor()
db_service = HeaderDetailDatabaseService()
ai_service = HeaderDetailAIService()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    """Main dashboard showing header/detail summary"""
    try:
        summary = db_service.get_all_headers_summary()
        
        # Calculate portfolio statistics
        total_value = sum(h['total_amount'] or 0 for h in summary)
        total_documents = len(summary)
        total_line_items = sum(h['line_item_count'] or 0 for h in summary)
        avg_doc_value = total_value / total_documents if total_documents > 0 else 0
        
        # Identify documents with total mismatches
        mismatches = []
        for doc in summary:
            calculated = doc['calculated_total'] or 0
            header_total = doc['total_amount'] or 0
            difference = abs(calculated - header_total)
            if difference > 0.01:
                mismatches.append({
                    'filename': doc['filename'],
                    'po_number': doc['po_number'],
                    'header_total': header_total,
                    'calculated_total': calculated,
                    'difference': difference
                })
        
        stats = {
            'total_value': total_value,
            'total_documents': total_documents,
            'total_line_items': total_line_items,
            'avg_doc_value': avg_doc_value,
            'mismatch_count': len(mismatches)
        }
        
        return render_template('index_header_detail.html', 
                             summary=summary[:10],  # Show latest 10
                             stats=stats,
                             mismatches=mismatches[:5])  # Show top 5 mismatches
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('index_header_detail.html', summary=[], stats={}, mismatches=[])

@app.route('/upload', methods=['GET', 'POST'])
def upload_pdf():
    """Upload and process PDF with header/detail extraction"""
    if request.method == 'POST':
        try:
            # Debug logging
            logger.info(f"POST request received. Files: {list(request.files.keys())}")
            logger.info(f"Form data: {list(request.form.keys())}")
            
            if 'pdf_file' not in request.files:
                logger.warning("No 'pdf_file' key in request.files")
                flash('No file selected', 'error')
                return redirect(request.url)
            
            file = request.files['pdf_file']
            logger.info(f"File object: {file}")
            logger.info(f"File filename: '{file.filename}'")
            
            if file.filename == '':
                logger.warning("File filename is empty")
                flash('No file selected', 'error')
                return redirect(request.url)
            
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Process PDF and extract text/metadata
                logger.info(f"Processing PDF: {filename}")
                pdf_data = pdf_processor.extract_text(filepath)
                
                # Extract structured data using header/detail AI
                logger.info("Starting AI header/detail extraction...")
                ai_result = ai_service.extract_header_detail_data(pdf_data.get('raw_text', ''))
                
                # Save to header/detail database
                header_id = db_service.save_header_detail_content(filename, pdf_data, ai_result)
                
                # Provide detailed feedback
                if ai_result.get('success'):
                    header_data = ai_result.get('header_data', {})
                    line_items = ai_result.get('line_items', [])
                    
                    po_number = header_data.get('po_number', 'N/A')
                    vendor = header_data.get('vendor_name', 'N/A')
                    total = header_data.get('total_amount', 0)
                    
                    flash(f'PDF processed successfully! Header ID: {header_id}', 'success')
                    flash(f'PO: {po_number} | Vendor: {vendor} | Total: ${total}', 'info')
                    flash(f'Extracted {len(line_items)} line items', 'info')
                else:
                    flash(f'PDF uploaded but AI extraction failed: {ai_result.get("error", "Unknown error")}', 'warning')
                
                # Clean up uploaded file
                try:
                    os.remove(filepath)
                except:
                    pass
                
                return redirect(url_for('view_document', header_id=header_id))
            else:
                flash('Invalid file type. Please upload a PDF file.', 'error')
                return redirect(request.url)
                
        except RequestEntityTooLarge:
            flash('File too large. Maximum size is 16MB.', 'error')
            return redirect(request.url)
        except Exception as e:
            logger.error(f"Error processing PDF upload: {e}")
            flash(f'Error processing PDF: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('upload_header_detail.html')

@app.route('/document/<int:header_id>')
def view_document(header_id):
    """View a specific document with all its line items"""
    try:
        document = db_service.get_header_with_line_items(header_id)
        if not document:
            flash('Document not found', 'error')
            return redirect(url_for('index'))
        
        # Calculate line item statistics
        line_items = document.get('line_items', [])
        calculated_total = sum(item.get('line_total', 0) or 0 for item in line_items)
        header_total = document.get('total_amount', 0) or 0
        total_mismatch = abs(calculated_total - header_total) > 0.01
        
        stats = {
            'line_item_count': len(line_items),
            'calculated_total': calculated_total,
            'header_total': header_total,
            'total_mismatch': total_mismatch,
            'mismatch_amount': calculated_total - header_total
        }
        
        return render_template('document_detail.html', document=document, stats=stats)
        
    except Exception as e:
        logger.error(f"Error loading document {header_id}: {e}")
        flash(f'Error loading document: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/documents')
def api_documents():
    """API endpoint for document summary"""
    try:
        summary = db_service.get_all_headers_summary()
        return jsonify({
            'success': True,
            'documents': summary,
            'total_count': len(summary)
        })
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/document/<int:header_id>')
def api_document(header_id):
    """API endpoint for specific document"""
    try:
        document = db_service.get_header_with_line_items(header_id)
        if not document:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404
        
        # Convert datetime objects to strings for JSON serialization
        def clean_for_json(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return obj
        
        # Clean the document data
        clean_document = {}
        for key, value in document.items():
            if key != 'line_items':
                clean_document[key] = clean_for_json(value)
        
        clean_line_items = []
        for item in document.get('line_items', []):
            clean_item = {}
            for key, value in item.items():
                clean_item[key] = clean_for_json(value)
            clean_line_items.append(clean_item)
        
        clean_document['line_items'] = clean_line_items
        
        return jsonify({
            'success': True,
            'document': clean_document
        })
        
    except Exception as e:
        logger.error(f"API error for document {header_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/reports')
def reports():
    """Reports page showing analytics"""
    try:
        summary = db_service.get_all_headers_summary()
        
        # Vendor analysis
        vendor_stats = {}
        for doc in summary:
            vendor = doc['vendor_name'] or 'Unknown'
            if vendor not in vendor_stats:
                vendor_stats[vendor] = {
                    'document_count': 0,
                    'total_value': 0,
                    'line_item_count': 0
                }
            vendor_stats[vendor]['document_count'] += 1
            vendor_stats[vendor]['total_value'] += doc['total_amount'] or 0
            vendor_stats[vendor]['line_item_count'] += doc['line_item_count'] or 0
        
        # Sort vendors by total value
        top_vendors = sorted(vendor_stats.items(), key=lambda x: x[1]['total_value'], reverse=True)[:10]
        
        return render_template('reports_header_detail.html', 
                             summary=summary,
                             vendor_stats=top_vendors)
                             
    except Exception as e:
        logger.error(f"Error loading reports: {e}")
        flash(f'Error loading reports: {str(e)}', 'error')
        return render_template('reports_header_detail.html', summary=[], vendor_stats=[])

@app.route('/compare')
def compare():
    """Comparison page placeholder"""
    return render_template('compare_header_detail.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True) 