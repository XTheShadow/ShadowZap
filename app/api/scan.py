from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel # This library is used to validate the incoming data
from enum import Enum          # A python special class that represents a fixed set of values or options

# A class defining the fixed terms or options so no invalid terms are used
class ScanType(Enum):
    BASIC = "basic"
    FULL = "full"
    PORT_SCAN = "port_scan"
    VULNERABILITY = "vulnerability"


# Creating a class to validate the incoming data
class ScanRequest(BaseModel):
    tartget_url: str  # Defining the type of the url data
    scan_type: str = "basic"  # Also the scan type being a string but setting the default type to "basic"

# Setting the application
app = FastAPI()

# Testing api
@app.get("/")
def test():
    return "The API is working"


# Endpoint to start a new scan
@app.post("/scan")
# Async functions are used for coroutines so it can be suspended and resumed
async def start_Scan(scan_request: ScanRequest): # An object "scan_request" from the "ScanRequest" class was created
    return{
        "status": "Scan initiated",
        "target": scan_request.tartget_url,  # Accessing the tartget_url from the scan_request object
        "scan_type": scan_request.scan_type  # Accessing the scan_type from the scan_request object
    }



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)