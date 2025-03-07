from fastapi.testclient import TestClient
from app.api.scan import app
import pytest
import httpx


client = TestClient(app)

def test_scan_endpoint():
    # Test data
    test_data = {
        "tartget_url": "https://example.com",
        "scan_type": "basic"
    }
    
    # Send POST request to /scan endpoint
    response = client.post("/scan", json=test_data)
    
    # Assert response status code is 200 (Assert checks if the condition is true)
    assert response.status_code == 200
    
    # Assert response contains expected data
    data = response.json()
    assert data["status"] == "Scan initiated"
    assert data["target"] == test_data["tartget_url"]
    assert data["scan_type"] == test_data["scan_type"]

# A function to test the default case 
def test_scan_endpoint_default_scan_type():
    # Test data with only target URL(The default case)
    test_data = {
        "tartget_url": "https://example.com"
    }
    
    # Send POST request to /scan endpoint
    response = client.post("/scan", json=test_data)
    
    # Assert response status code is 200
    assert response.status_code == 200
    
    # Assert response contains expected data with default scan type
    data = response.json()
    assert data["status"] == "Scan initiated"
    assert data["target"] == test_data["tartget_url"]
    assert data["scan_type"] == "basic"  # Default value from ScanRequest class