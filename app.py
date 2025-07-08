import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from services.pdf_processor import PDFProcessor
from services.database_service import DatabaseService
from services.ai_extraction_service import AIExtractionService
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
db_service = DatabaseService()
ai_service = AIExtractionService()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_pdf():
    if request.method == 'POST':
        try:
            if 'pdf_file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)
            file = request.files['pdf_file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                # Process PDF and extract text/metadata
                pdf_data = pdf_processor.extract_text(filepath)
                
                # Extract structured data using AI
                logger.info("Starting AI extraction...")
                ai_extracted_data = ai_service.extract_structured_data(pdf_data.get('raw_text', ''))
                
                # Save to ETO_PDF database with AI data
                upload_id = db_service.save_pdf_content(filename, pdf_data, ai_extracted_data)
                flash(f'PDF uploaded and processed successfully! Upload ID: {upload_id}', 'success')
                return redirect(url_for('upload_pdf'))
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
    return render_template('upload.html')

@app.route('/compare')
def compare():
    return render_template('compare.html')

@app.route('/reports')
def reports():
    return render_template('reports.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080) 