"""
Test suite for Bill Analyzer
"""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import io

from app import app

client = TestClient(app)


class TestHealth:
    """Test health check endpoint"""
    
    def test_health_check(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data


class TestUpload:
    """Test file upload functionality"""
    
    def test_upload_valid_pdf(self):
        # Create a minimal PDF file for testing
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF"
        
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "file_id" in data
        assert data["filename"] == "test.pdf"
    
    def test_upload_invalid_extension(self):
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.txt", io.BytesIO(b"test"), "text/plain")}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


class TestCommands:
    """Test command processing"""
    
    def test_command_total(self):
        # This would need a pre-uploaded file
        # Simplified test - real tests would use fixtures
        pass
    
    def test_command_invalid_file(self):
        response = client.post(
            "/api/v1/query",
            data={"file_id": "invalid_id", "command": "total"}
        )
        
        assert response.status_code == 404


class TestForgeryDetection:
    """Test forgery detection"""
    
    def test_forgery_missing_files(self):
        response = client.post(
            "/api/v1/detect-forgery",
            data={
                "original_file_id": "nonexistent",
                "suspected_file_id": "nonexistent"
            }
        )
        
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
