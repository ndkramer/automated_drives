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
        """Extract text using OCR with enhanced image preprocessing for better accuracy"""
        try:
            # Try to import OCR dependencies
            from pdf2image import convert_from_path
            import pytesseract
            from PIL import Image, ImageEnhance, ImageFilter
            
            logger.info("Attempting OCR extraction for image-based PDF...")
            
            # Convert PDF to images with higher DPI for better quality
            images = convert_from_path(filepath, dpi=400)
            
            full_text = []
            for page_num, image in enumerate(images, 1):
                try:
                    # Enhanced OCR with multiple attempts
                    page_text = self._ocr_with_preprocessing(image)
                    if page_text.strip():
                        full_text.append(f"--- Page {page_num} (OCR) ---\n{page_text}")
                except Exception as e:
                    logger.warning(f"OCR failed on page {page_num}: {e}")
            
            return '\n\n'.join(full_text)
            
        except ImportError:
            logger.warning("OCR dependencies not available. Install pdf2image and pytesseract for image-based PDF support.")
            raise Exception("OCR dependencies not installed")

    def _ocr_with_preprocessing(self, image) -> str:
        """
        Perform OCR with image preprocessing and multiple configurations
        to handle poor quality scanned documents
        """
        import pytesseract
        from PIL import Image, ImageEnhance, ImageFilter
        
        # Try multiple preprocessing approaches
        preprocessing_methods = [
            self._preprocess_default,
            self._preprocess_high_contrast,
            self._preprocess_denoised,
            self._preprocess_sharpened
        ]
        
        # OCR configurations optimized for different document types
        ocr_configs = [
            '--oem 3 --psm 6',  # Uniform block of text
            '--oem 3 --psm 4',  # Single column of text  
            '--oem 3 --psm 3',  # Fully automatic page segmentation
            '--oem 3 --psm 1',  # Automatic page segmentation with OSD
        ]
        
        best_result = ""
        best_confidence = 0
        
        for preprocess_method in preprocessing_methods:
            try:
                processed_image = preprocess_method(image)
                
                for config in ocr_configs:
                    try:
                        # Get OCR result with confidence data
                        result = pytesseract.image_to_string(processed_image, config=config)
                        
                        # Simple confidence estimation based on text quality
                        confidence = self._estimate_ocr_confidence(result)
                        
                        if confidence > best_confidence and len(result.strip()) > 50:
                            best_result = result
                            best_confidence = confidence
                            
                    except Exception as e:
                        logger.debug(f"OCR config {config} failed: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Preprocessing method failed: {e}")
                continue
        
        return best_result if best_result else pytesseract.image_to_string(image)

    def _preprocess_default(self, image):
        """Default preprocessing - convert to grayscale"""
        return image.convert('L')

    def _preprocess_high_contrast(self, image):
        """High contrast preprocessing for faded documents"""
        from PIL import ImageEnhance
        image = image.convert('L')
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(2.5)

    def _preprocess_denoised(self, image):
        """Denoising preprocessing for noisy scans"""
        from PIL import ImageFilter
        image = image.convert('L')
        return image.filter(ImageFilter.MedianFilter(3))

    def _preprocess_sharpened(self, image):
        """Sharpening preprocessing for blurry documents"""
        from PIL import ImageEnhance, ImageFilter
        image = image.convert('L')
        # Apply sharpening filter
        image = image.filter(ImageFilter.SHARPEN)
        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(2.0)

    def _estimate_ocr_confidence(self, text: str) -> float:
        """
        Estimate OCR confidence based on text characteristics
        Higher scores for text with more recognizable patterns
        """
        if not text or len(text.strip()) < 10:
            return 0.0
        
        confidence_score = 0.0
        
        # Check for common business document patterns
        patterns = [
            (r'\b\d{4,6}\b', 5.0),  # Invoice/PO numbers
            (r'\$\d+\.?\d*', 10.0),  # Currency amounts
            (r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', 8.0),  # Dates
            (r'\b[A-Z]{2,}\s+[A-Z]{2,}\b', 3.0),  # Company names
            (r'\(\d{3}\)\s*\d{3}-\d{4}', 7.0),  # Phone numbers
            (r'\b\d{5}(-\d{4})?\b', 4.0),  # ZIP codes
        ]
        
        for pattern, weight in patterns:
            import re
            matches = len(re.findall(pattern, text))
            confidence_score += matches * weight
        
        # Penalize for too many special characters (OCR errors)
        special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s\.,\-\(\)\/\$]', text)) / len(text)
        confidence_score -= special_char_ratio * 20
        
        # Bonus for reasonable text length
        if 100 <= len(text) <= 2000:
            confidence_score += 5.0
        
        return max(0.0, confidence_score)

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