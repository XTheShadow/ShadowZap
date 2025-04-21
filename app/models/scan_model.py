from pydantic import BaseModel, AnyHttpUrl, validator # This library is used to validate the incoming data
from enum import Enum          # A python special class that represents a fixed set of values or options

# A class defining the fixed terms or options so no invalid terms are used
class ScanType(Enum):
    BASIC = "basic"
    FULL = "full"
    API_SCAN = "api_scan"
    SPIDER_SCAN = "spider_scan"

# Creating a class to validate the incoming data
class ScanRequest(BaseModel):
    target_url: AnyHttpUrl      # Changed the type to be URL to ensure valid urls only
    scan_type: ScanType = ScanType.BASIC  # Changed to use the "ScanType" class so there is no invalid entries
    ports: str = "1-1000"   # Defining the default port range
    timeout: int = 60       # Defining a timout after 60 seconds of no response

    @validator('target_url') #This decorator is used to validate the incoming url
    def normalize_url(cls, v): # This is a method to normalize the url, cls is used to access the class itself and v is the value(URL)
        return str(v).rstrip('/') # This removes any trailing slashes from the url