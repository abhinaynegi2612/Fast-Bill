# Bill Analyzer - Learning Roadmap

## 🎯 Project Overview
A **FastAPI-based system** that analyzes bills with two main modules:
1. **Forgery Detection** - Detects tampering in PDF bills
2. **Intelligent Bill Reader** - Extracts and queries bill data

---

## 📚 Learning Path (Follow in Order)

### 1. **Core Architecture** (Start Here)
**File**: `README.md` (Lines 5-21)
**What to Learn**:
- Two-module system design
- How modules interact
- Data flow from upload → analysis → response

**Key Concepts**:
```
Upload → Parse → Extract → Analyze → Query
```

### 2. **Project Structure** 
**File**: `README.md` (Lines 23-56)
**What to Learn**:
- FastAPI project organization
- MVC pattern with services layer
- Separation of concerns

**Important Files**:
- `main.py` - Entry point
- `app/api/routes.py` - API endpoints
- `app/services/` - Business logic
- `app/models/schemas.py` - Data models

### 3. **System Dependencies**
**File**: `README.md` (Lines 58-99)
**What to Learn**:
- Why Tesseract OCR is needed (text extraction)
- Why Poppler is needed (PDF → image conversion)
- Python packages and their purposes

**Key Dependencies**:
- `pdfplumber` - Extract text from PDFs
- `pytesseract` - OCR for scanned PDFs
- `PyMuPDF` - PDF manipulation
- `FastAPI` - Web framework

### 4. **API Endpoints**
**File**: `README.md` (Lines 116-128)
**What to Learn**:
- RESTful API design
- File upload handling
- CRUD operations on bills

**Core Flow**:
1. `POST /upload` - Upload PDF
2. `POST /parse/{file_id}` - Extract data
3. `POST /query` - Ask questions
4. `POST /detect-forgery` - Compare bills

### 5. **Module 2: Bill Reader** (Easier First)
**File**: `README.md` (Lines 129-164)
**What to Study**:
- Natural language command processing
- Pattern matching for intents
- Response generation

**Code to Read**:
```python
# app/services/command_processor.py
class CommandProcessor:
    - INTENT_PATTERNS (how commands are matched)
    - _detect_intent() (pattern matching logic)
    - _handle_*() methods (data extraction)
```

**Example Flow**:
```
User: "most expensive item"
↓
Pattern matches: r'most\s*expensive\s*item'
↓
Handler: _handle_most_expensive()
↓
Find max amount in items
↓
Response: "Most expensive item: Oil – ₹210"
```

### 6. **Bill Parsing Logic**
**File**: `README.md` (Lines 231-270)
**What to Study**:
- Multi-strategy PDF parsing
- Regex patterns for amount extraction
- OCR fallback for scanned PDFs

**Code to Read**:
```python
# app/services/bill_parser.py
class BillParser:
    - _parse_with_pdfplumber() (structured PDFs)
    - _parse_with_ocr() (scanned PDFs)
    - AMOUNT_PATTERNS (regex for totals/GST)
    - _post_process() (data validation)
```

### 7. **Module 1: Forgery Detection** (Advanced)
**File**: `README.md` (Lines 166-229)
**What to Study**:
- 5-layer detection system
- Hash comparison
- Metadata analysis
- Visual diff
- OCR consistency
- Structural integrity

**Code to Read**:
```python
# app/services/forgery_detector.py
class ForgeryDetector:
    - detect() (main orchestrator)
    - _check_hash() (file comparison)
    - _check_metadata() (creation dates, software)
    - _check_visual() (pixel differences)
    - _check_ocr_consistency() (amount verification)
```

### 8. **Data Models**
**File**: `app/models/schemas.py`
**What to Learn**:
- Pydantic models for validation
- Data structures used throughout
- Type hints and validation

**Key Models**:
- `BillData` - Structured bill information
- `BillItem` - Individual line items
- `CommandType` - Enum for query types
- `ForgeryDetectionResponse` - Detection results

### 9. **API Routes**
**File**: `app/api/routes.py`
**What to Learn**:
- FastAPI endpoint definitions
- File upload handling
- Error handling
- Response formatting

### 10. **Configuration**
**File**: `app/core/config.py`
**What to Learn**:
- Settings management
- Environment variables
- Path configuration
- Tesseract path setup

