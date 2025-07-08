"""
PDF Processing Service
Extracts text, metadata, and structured data from PDF files.
Supports both text-based and image-based PDFs with OCR fallback.
"""

import os
import logging
import PyPDF2
import pdfplumber
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PDFProcessor:
    """Service for processing PDF files and extracting text content"""

    def extract_text(self, filepath: str) -> dict:
        """
        Extract text content and metadata from a PDF file.
        Tries multiple extraction methods for maximum compatibility.

        Args:
            filepath: Path to the PDF file

        Returns:
            Dictionary containing extracted text, metadata, and structured data
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"PDF file not found: {filepath}")

        # Extract metadata
        metadata = self._extract_metadata(filepath)

        # Try multiple text extraction methods
        text_content = self._extract_text_with_fallback(filepath)

        # Parse structured data
        structured_data = self._parse_structured_data(text_content)

        return {
            'metadata': metadata,
            'raw_text': text_content,
            'structured_data': structured_data,
            'file_size': os.path.getsize(filepath),
            'page_count': metadata.get('page_count', 0),
            'extraction_method': getattr(self, '_last_extraction_method', 'unknown')
        }

    def _extract_metadata(self, filepath: str) -> dict:
        """Extract PDF metadata using PyPDF2"""
        try:
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                metadata = {
                    'page_count': len(pdf_reader.pages),
                    'title': '',
                    'author': '',
                    'subject': '',
                    'creator': '',
                    'producer': ''
                }
                if pdf_reader.metadata:
                    info = pdf_reader.metadata
                    metadata.update({
                        'title': info.get('/Title', ''),
                        'author': info.get('/Author', ''),
                        'subject': info.get('/Subject', ''),
                        'creator': info.get('/Creator', ''),
                        'producer': info.get('/Producer', '')
                    })
                return metadata
        except Exception as e:
            logger.warning(f"Error extracting metadata: {e}")
            return {'page_count': 0}

    def _extract_text_with_fallback(self, filepath: str) -> str:
        """
        Try multiple text extraction methods with fallback options
        """
        # Method 1: pdfplumber (best for most PDFs)
        try:
            text = self._extract_with_pdfplumber(filepath)
            if text and len(text.strip()) > 10:  # Minimum viable text
                self._last_extraction_method = 'pdfplumber'
                logger.info(f"Successfully extracted text using pdfplumber ({len(text)} chars)")
                return text
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")

        # Method 2: PyPDF2 (alternative text extraction)
        try:
            text = self._extract_with_pypdf2(filepath)
            if text and len(text.strip()) > 10:
                self._last_extraction_method = 'pypdf2'
                logger.info(f"Successfully extracted text using PyPDF2 ({len(text)} chars)")
                return text
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}")

        # Method 3: OCR with Tesseract (for image-based PDFs)
        try:
            text = self._extract_with_ocr(filepath)
            if text and len(text.strip()) > 10:
                self._last_extraction_method = 'ocr'
                logger.info(f"Successfully extracted text using OCR ({len(text)} chars)")
                return text
        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")

        # Method 4: Image extraction info (fallback)
        try:
            image_info = self._analyze_pdf_images(filepath)
            if image_info:
                self._last_extraction_method = 'image_analysis'
                logger.warning("PDF appears to be image-based. Consider using OCR tools.")
                return f"[Image-based PDF detected - {image_info}. Text extraction failed. Consider using OCR.]"
        except Exception as e:
            logger.warning(f"Image analysis failed: {e}")

        # All methods failed
        self._last_extraction_method = 'failed'
        logger.error("All text extraction methods failed")
        return "[No text could be extracted from this PDF]"

    def _extract_with_pdfplumber(self, filepath: str) -> str:
        """Extract text content using pdfplumber"""
        full_text = []
        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        full_text.append(f"--- Page {page_num} ---\n{page_text}")
                    else:
                        # Try extracting from tables if regular text fails
                        tables = page.extract_tables()
                        if tables:
                            table_text = self._tables_to_text(tables)
                            full_text.append(f"--- Page {page_num} (Tables) ---\n{table_text}")
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num}: {e}")
        
        return '\n\n'.join(full_text)

    def _extract_with_pypdf2(self, filepath: str) -> str:
        """Extract text using PyPDF2 as fallback"""
        full_text = []
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        full_text.append(f"--- Page {page_num} ---\n{page_text}")
                except Exception as e:
                    logger.warning(f"PyPDF2 error on page {page_num}: {e}")
        
        return '\n\n'.join(full_text)

    def _extract_with_ocr(self, filepath: str) -> str:
        """Extract text using OCR (requires pdf2image and pytesseract)"""
        try:
            # Try to import OCR dependencies
            from pdf2image import convert_from_path
            import pytesseract
            
            logger.info("Attempting OCR extraction for image-based PDF...")
            
            # Convert PDF to images
            images = convert_from_path(filepath, dpi=300)
            
            full_text = []
            for page_num, image in enumerate(images, 1):
                try:
                    # Perform OCR on the image
                    page_text = pytesseract.image_to_string(image, lang='eng')
                    if page_text.strip():
                        full_text.append(f"--- Page {page_num} (OCR) ---\n{page_text}")
                except Exception as e:
                    logger.warning(f"OCR failed on page {page_num}: {e}")
            
            return '\n\n'.join(full_text)
            
        except ImportError:
            logger.warning("OCR dependencies not available. Install pdf2image and pytesseract for image-based PDF support.")
            raise Exception("OCR dependencies not installed")

    def _analyze_pdf_images(self, filepath: str) -> str:
        """Analyze if PDF contains images instead of text"""
        try:
            with pdfplumber.open(filepath) as pdf:
                page_info = []
                for page_num, page in enumerate(pdf.pages, 1):
                    images = page.images
                    if images:
                        page_info.append(f"Page {page_num}: {len(images)} images")
                
                if page_info:
                    return f"Contains images: {', '.join(page_info)}"
                else:
                    return "No images detected"
        except Exception:
            return "Unable to analyze images"

    def _tables_to_text(self, tables) -> str:
        """Convert extracted tables to text format"""
        table_text = []
        for table_num, table in enumerate(tables, 1):
            if table:
                table_text.append(f"Table {table_num}:")
                for row in table:
                    if row:
                        # Clean and join row cells
                        clean_row = [str(cell).strip() if cell else '' for cell in row]
                        table_text.append(' | '.join(clean_row))
                table_text.append('')  # Empty line between tables
        
        return '\n'.join(table_text)

    def _parse_structured_data(self, text: str) -> dict:
        """
        Parse structured data from extracted text.
        Extracts dates, emails, URLs, numbers, and key-value pairs.
        """
        structured_data = {
            'dates': [],
            'emails': [],
            'urls': [],
            'numbers': [],
            'key_value_pairs': {}
        }
        try:
            # Dates
            date_patterns = [
                r'\d{1,2}/\d{1,2}/\d{2,4}',
                r'\d{4}-\d{2}-\d{2}',
                r'\d{1,2}-\d{1,2}-\d{2,4}'
            ]
            for pattern in date_patterns:
                structured_data['dates'].extend(re.findall(pattern, text))

            # Emails
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            structured_data['emails'] = re.findall(email_pattern, text)

            # URLs
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            structured_data['urls'] = re.findall(url_pattern, text)

            # Numbers
            number_pattern = r'\b\d+(?:\.\d+)?\b'
            structured_data['numbers'] = re.findall(number_pattern, text)

            # Key-value pairs
            key_value_pattern = r'([A-Za-z\s]+):\s*([^\n]+)'
            matches = re.findall(key_value_pattern, text)
            for key, value in matches:
                key = key.strip()
                value = value.strip()
                if key and value:
                    structured_data['key_value_pairs'][key] = value

        except Exception as e:
            logger.warning(f"Error parsing structured data: {e}")

        return structured_data 