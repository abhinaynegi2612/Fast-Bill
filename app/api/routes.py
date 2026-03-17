"""
API Endpoints - All routes for Bill Analyzer
"""
import uuid
import hashlib
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional
import time

from app.core.config import settings
from app.models.schemas import (
    UploadResponse, BillData, CommandResponse, 
    ForgeryDetectionResponse, ErrorResponse, HealthResponse
)
from app.services.bill_parser import bill_parser
from app.services.command_processor import command_processor
from app.services.forgery_detector import forgery_detector

router = APIRouter()

# In-memory store for uploaded files (use Redis/DB in production)
uploaded_files: dict = {}


@router.get("/favicon.ico")
async def favicon():
    """Return empty response for favicon to prevent 404"""
    return JSONResponse(content={}, status_code=204)


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA-256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()[:16]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services = {
        "bill_parser": "ready",
        "command_processor": "ready",
        "forgery_detector": "ready"
    }
    
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        services=services
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_bill(file: UploadFile = File(...)):
    """
    Upload a bill PDF for analysis
    
    - **file**: PDF file of the bill
    - Returns file_id for subsequent operations
    """
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Generate unique file_id
    file_id = str(uuid.uuid4())[:8]
    safe_filename = f"{file_id}{file_ext}"
    file_path = settings.UPLOAD_DIR / safe_filename
    
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Calculate hash and size
        file_hash = calculate_file_hash(file_path)
        file_size = file_path.stat().st_size
        
        if file_size > settings.MAX_FILE_SIZE:
            file_path.unlink()
            raise HTTPException(status_code=413, detail="File too large")
        
        # Store metadata
        uploaded_files[file_id] = {
            "filename": file.filename,
            "file_path": str(file_path),
            "file_hash": file_hash,
            "file_size": file_size,
            "bill_data": None  # Will be populated on parse
        }
        
        return UploadResponse(
            success=True,
            file_id=file_id,
            filename=file.filename,
            file_path=str(file_path),
            file_size=file_size,
            file_hash=file_hash,
            message="File uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/parse/{file_id}", response_model=BillData)
async def parse_bill(file_id: str):
    """
    Parse uploaded bill and extract structured data
    
    - **file_id**: ID from upload endpoint
    - Returns structured bill data (items, amounts, GST, etc.)
    """
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_info = uploaded_files[file_id]
    file_path = Path(file_info["file_path"])
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File no longer exists")
    
    try:
        # Parse the bill
        bill_data = bill_parser.parse_pdf(file_path)
        
        # Store for command processing
        uploaded_files[file_id]["bill_data"] = bill_data
        
        return bill_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")


@router.post("/query", response_model=CommandResponse)
async def query_bill(file_id: str = Form(...), command: str = Form(...)):
    """
    Query parsed bill with natural language command
    
    **Commands supported:**
    - "total" - Get total amount
    - "gst amount" - Get GST/tax amount
    - "most expensive item" - Find costliest item
    - "list all items" - Show all items
    - "how many items" - Count of items
    - "average price" - Average item price
    - "summary" - Full bill summary
    
    - **file_id**: ID from upload endpoint
    - **command**: Natural language query
    - Returns answer with extracted data
    """
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_info = uploaded_files[file_id]
    
    # Parse if not already done
    if file_info.get("bill_data") is None:
        try:
            bill_data = bill_parser.parse_pdf(Path(file_info["file_path"]))
            file_info["bill_data"] = bill_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse bill: {str(e)}")
    
    bill_data = file_info["bill_data"]
    
    # Load into command processor
    command_processor.load_bill(bill_data)
    
    # Process command
    response = command_processor.process_command(command)
    
    return response


@router.post("/detect-forgery", response_model=ForgeryDetectionResponse)
async def detect_forgery(
    original_file_id: str = Form(...),
    suspected_file_id: str = Form(...)
):
    """
    Detect forgery/tampering by comparing original vs suspected bill
    
    **Checks performed:**
    - File hash comparison
    - Metadata analysis (creation date, software used)
    - Visual comparison (pixel-level diff)
    - OCR consistency (amount changes detection)
    - Structural integrity (fonts, page count)
    
    - **original_file_id**: ID of original bill
    - **suspected_file_id**: ID of bill to check
    - Returns tampering analysis with confidence score
    """
    # Validate both files exist
    if original_file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="Original file not found")
    if suspected_file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="Suspected file not found")
    
    orig_info = uploaded_files[original_file_id]
    susp_info = uploaded_files[suspected_file_id]
    
    orig_path = Path(orig_info["file_path"])
    susp_path = Path(susp_info["file_path"])
    
    if not orig_path.exists() or not susp_path.exists():
        raise HTTPException(status_code=404, detail="One or both files no longer exist")
    
    try:
        # Run forgery detection
        result = forgery_detector.detect(orig_path, susp_path)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forgery detection failed: {str(e)}")


@router.get("/bill/{file_id}/json")
async def get_bill_json(file_id: str):
    """Get bill data as raw JSON"""
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_info = uploaded_files[file_id]
    
    if file_info.get("bill_data") is None:
        raise HTTPException(status_code=400, detail="Bill not parsed yet. Call /parse first.")
    
    return file_info["bill_data"].dict()


@router.get("/bill/{file_id}/dataframe")
async def get_bill_dataframe(file_id: str):
    """Get bill items as CSV (DataFrame export)"""
    import pandas as pd
    from fastapi.responses import StreamingResponse
    import io
    
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_info = uploaded_files[file_id]
    
    if file_info.get("bill_data") is None:
        raise HTTPException(status_code=400, detail="Bill not parsed yet. Call /parse first.")
    
    bill_data = file_info["bill_data"]
    
    if not bill_data.items:
        raise HTTPException(status_code=404, detail="No items found in bill")
    
    # Create DataFrame
    df = pd.DataFrame([
        {
            'Item Name': item.name,
            'Quantity': item.quantity,
            'Unit': item.unit,
            'Price': item.price,
            'Amount': item.amount
        }
        for item in bill_data.items
    ])
    
    # Add summary row
    summary = pd.DataFrame([{
        'Item Name': '--- SUMMARY ---',
        'Quantity': '',
        'Unit': '',
        'Price': '',
        'Amount': ''
    }, {
        'Item Name': 'Subtotal',
        'Quantity': '',
        'Unit': '',
        'Price': '',
        'Amount': bill_data.subtotal
    }, {
        'Item Name': f'GST ({bill_data.gst_rate}%)',
        'Quantity': '',
        'Unit': '',
        'Price': '',
        'Amount': bill_data.gst_amount
    }, {
        'Item Name': 'Total',
        'Quantity': '',
        'Unit': '',
        'Price': '',
        'Amount': bill_data.total_amount
    }])
    
    df = pd.concat([df, summary], ignore_index=True)
    
    # Convert to CSV
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=bill_{file_id}.csv"}
    )


@router.delete("/upload/{file_id}")
async def delete_upload(file_id: str):
    """Delete uploaded file"""
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_info = uploaded_files[file_id]
    file_path = Path(file_info["file_path"])
    
    if file_path.exists():
        file_path.unlink()
    
    del uploaded_files[file_id]
    
    return {"message": "File deleted successfully"}
