"""
Forgery Detection Service - Module 1
Production-level forgery/tampering detection for bill PDFs
"""
import hashlib
import json
import re
import cv2
import numpy as np
import fitz  # PyMuPDF
import pikepdf
from PIL import Image, ImageChops
from pdf2image import convert_from_path
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime

from app.models.schemas import ForgeryDetectionResponse, ForgeryCheck
from app.core.config import settings

# Configure Tesseract path for Windows
import pytesseract
pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

logger = logging.getLogger(__name__)


@dataclass
class PDFMetadata:
    """Structured PDF metadata"""
    filename: str
    file_hash: str
    file_size: int
    page_count: int
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    producer: Optional[str] = None
    creator: Optional[str] = None
    author: Optional[str] = None
    software: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'filename': self.filename,
            'file_hash': self.file_hash,
            'file_size': self.file_size,
            'page_count': self.page_count,
            'creation_date': self.creation_date,
            'modification_date': self.modification_date,
            'producer': self.producer,
            'creator': self.creator,
            'author': self.author,
            'software': self.software
        }


class ForgeryDetector:
    """
    Multi-layered forgery detection for bill PDFs
    Uses: metadata analysis, visual comparison, OCR mismatch detection,
    hash comparison, structural analysis
    """
    
    def __init__(self):
        self.checks: List[ForgeryCheck] = []
        self.confidence_scores: List[float] = []
        self.reasons: List[str] = []
    
    def detect(self, original_path: str | Path, suspected_path: str | Path) -> ForgeryDetectionResponse:
        """
        Main entry point - runs all forgery detection checks
        """
        import time
        start_time = time.time()
        
        original_path = Path(original_path)
        suspected_path = Path(suspected_path)
        
        self.checks = []
        self.confidence_scores = []
        self.reasons = []
        
        # Run all detection layers
        self._check_file_hash(original_path, suspected_path)
        self._check_metadata(original_path, suspected_path)
        self._check_visual_similarity(original_path, suspected_path)
        self._check_ocr_consistency(original_path, suspected_path)
        self._check_structural_integrity(original_path, suspected_path)
        
        # Calculate final verdict
        tampered = any(not check.passed for check in self.checks)
        confidence = self._calculate_overall_confidence()
        
        # Get metadata for response
        orig_meta = self._extract_metadata(original_path)
        susp_meta = self._extract_metadata(suspected_path)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return ForgeryDetectionResponse(
            tampered=tampered,
            confidence=confidence,
            reasons=self.reasons,
            checks=self.checks,
            original_metadata=orig_meta.to_dict() if orig_meta else None,
            suspected_metadata=susp_meta.to_dict() if susp_meta else None,
            processing_time_ms=processing_time
        )
    
    def _check_file_hash(self, orig_path: Path, susp_path: Path):
        """Check 1: File hash comparison"""
        orig_hash = self._calculate_hash(orig_path)
        susp_hash = self._calculate_hash(susp_path)
        
        identical = orig_hash == susp_hash
        
        check = ForgeryCheck(
            check_name="File Hash Comparison",
            passed=identical,
            confidence=1.0 if identical else 0.0,
            details="Files are identical" if identical else "Files have different content",
            evidence={
                'original_hash': orig_hash,
                'suspected_hash': susp_hash
            }
        )
        self.checks.append(check)
        
        if not identical:
            self.reasons.append("File hash mismatch - content is different")
            self.confidence_scores.append(1.0)
    
    def _check_metadata(self, orig_path: Path, susp_path: Path):
        """Check 2: Metadata analysis for suspicious indicators"""
        orig_meta = self._extract_metadata(orig_path)
        susp_meta = self._extract_metadata(susp_path)
        
        metadata_issues = []
        confidence = 1.0
        
        # Check for suspicious software
        suspicious_keywords = settings.METADATA_SUSPICIOUS_KEYWORDS
        
        for meta in [susp_meta]:
            software_str = ' '.join([
                str(meta.producer or ''),
                str(meta.creator or ''),
                str(meta.software or '')
            ]).lower()
            
            for keyword in suspicious_keywords:
                if keyword in software_str:
                    metadata_issues.append(f"Suspicious software detected: {keyword}")
                    confidence -= 0.2
        
        # Check modification date mismatch
        if orig_meta.modification_date and susp_meta.modification_date:
            if orig_meta.modification_date != susp_meta.modification_date:
                metadata_issues.append("Modification dates differ significantly")
                confidence -= 0.1
        
        # Check for recent edits (only relevant if files are different)
        if susp_meta.modification_date and orig_meta.file_hash != susp_meta.file_hash:
            try:
                metadata_issues.append("Recent modification detected")
                confidence -= 0.05
            except:
                pass
        
        check = ForgeryCheck(
            check_name="Metadata Analysis",
            passed=len(metadata_issues) == 0,
            confidence=max(0.0, confidence),
            details="No suspicious metadata found" if len(metadata_issues) == 0 else f"Found {len(metadata_issues)} issues",
            evidence={'issues': metadata_issues}
        )
        self.checks.append(check)
        
        if metadata_issues:
            self.reasons.extend(metadata_issues)
            self.confidence_scores.append(1.0 - confidence)
    
    def _check_visual_similarity(self, orig_path: Path, susp_path: Path):
        """Check 3: Visual comparison using image diff"""
        try:
            # Convert first page to images
            orig_images = convert_from_path(orig_path, dpi=150, first_page=1, last_page=1)
            susp_images = convert_from_path(susp_path, dpi=150, first_page=1, last_page=1)
            
            if not orig_images or not susp_images:
                raise ValueError("Could not convert PDF to images")
            
            orig_img = orig_images[0]
            susp_img = susp_images[0]
            
            # Ensure same size
            if orig_img.size != susp_img.size:
                susp_img = susp_img.resize(orig_img.size)
            
            # Calculate diff
            diff = ImageChops.difference(orig_img, susp_img)
            
            # Convert to numpy for analysis
            diff_array = np.array(diff)
            non_zero = np.count_nonzero(diff_array)
            total_pixels = diff_array.size
            
            diff_percentage = (non_zero / total_pixels) * 100
            
            # Threshold: >1% difference is suspicious
            threshold = 1.0
            passed = diff_percentage < threshold
            
            # Check for specific tampering patterns
            if not passed:
                # Check for region-based edits (localized changes)
                gray = cv2.cvtColor(diff_array, cv2.COLOR_RGB2GRAY)
                _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
                
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Large contours indicate edited regions
                large_contours = [c for c in contours if cv2.contourArea(c) > 1000]
                
                if large_contours:
                    self.reasons.append(f"Visual inconsistency detected: {len(large_contours)} edited regions found")
                    self.confidence_scores.append(min(1.0, diff_percentage / 10))
            
            check = ForgeryCheck(
                check_name="Visual Comparison",
                passed=passed,
                confidence=max(0.0, 1.0 - (diff_percentage / 10)),
                details=f"Image difference: {diff_percentage:.2f}%",
                evidence={
                    'difference_percentage': diff_percentage,
                    'pixels_changed': int(non_zero),
                    'total_pixels': int(total_pixels)
                }
            )
            self.checks.append(check)
            
        except Exception as e:
            error_msg = str(e)
            # Check if it's a poppler issue
            if "poppler" in error_msg.lower() or "page count" in error_msg.lower():
                logger.warning("Poppler not installed - skipping visual comparison")
                self.checks.append(ForgeryCheck(
                    check_name="Visual Comparison",
                    passed=True,  # Don't flag as tampered if we can't check
                    confidence=0.5,
                    details="Visual comparison skipped (Poppler not installed)",
                    evidence={'note': 'Install poppler for visual comparison: conda install -c conda-forge poppler'}
                ))
            else:
                logger.warning(f"Visual comparison failed: {e}")
                self.checks.append(ForgeryCheck(
                    check_name="Visual Comparison",
                    passed=False,
                    confidence=0.5,
                    details=f"Visual comparison error: {str(e)}",
                    evidence={'error': str(e)}
                ))
    
    def _check_ocr_consistency(self, orig_path: Path, susp_path: Path):
        """Check 4: OCR text comparison for tampering"""
        try:
            import pytesseract
            
            # Convert to images
            orig_images = convert_from_path(orig_path, dpi=200, first_page=1, last_page=1)
            susp_images = convert_from_path(susp_path, dpi=200, first_page=1, last_page=1)
            
            orig_text = pytesseract.image_to_string(orig_images[0])
            susp_text = pytesseract.image_to_string(susp_images[0])
            
            # Compare extracted amounts (critical for bills)
            orig_amounts = self._extract_amounts(orig_text)
            susp_amounts = self._extract_amounts(susp_text)
            
            # Check for amount discrepancies
            amount_issues = []
            
            for key in ['total', 'gst', 'subtotal']:
                if key in orig_amounts and key in susp_amounts:
                    if abs(orig_amounts[key] - susp_amounts[key]) > 0.01:
                        amount_issues.append(f"{key.capitalize()} amount changed: {orig_amounts[key]:.2f} → {susp_amounts[key]:.2f}")
            
            # Check for missing amounts
            for key in orig_amounts:
                if key not in susp_amounts:
                    amount_issues.append(f"{key.capitalize()} amount removed from suspected bill")
            
            # Check for new amounts
            for key in susp_amounts:
                if key not in orig_amounts:
                    amount_issues.append(f"New {key} amount added to suspected bill")
            
            passed = len(amount_issues) == 0
            confidence = 1.0 - (len(amount_issues) * 0.25)
            
            check = ForgeryCheck(
                check_name="OCR Consistency",
                passed=passed,
                confidence=max(0.0, confidence),
                details="OCR amounts match" if passed else f"Found {len(amount_issues)} amount discrepancies",
                evidence={
                    'original_amounts': orig_amounts,
                    'suspected_amounts': susp_amounts,
                    'issues': amount_issues
                }
            )
            self.checks.append(check)
            
            if amount_issues:
                self.reasons.extend(amount_issues)
                self.confidence_scores.append(1.0 - confidence)
                
        except Exception as e:
            error_msg = str(e)
            if "poppler" in error_msg.lower() or "page count" in error_msg.lower():
                logger.warning("Poppler not installed - skipping OCR check")
                self.checks.append(ForgeryCheck(
                    check_name="OCR Consistency",
                    passed=True,
                    confidence=0.5,
                    details="OCR check skipped (Poppler not installed)",
                    evidence={'note': 'Install poppler for OCR comparison'}
                ))
            else:
                logger.warning(f"OCR consistency check failed: {e}")
                self.checks.append(ForgeryCheck(
                    check_name="OCR Consistency",
                    passed=False,
                    confidence=0.5,
                    details=f"OCR error: {str(e)}",
                    evidence={'error': str(e)}
                ))
    
    def _check_structural_integrity(self, orig_path: Path, susp_path: Path):
        """Check 5: PDF structure comparison"""
        try:
            orig_doc = fitz.open(orig_path)
            susp_doc = fitz.open(susp_path)
            
            issues = []
            
            # Page count check
            if len(orig_doc) != len(susp_doc):
                issues.append(f"Page count changed: {len(orig_doc)} → {len(susp_doc)}")
            
            # Object count check (rough indicator of structure changes)
            orig_objects = orig_doc.xref_length()
            susp_objects = susp_doc.xref_length()
            
            if abs(orig_objects - susp_objects) > 10:
                issues.append(f"PDF structure significantly modified")
            
            # Font analysis
            orig_fonts = set()
            susp_fonts = set()
            
            for page in orig_doc:
                fonts = page.get_fonts()
                orig_fonts.update([f[3] for f in fonts])
            
            for page in susp_doc:
                fonts = page.get_fonts()
                susp_fonts.update([f[3] for f in fonts])
            
            if orig_fonts != susp_fonts:
                added = susp_fonts - orig_fonts
                removed = orig_fonts - susp_fonts
                if added:
                    issues.append(f"New fonts detected: {', '.join(list(added)[:3])}")
                if removed:
                    issues.append(f"Fonts removed: {', '.join(list(removed)[:3])}")
            
            orig_doc.close()
            susp_doc.close()
            
            passed = len(issues) == 0
            confidence = 1.0 - (len(issues) * 0.2)
            
            check = ForgeryCheck(
                check_name="Structural Integrity",
                passed=passed,
                confidence=max(0.0, confidence),
                details="PDF structure intact" if passed else f"Found {len(issues)} structural issues",
                evidence={
                    'original_pages': len(orig_doc),
                    'suspected_pages': len(susp_doc),
                    'original_fonts': list(orig_fonts)[:10],
                    'suspected_fonts': list(susp_fonts)[:10],
                    'issues': issues
                }
            )
            self.checks.append(check)
            
            if issues:
                self.reasons.extend(issues)
                self.confidence_scores.append(1.0 - confidence)
                
        except Exception as e:
            logger.warning(f"Structural integrity check failed: {e}")
            # Don't flag as tampered if we can't check
            self.checks.append(ForgeryCheck(
                check_name="Structural Integrity",
                passed=True,
                confidence=0.5,
                details=f"Structure check skipped: {str(e)}",
                evidence={'note': 'Structural comparison unavailable'}
            ))
    
    def _calculate_overall_confidence(self) -> float:
        """Calculate overall tampering confidence percentage"""
        if not self.confidence_scores:
            return 0.0
        
        # Weighted average of all confidence scores
        avg_confidence = sum(self.confidence_scores) / len(self.confidence_scores)
        return round(avg_confidence * 100, 2)
    
    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _extract_metadata(self, file_path: Path) -> PDFMetadata:
        """Extract PDF metadata using PyMuPDF"""
        doc = fitz.open(file_path)
        metadata = doc.metadata
        
        # Extract software info from XMP if available
        software = []
        try:
            xmp = doc.metadata.get('xmp', '')
            if xmp:
                # Simple extraction - in production use proper XML parsing
                software_matches = re.findall(r'<pdf:Producer>(.*?)</pdf:Producer>', str(xmp))
                software.extend(software_matches)
        except:
            pass
        
        file_hash = self._calculate_hash(file_path)
        
        pdf_meta = PDFMetadata(
            filename=file_path.name,
            file_hash=file_hash,
            file_size=file_path.stat().st_size,
            page_count=len(doc),
            creation_date=metadata.get('creationDate'),
            modification_date=metadata.get('modDate'),
            producer=metadata.get('producer'),
            creator=metadata.get('creator'),
            author=metadata.get('author'),
            software=software if software else None
        )
        
        doc.close()
        return pdf_meta
    
    def _extract_amounts(self, text: str) -> Dict[str, float]:
        """Extract monetary amounts from OCR text"""
        amounts = {}
        
        # Total patterns
        total_match = re.search(r'(?:Total|Grand Total)[:\s]*[₹Rs.\s]*(\d+[.,]?\d*)', text, re.IGNORECASE)
        if total_match:
            amounts['total'] = float(total_match.group(1).replace(',', ''))
        
        # GST patterns
        gst_match = re.search(r'(?:GST|Tax)[:\s]*[₹Rs.\s]*(\d+[.,]?\d*)', text, re.IGNORECASE)
        if gst_match:
            amounts['gst'] = float(gst_match.group(1).replace(',', ''))
        
        # Subtotal patterns
        subtotal_match = re.search(r'(?:Subtotal|Sub-total)[:\s]*[₹Rs.\s]*(\d+[.,]?\d*)', text, re.IGNORECASE)
        if subtotal_match:
            amounts['subtotal'] = float(subtotal_match.group(1).replace(',', ''))
        
        return amounts


# Singleton instance
forgery_detector = ForgeryDetector()
