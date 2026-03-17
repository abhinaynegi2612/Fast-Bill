"""
Pydantic Models for API Request/Response
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class CommandType(str, Enum):
    """Supported command types for bill analysis"""
    TOTAL = "total"
    GST = "gst"
    SMALLEST_AMOUNT = "smallest_amount"
    LARGEST_AMOUNT = "largest_amount"
    MOST_EXPENSIVE_ITEM = "most_expensive_item"
    LEAST_EXPENSIVE_ITEM = "least_expensive_item"
    HIGHEST_QUANTITY = "highest_quantity"
    LIST_ITEMS = "list_items"
    ITEM_COUNT = "item_count"
    AVERAGE_PRICE = "average_price"
    FIND_ITEM = "find_item"
    DUPLICATE_ITEMS = "duplicate_items"
    SUMMARY = "summary"
    CUSTOM = "custom"


class BillItem(BaseModel):
    """Individual bill item"""
    name: str
    quantity: float = 1.0
    unit: str = "pcs"
    price: float
    amount: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Rice",
                "quantity": 2,
                "unit": "kg",
                "price": 50.0,
                "amount": 100.0
            }
        }


class BillData(BaseModel):
    """Structured bill data"""
    vendor_name: Optional[str] = None
    bill_number: Optional[str] = None
    bill_date: Optional[str] = None
    items: List[BillItem] = []
    subtotal: float = 0.0
    gst_amount: float = 0.0
    gst_rate: Optional[float] = None
    total_amount: float = 0.0
    currency: str = "INR"
    raw_text: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "vendor_name": "Grocery Store",
                "bill_number": "B001",
                "bill_date": "2024-01-15",
                "items": [
                    {"name": "Rice", "quantity": 2, "unit": "kg", "price": 50.0, "amount": 100.0}
                ],
                "subtotal": 100.0,
                "gst_amount": 18.0,
                "gst_rate": 18.0,
                "total_amount": 118.0,
                "currency": "INR"
            }
        }


class ForgeryCheck(BaseModel):
    """Individual forgery check result"""
    check_name: str
    passed: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: str
    evidence: Optional[Dict[str, Any]] = None


class ForgeryDetectionResponse(BaseModel):
    """Response for forgery detection"""
    tampered: bool
    confidence: float = Field(..., ge=0.0, le=100.0)
    reasons: List[str] = []
    checks: List[ForgeryCheck] = []
    original_metadata: Optional[Dict[str, Any]] = None
    suspected_metadata: Optional[Dict[str, Any]] = None
    visual_diff_path: Optional[str] = None
    processing_time_ms: int = 0
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class CommandResponse(BaseModel):
    """Response for command-based queries"""
    command: str
    intent: str
    answer: str
    data: Optional[Dict[str, Any]] = None
    bill_summary: Optional[BillData] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: int = 0
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class UploadResponse(BaseModel):
    """File upload response"""
    success: bool
    file_id: str
    filename: str
    file_path: str
    file_size: int
    file_hash: str
    message: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = {}
