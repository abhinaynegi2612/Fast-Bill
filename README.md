# Fast-Bill - Bill Analyzer API

A complete FastAPI-based bill analysis system with forgery detection and intelligent query capabilities.

## System Architecture

```
Bill Analyzer
├── Module 1: Forgery Detection
│   ├── Metadata Analysis (creation date, software)
│   ├── Visual Comparison (pixel-level diff)
│   ├── OCR Consistency (amount verification)
│   ├── Hash Comparison
│   └── Structural Analysis (fonts, pages)
│
└── Module 2: Intelligent Bill Reader
    ├── PDF Parsing (pdfplumber + PyMuPDF)
    ├── OCR (pytesseract for scanned PDFs)
    ├── Command Processing (rule-based NLP)
    └── Data Export (JSON/DataFrame)
```

## Folder Structure

```
Bill Analyzer/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          # All API endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py          # Settings & configuration
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Pydantic models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── bill_parser.py     # PDF extraction
│   │   ├── command_processor.py # NLP commands
│   │   ├── forgery_detector.py # Tampering detection
│   │   └── llm_service.py     # Optional AI
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py         # Utility functions
│   └── __init__.py            # FastAPI app
├── tests/
│   ├── __init__.py
│   └── test_api.py            # Test suite
├── uploads/                   # File storage
├── temp/                      # Temporary files
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
├── .env.example               # Environment template
└── README.md                  # This file
```

## System Dependencies (Required)

This project requires **Python packages** (installed via pip) and **System libraries** (installed separately).

### System Libraries Required

| Library | Purpose | Install Command |
|---------|---------|-----------------|
| **Tesseract OCR** | Text extraction from images | Platform-specific below |
| **Poppler** | PDF to image conversion | Platform-specific below |

### Installation by Platform

#### Windows (using Conda - Recommended)
```bash
# Install both dependencies
conda install -c conda-forge tesseract poppler
```

#### Windows (Manual Installation)
1. **Tesseract**: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - Install and add `C:\Program Files\Tesseract-OCR` to PATH

2. **Poppler**: Download from https://github.com/oschwartz10612/poppler-windows/releases
   - Extract to `C:\poppler\bin` and add to PATH

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils
```

#### macOS
```bash
brew install tesseract poppler
```

### Python Dependencies

```bash
pip install -r requirements.txt
```

## Step-by-Step Implementation

### 2. Run the Application

```bash
# Development mode (with reload)
python main.py

# Or using uvicorn directly
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/upload` | POST | Upload bill PDF |
| `/api/v1/parse/{file_id}` | POST | Parse bill data |
| `/api/v1/query` | POST | Query with natural language |
| `/api/v1/detect-forgery` | POST | Compare original vs suspected |
| `/api/v1/bill/{file_id}/json` | GET | Get raw JSON |
| `/api/v1/bill/{file_id}/dataframe` | GET | Get CSV export |
| `/api/v1/upload/{file_id}` | DELETE | Delete upload |

## Module 2: Intelligent Bill Reader (Command-Based)

### Supported Commands

| Command | Example | Response |
|---------|---------|----------|
| total | "What is the total?" | Total amount with GST |
| gst | "How much GST?" | GST amount and rate |
| smallest_amount | "Smallest item" | Cheapest item |
| largest_amount | "Largest amount" | Most expensive |
| most_expensive_item | "Most expensive item" | Item name + price |
| list_items | "List all items" | Numbered item list |
| item_count | "How many items?" | Total count |
| average_price | "Average price" | Mean item price |
| duplicate_items | "Which items twice?" | Duplicate names |
| summary | "Give me summary" | Full bill summary |

### Example Usage

```bash
# Upload a bill
curl -X POST "http://localhost:8000/api/v1/upload" \
  -F "file=@grocery_bill.pdf"

# Response: {"file_id": "abc123", ...}

# Parse the bill
curl -X POST "http://localhost:8000/api/v1/parse/abc123"

# Query the bill
curl -X POST "http://localhost:8000/api/v1/query" \
  -F "file_id=abc123" \
  -F "command=most expensive item"

# Response: "Most expensive item: Oil – ₹210"
```

## Module 1: Forgery Detection

### Detection Layers

1. **File Hash Comparison**
   - SHA-256 hash of both files
   - Identical files = no tampering

2. **Metadata Analysis**
   - Creation/modification dates
   - Software used (Photoshop = suspicious)
   - Producer/Creator fields

3. **Visual Comparison**
   - Pixel-by-pixel difference
   - Edited region detection
   - Diff percentage calculation

4. **OCR Consistency**
   - Amount value comparison
   - Total/GST/subtotal verification
   - Text extraction validation

5. **Structural Integrity**
   - Page count comparison
   - Font analysis
   - PDF object count

### Example Usage

```bash
# Upload both files
curl -X POST "http://localhost:8000/api/v1/upload" -F "file=@original.pdf"
curl -X POST "http://localhost:8000/api/v1/upload" -F "file=@suspected.pdf"