---

## 🔍 Deep Dive Topics

### Bill Parsing Challenges
1. **Multiple PDF Formats**: Structured vs Scanned
2. **Amount Extraction**: Various currency formats
3. **GST Calculation**: Different tax structures
4. **Item Recognition**: Table vs line-item formats

### Forgery Detection Techniques
1. **Hash Comparison**: Basic file identity
2. **Metadata Analysis**: Creation tools, dates
3. **Visual Diff**: Pixel-level changes
4. **OCR Consistency**: Amount tampering detection
5. **Structural Analysis**: Font/page changes

### Command Processing
1. **Pattern Matching**: Regex for intent detection
2. **Fallback Handling**: Unknown commands
3. **Data Extraction**: Pandas operations
4. **Response Formatting**: Natural language generation

---

## 🛠️ Implementation Details to Study

### 1. Error Handling
```python
# Graceful degradation when dependencies missing
try:
    import pytesseract
except ImportError:
    logger.warning("Tesseract not available")
```

### 2. Multi-Strategy Approach
```python
# Try pdfplumber first, fallback to OCR
if text := self._parse_with_pdfplumber(pdf_path):
    return text
else:
    return self._parse_with_ocr(pdf_path)
```

### 3. Pattern Matching
```python
# Flexible command recognition
INTENT_PATTERNS = {
    CommandType.TOTAL: [
        r'total\s*(?:amount|bill|price)?',
        r'grand\s*total',
        r'how\s*much\s*did\s*i\s*(?:pay|spend)',
    ]
}
```

### 4. Confidence Scoring
```python
# Forgery detection confidence
confidence = (passed_checks / total_checks) * 100
```

---

## 🧪 Testing Your Understanding

### 1. Add a New Command
Add support for "show me items above ₹100"
- Add pattern to `INTENT_PATTERNS`
- Create `_handle_expensive_items()` method
- Test with sample bill

### 2. Improve Forgery Detection
Add font analysis to detect text replacement
- Extract font information from PDF
- Compare font families between files
- Flag suspicious font changes

### 3. Handle New Bill Format
Add support for restaurant bills with table numbers
- Update `AMOUNT_PATTERNS` regex
- Add table number extraction
- Test with restaurant PDF

---

## 📖 Key Files to Master

| Priority | File | Purpose |
|----------|------|---------|
| 1 | `app/services/command_processor.py` | NLP queries (easiest) |
| 2 | `app/services/bill_parser.py` | PDF extraction |
| 3 | `app/services/forgery_detector.py` | Tampering detection |
| 4 | `app/api/routes.py` | API endpoints |
| 5 | `app/models/schemas.py` | Data structures |
| 6 | `app/core/config.py` | Configuration |

---

## 🎯 Quick Start Guide

1. **Run the app**: `python main.py`
2. **Upload a bill**: Use Swagger UI at `http://localhost:8000/docs`
3. **Parse it**: Call `/parse/{file_id}`
4. **Query it**: Try commands like "total", "most expensive", "summary"
5. **Test forgery**: Upload two bills and compare

---

## 💡 Pro Tips

1. **Start with Module 2** (Bill Reader) - it's simpler
2. **Use the dashboard** to understand the UI flow
3. **Check logs** to see internal processing
4. **Test with different bill formats** to understand edge cases
5. **Read the regex patterns** to see how data extraction works

---

## 🔗 External Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **pdfplumber**: https://github.com/jsvine/pdfplumber
- **PyMuPDF**: https://pymupdf.readthedocs.io/
- **Tesseract OCR**: https://github.com/tesseract-ocr/tesseract
- **Pydantic**: https://pydantic-docs.helpmanual.io/

---

## ✅ Checklist for Mastery

- [ ] Understand the two-module architecture
- [ ] Can explain the bill parsing flow
- [ ] Know how command patterns work
- [ ] Understand all 5 forgery detection layers
- [ ] Can add new query commands
- [ ] Know how to handle different PDF formats
- [ ] Understand the API structure
- [ ] Can troubleshoot common issues
- [ ] Know the purpose of each dependency
- [ ] Can explain the data models

Master these topics and you'll have a complete understanding of the Bill Analyzer project!
