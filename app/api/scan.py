from fastapi import FastAPI
import uvicorn
from ..tasks.scan_tasks import run_scan # Importing the run_scan function from the scan_tasks.py file
from ..models.scan_model import ScanRequest # Importing the ScanRequest class from the scan_model.py file

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
    
    task = run_scan.delay(
        str(scan_request.target_url), # Here the target_url is converted to a string for celery
        scan_request.scan_type.value,  # This is to get the scan type value from the ScanType class(Enum)
        scan_request.report_type.value,  # This is to get the report type value from the ReportType class(Enum)
        scan_request.report_format.value  # To get the report format value from the ReportFormat class(Enum)
    )
    
    return{
        "status": "Scan initiated",
        "task_id": str(task.id), # returning the task id for better tracking
        "target": scan_request.target_url,  # Accessing the target_url from the scan_request object
        "scan_type": scan_request.scan_type  # Accessing the scan_type from the scan_request object
    }



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)