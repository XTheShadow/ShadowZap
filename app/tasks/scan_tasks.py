# This file is for handling the Celery tasks.
from ..services.celery_service import Celery #Importing the Celery class from the services folder(.. means 2 directories up)
from pydantic import AnyHttpUrl
from ..api.scan import ScanType


@celery.task
def run_scan(target_url: AnyHttpUrl, scan_type: ScanType):
    return{
        "status": "Completed!",
        "target": target_url,
        "Scan_type": scan_type,
    }
