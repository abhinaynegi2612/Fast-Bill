"""
Bill Parser Service
Extracts structured data from PDF bills using multiple strategies
"""
import re
import pdfplumber
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

from app.models.schemas import BillData, BillItem
from app.core.config import settings

# Configure Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

logger = logging.getLogger(__name__)


class BillParser:
    """Extract and structure bill data from PDFs"""
    
    # Common patterns for Indian bills
    AMOUNT_PATTERNS = [
        r'Total\s*Amount[:\s]+[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'Grand\s*Total[:\s]+[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'Net\s*Amount[:\s]+[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'Amount\s*Payable[:\s]+[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'Bill\s*Total[:\s]+[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'Total[:\s]+[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'₹\s*([0-9,]+\.?[0-9]*)',
        r'([0-9,]+\.[0-9]{2})',
    ]
    
    GST_PATTERNS = [
        r'GST\s*\(\d+%\)[:\s]*[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'GST\s*@\s*\d+%[:\s]*[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'GST\s*(?:Amount|Value)[:\s]*[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'Total\s*GST[:\s]*[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'\bTax\b[:\s]*[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
        r'(?:CGST|SGST|IGST)[:\s]*[₹Rs.\s]*([0-9,]+\.?[0-9]*)',
    ]
    
    ITEM_PATTERNS = [
        r'(\d+)\s+(\w+)\s+([\w\s-]+?)\s+(\d+(?:\.\d{2})?)\s+(\d+(?:\.\d{2})?)',
        r'([\w\s-]+?)\s+(\d+(?:\.\d+)?)\s+(\w+)\s+[₹x]?\s*(\d+(?:\.\d{2})?)',
    ]
    
    def __init__(self):
        self.df_items: Optional[pd.DataFrame] = None
        self.raw_text: str = ""
    
    def parse_pdf(self, pdf_path: str | Path) -> BillData:
        """Main parsing method - tries multiple extraction strategies"""
        pdf_path = Path(pdf_path)
        
        # Strategy 1: Direct text extraction with pdfplumber
        bill_data = self._parse_with_pdfplumber(pdf_path)
        
        # Strategy 2: If insufficient data, use OCR
        if not bill_data.items or bill_data.total_amount == 0:
            bill_data = self._parse_with_ocr(pdf_path, bill_data)
        
        # Strategy 3: Post-process and validate
        bill_data = self._post_process(bill_data)
        
        return bill_data
    
    def _parse_with_pdfplumber(self, pdf_path: Path) -> BillData:
        """Extract using pdfplumber (best for structured PDFs)"""
        bill_data = BillData()
        all_text = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    all_text.append(text)
                    
                    # Extract tables
                    tables = page.extract_tables()
                    for table in tables:
                        items = self._parse_table_to_items(table)
                        if items:
                            bill_data.items.extend(items)
                    
                    # Extract from text if no tables
                    if not bill_data.items:
                        items = self._extract_items_from_text(text)
                        bill_data.items.extend(items)
                    
                    # Extract amounts
                    bill_data.total_amount = self._extract_total_smart(text)
                    if bill_data.total_amount == 0:
                        bill_data.total_amount = self._extract_amount(text, self.AMOUNT_PATTERNS)
                    
                    bill_data.gst_amount = self._extract_gst_smart(text)
                    
                    # Calculate subtotal
                    if bill_data.items:
                        bill_data.subtotal = sum(item.amount for item in bill_data.items)
                    elif bill_data.total_amount > bill_data.gst_amount:
                        bill_data.subtotal = bill_data.total_amount - bill_data.gst_amount
                    
                    # Extract metadata
                    bill_data.vendor_name = self._extract_vendor(text)
                    bill_data.bill_number = self._extract_bill_number(text)
                    bill_data.bill_date = self._extract_date(text)
                    
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
        
        bill_data.raw_text = "\n".join(all_text)
        return bill_data
    
    def _parse_with_ocr(self, pdf_path: Path, existing_data: BillData) -> BillData:
        """Extract using OCR (for scanned/image PDFs)"""
        try:
            images = convert_from_path(pdf_path, dpi=settings.OCR_DPI)
            
            all_text = []
            for image in images:
                text = pytesseract.image_to_string(image, lang=settings.OCR_LANG)
                all_text.append(text)
                
                if not existing_data.items:
                    items = self._extract_items_from_text(text)
                    existing_data.items.extend(items)
                
                if existing_data.total_amount == 0:
                    existing_data.total_amount = self._extract_total_smart(text)
                if existing_data.total_amount == 0:
                    existing_data.total_amount = self._extract_amount(text, self.AMOUNT_PATTERNS)
                
                if existing_data.gst_amount == 0:
                    existing_data.gst_amount = self._extract_gst_smart(text)
            
            existing_data.raw_text = existing_data.raw_text + "\n" + "\n".join(all_text)
            
            if existing_data.items and existing_data.subtotal == 0:
                existing_data.subtotal = sum(item.amount for item in existing_data.items)
            
        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")
        
        return existing_data
    
    def _parse_table_to_items(self, table: List[List[Any]]) -> List[BillItem]:
        """Convert extracted table to BillItem objects"""
        items = []
        
        if not table or len(table) < 2:
            return items
        
        headers = [str(h).lower().strip() if h else "" for h in table[0]]
        
        name_idx = self._find_column_index(headers, ['item', 'description', 'product', 'name'])
        qty_idx = self._find_column_index(headers, ['qty', 'quantity', 'qnty'])
        price_idx = self._find_column_index(headers, ['price', 'rate', 'unit price', 'mrp'])
        amount_idx = self._find_column_index(headers, ['amount', 'total', 'value'])
        
        for row in table[1:]:
            if not row or all(cell is None for cell in row):
                continue
            
            try:
                name = row[name_idx] if name_idx is not None and name_idx < len(row) else "Unknown"
                qty = float(row[qty_idx]) if qty_idx is not None and qty_idx < len(row) and row[qty_idx] else 1.0
                price = float(row[price_idx]) if price_idx is not None and price_idx < len(row) and row[price_idx] else 0.0
                amount = float(row[amount_idx]) if amount_idx is not None and amount_idx < len(row) and row[amount_idx] else 0.0
                
                if amount == 0 and price > 0 and qty > 0:
                    amount = price * qty
                
                if name and str(name).strip() and amount > 0:
                    items.append(BillItem(
                        name=str(name).strip(),
                        quantity=qty,
                        price=price,
                        amount=amount
                    ))
            except (ValueError, IndexError, TypeError):
                continue
        
        return items
    
    def _find_column_index(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index by keywords"""
        for i, header in enumerate(headers):
            if any(keyword in header for keyword in keywords):
                return i
        return None
    
    def _extract_items_from_text(self, text: str) -> List[BillItem]:
        """Extract item lines from raw text using regex"""
        items = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for pattern in self.ITEM_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    try:
                        if len(groups) >= 5:
                            qty = float(groups[0])
                            name = groups[2].strip()
                            price = float(groups[3].replace(',', ''))
                            amount = float(groups[4].replace(',', ''))
                        elif len(groups) >= 4:
                            name = groups[0].strip()
                            qty = float(groups[1])
                            price = float(groups[3].replace(',', ''))
                            amount = qty * price
                        else:
                            continue
                        
                        if name and amount > 0:
                            items.append(BillItem(
                                name=name,
                                quantity=qty,
                                price=price,
                                amount=amount
                            ))
                        break
                    except (ValueError, IndexError):
                        continue
        
        return items
    
    def _extract_total_smart(self, text: str) -> float:
        """Smart extraction for Total - looks for amounts near Total keywords"""
        lines = text.split('\n')
        total_keywords = ['total amount', 'grand total', 'net amount', 'amount payable', 'bill total']
        amounts_found = []
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            if any(keyword in line_lower for keyword in total_keywords) and 'subtotal' not in line_lower:
                amount_match = re.search(r'[₹Rs.\s]*([0-9,]+\.?[0-9]*)', line)
                if amount_match:
                    try:
                        amount_str = amount_match.group(1).replace(',', '')
                        amount = float(amount_str)
                        if 0 < amount < 1000000:
                            amounts_found.append((amount, i))
                    except ValueError:
                        pass
        
        if amounts_found:
            return max(amounts_found, key=lambda x: x[0])[0]
        
        last_lines = '\n'.join(lines[-10:])
        all_amounts = re.findall(r'[₹Rs.\s]*([0-9,]+\.[0-9]{2})', last_lines)
        
        valid_amounts = []
        for amt_str in all_amounts:
            try:
                amt = float(amt_str.replace(',', ''))
                if 0 < amt < 1000000:
                    valid_amounts.append(amt)
            except ValueError:
                pass
        
        if valid_amounts:
            return max(valid_amounts)
        
        return 0.0
    
    def _extract_gst_smart(self, text: str) -> float:
        """Smart extraction for GST - looks for GST lines specifically"""
        lines = text.split('\n')
        
        for line in lines:
            line_lower = line.lower()
            
            # Check if line contains GST keyword (but not Subtotal or Total)
            if 'gst' in line_lower and 'subtotal' not in line_lower and 'total' not in line_lower:
                # Look for pattern: GST (5%): 51.5 or GST: 51.5 or GST (5%) 51.5
                # The amount comes AFTER the percentage or GST label
                amount_match = re.search(r'(?:GST|Tax).*?(?:\d+%)?[:\s]*[₹Rs.\s]*([0-9,]+\.?[0-9]*)', line, re.IGNORECASE)
                if amount_match:
                    try:
                        amount_str = amount_match.group(1).replace(',', '')
                        amount = float(amount_str)
                        # GST amount should be reasonable (not the percentage number like 5, 12, 18)
                        # Percentages are usually 5, 12, 18, 28 - amounts are usually larger
                        if amount > 10:  # Filter out small numbers that might be percentages
                            return amount
                    except ValueError:
                        pass
        
        return self._extract_amount(text, self.GST_PATTERNS)
    
    def _extract_amount(self, text: str, patterns: List[str]) -> float:
        """Extract monetary amount using regex patterns"""
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    
                    amount_str = str(match).strip()
                    amount_str = amount_str.replace(',', '').replace(' ', '').replace('Rs.', '').replace('₹', '')
                    
                    if not amount_str or amount_str == '.':
                        continue
                        
                    amount = float(amount_str)
                    if 0 < amount < 1000000:
                        return amount
                except (ValueError, TypeError):
                    continue
        return 0.0
    
    def _extract_vendor(self, text: str) -> Optional[str]:
        """Extract vendor/store name from bill"""
        lines = [l.strip() for l in text.split('\n') if l.strip()][:10]
        
        for line in lines:
            if any(skip in line.lower() for skip in ['bill', 'invoice', 'date', 'tax']):
                continue
            if len(line) > 3 and not line.isdigit():
                return line
        return None
    
    def _extract_bill_number(self, text: str) -> Optional[str]:
        """Extract bill/invoice number"""
        patterns = [
            r'(?:Bill|Invoice)\s*(?:No|Number|#)[:.\s]*(\w+[-]?\d+)',
            r'(?:Bill|Invoice)\s*(?:No|Number|#)[:.\s]*(\d+)',
            r'#\s*(\d{3,})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract bill date - supports multiple formats"""
        patterns = [
            r'(?:Date)[:.\s]*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',
            r'(?:Date)[:.\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(?:Date)[:.\s]*(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _post_process(self, bill_data: BillData) -> BillData:
        """Validate and clean extracted data"""
        seen = set()
        unique_items = []
        for item in bill_data.items:
            key = (item.name.lower(), item.amount)
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        bill_data.items = unique_items
        
        if bill_data.items and bill_data.subtotal == 0:
            bill_data.subtotal = sum(item.amount for item in bill_data.items)
        
        if bill_data.gst_amount == 0:
            if bill_data.subtotal > 0 and bill_data.total_amount > bill_data.subtotal:
                bill_data.gst_amount = bill_data.total_amount - bill_data.subtotal
                if bill_data.subtotal > 0:
                    bill_data.gst_rate = round((bill_data.gst_amount / bill_data.subtotal) * 100, 2)
            elif bill_data.items and bill_data.total_amount > 0:
                items_total = sum(item.amount for item in bill_data.items)
                if bill_data.total_amount > items_total:
                    bill_data.subtotal = items_total
                    bill_data.gst_amount = bill_data.total_amount - items_total
                    bill_data.gst_rate = round((bill_data.gst_amount / items_total) * 100, 2)
        
        if bill_data.items:
            self.df_items = pd.DataFrame([
                {
                    'name': item.name,
                    'quantity': item.quantity,
                    'unit': item.unit,
                    'price': item.price,
                    'amount': item.amount
                }
                for item in bill_data.items
            ])
        
        return bill_data
    
    def to_dataframe(self) -> Optional[pd.DataFrame]:
        """Return items as pandas DataFrame"""
        return self.df_items
    
    def to_dict(self, bill_data: BillData) -> Dict[str, Any]:
        """Convert BillData to dictionary"""
        return bill_data.dict()


# Singleton instance
bill_parser = BillParser()
