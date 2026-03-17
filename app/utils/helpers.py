"""
Utility functions for Bill Analyzer
"""
import re
from typing import Optional
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove path traversal and special chars
    sanitized = re.sub(r'[^\w\s.-]', '', filename)
    sanitized = re.sub(r'\s+', '_', sanitized)
    return sanitized[:100]  # Limit length


def format_currency(amount: float, currency: str = "INR") -> str:
    """Format amount with currency symbol"""
    symbols = {
        "INR": "₹",
        "USD": "$",
        "EUR": "€",
        "GBP": "£"
    }
    symbol = symbols.get(currency, currency)
    return f"{symbol}{amount:,.2f}"


def validate_pdf(file_path: Path) -> bool:
    """Validate if file is a valid PDF"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
            return header == b'%PDF'
    except Exception:
        return False


def extract_file_info(file_path: Path) -> dict:
    """Extract basic file information"""
    stat = file_path.stat()
    return {
        "name": file_path.name,
        "size": stat.st_size,
        "created": stat.st_ctime,
        "modified": stat.st_mtime
    }


def chunk_list(lst: list, chunk_size: int):
    """Split list into chunks"""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def safe_float(value, default: float = 0.0) -> float:
    """Safely convert value to float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