# Detect forgery
curl -X POST "http://localhost:8000/api/v1/detect-forgery" \
  -F "original_file_id=orig123" \
  -F "suspected_file_id=susp456"
```

### Example Response

```json
{
  "tampered": true,
  "confidence": 87.5,
  "reasons": [
    "Total amount changed: 118.00 → 218.00",
    "Visual inconsistency: 2 edited regions found",
    "Suspicious software detected: photoshop"
  ],
  "checks": [
    {
      "check_name": "File Hash Comparison",
      "passed": false,
      "confidence": 0.0,
      "details": "Files have different content",
      "evidence": {...}
    },
    ...
  ]
}
```

## Bill Parsing Logic

### Extraction Strategy

```python
# Strategy 1: pdfplumber (structured PDFs)
- Extract text and tables
- Parse table rows into BillItem objects
- Extract amounts using regex patterns

# Strategy 2: OCR (scanned/image PDFs)
- Convert PDF to images
- Use Tesseract OCR
- Extract text from images

# Strategy 3: Post-processing
- Remove duplicates
- Validate totals
- Calculate missing fields
```

### Amount Extraction Patterns

```python
AMOUNT_PATTERNS = [
    r'Total[:\s]*[₹Rs.\s]*(\d+[.,]?\d*)',
    r'Grand Total[:\s]*[₹Rs.\s]*(\d+[.,]?\d*)',
    r'GST[:\s]*[₹Rs.\s]*(\d+[.,]?\d*)',
]
```

## Command → Action Mapping

```python
INTENT_PATTERNS = {
    "total": ["total", "grand total", "how much"],
    "gst": ["gst", "tax", "how much gst"],
    "most_expensive": ["most expensive", "costliest", "highest price"],
    ...
}

# Intent detection → Handler execution → Response formatting
```

## Optional LLM Integration

### Setup

```bash
# Add to .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Features

- Enhanced natural language responses
- Forgery explanation generation
- Context-aware answers

### Fallback

If LLM is not configured, system uses template-based responses automatically.

## Testing with Real Bills

### Create Test Bills

```python
# Generate sample PDF for testing
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font('Arial', 'B', 16)
pdf.cell(40, 10, 'Grocery Store')
pdf.ln()
pdf.set_font('Arial', '', 12)
pdf.cell(40, 10, 'Rice - 2 kg - ₹100')
pdf.ln()
pdf.cell(40, 10, 'Oil - 1 ltr - ₹210')
pdf.ln()
pdf.cell(40, 10, 'GST (18%): ₹55.80')
pdf.ln()
pdf.cell(40, 10, 'Total: ₹365.80')
pdf.output('test_bill.pdf')
```

### Test Forgery

1. Create original bill
2. Open in image editor
3. Change an amount (e.g., ₹100 → ₹1000)
4. Save as suspected.pdf
5. Upload both and run detection

## Common Problems + Fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| OCR fails | Tesseract not installed | Install Tesseract + add to PATH |
| PDF won't parse | Corrupted/scanned | Increase OCR DPI |
| Wrong amounts | Poor quality scan | Pre-process images |
| Memory error | Large PDFs | Process page by page |
| CORS error | Frontend origin | Update CORS in config |

## Viva Preparation

### Key Concepts to Explain

1. **Multi-layered Detection**: Explain why we use 5 different checks
2. **False Positive Rate**: Confidence scores and thresholds
3. **OCR vs Text Extraction**: When to use each
4. **Command Pattern Matching**: Rule-based vs LLM
5. **Data Validation**: Post-processing and cleaning

### Architecture Diagram

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Upload    │───▶│   Parse PDF  │───▶│   Extract   │
│   (File)    │    │(pdfplumber/) │    │   (Items)   │
└─────────────┘    └──────────────┘    └─────────────┘
                                              │
                    ┌───────────────────────────┘
                    ▼
            ┌───────────────┐
            │  BillData JSON  │
            │ (Structured)    │
            └───────┬───────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌────────┐  ┌─────────┐  ┌──────────┐
   │Query   │  │Forgery  │  │Export    │
   │(NLP)   │  │Detection│  │(JSON/CSV)│
   └────────┘  └─────────┘  └──────────┘
```

### Code Highlights

- **BillParser**: Multi-strategy extraction with fallback
- **CommandProcessor**: Intent pattern matching
- **ForgeryDetector**: Layered security checks
- **LLMService**: Clean optional AI integration

## Security Considerations

1. **File Validation**: Extension + size checks
2. **Path Sanitization**: Prevent path traversal
3. **Memory Limits**: Prevent DoS from large files
4. **CORS**: Configure for production
5. **Cleanup**: Delete temp files after processing

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

```bash
DEBUG=false
MAX_FILE_SIZE=104857600  # 100MB
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health Check: `http://localhost:8000/api/v1/health`

## License

MIT License - See LICENSE file

## Support

For issues or questions:
- Check Common Problems section
- Review logs in DEBUG mode
- Verify Tesseract installation
