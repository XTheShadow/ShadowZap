from pydantic import BaseModel, AnyHttpUrl, validator, Field
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

# A class defining the fixed terms or options so no invalid terms are used
class ScanType(str, Enum):
    BASIC = "basic"
    FULL = "full"
    API_SCAN = "api_scan"
    SPIDER_SCAN = "spider_scan"
    
# Report type options
class ReportType(str, Enum): # Added str to the class to ensure that the report type is a string and Enum to ensure that the report type is one of the options
    NORMAL = "normal"
    ENHANCED = "enhanced"
    

# Report format options
class ReportFormat(str, Enum):
    PDF = "pdf"
    HTML = "html"
    XML = "xml"
    JSON = "json"
    MARKDOWN = "markdown"


# This is the model for the scan
class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Creating a class to validate the incoming data
class ScanRequest(BaseModel):
    target_url: AnyHttpUrl      # Changed the type to be URL to ensure valid urls only
    scan_type: ScanType = ScanType.BASIC  # Changed to use the "ScanType" class so there is no invalid entries
    ports: str = "1-1000"   # Defining the default port range
    timeout: int = 60       # Defining a timout after 60 seconds of no response
    report_type: ReportType = ReportType.ENHANCED  # Type of report (normal or enhanced with AI analysis)
    report_format: ReportFormat = ReportFormat.HTML  # Format of the report (HTML, XML, or JSON)

    @validator('target_url') #This decorator is used to validate the incoming url
    def normalize_url(cls, v): # This is a method to normalize the url, cls is used to access the class itself and v is the value(URL)
        return str(v).rstrip('/') # This removes any trailing slashes from the url


# This is the model for the vulnerability count in the database
class VulnerabilityCount(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


# This is the model for creating a new scan in the database
class ScanCreate(BaseModel):
    """Model for creating a new scan"""
    target_url: AnyHttpUrl
    scan_type: ScanType
    ports_scanned: str = "1-1000"
    report_type: ReportType
    report_format: ReportFormat


# This is the model for updating an existing scan in the database
class ScanUpdate(BaseModel):
    """Model for updating an existing scan"""
    status: Optional[ScanStatus] = None
    duration: Optional[int] = None
    vulnerability_count: Optional[Dict[str, int]] = None


# This is the model for the scan in the database
class Scan(BaseModel):
    
    scan_id: str
    target_url: str
    scan_type: str
    status: str
    timestamp: datetime
    duration: int
    ports_scanned: str
    report_type: str
    report_format: str
    vulnerability_count: Dict[str, int]

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

    @validator('status')
    def validate_status(cls, v):
        if v not in [item.value for item in ScanStatus]:
            raise ValueError(f"Invalid status: {v}")
        return v