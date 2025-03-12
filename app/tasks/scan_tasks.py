# This file is for handling the Celery tasks.
from ..services.celery_service import celery # Importing the celery instance from celery_service
from pydantic import AnyHttpUrl
from ..models.scan_model import ScanType

@celery.task
def run_scan(target_url: AnyHttpUrl, scan_type: ScanType):
    return{
        "status": "Completed!",
        "target": target_url,
        "Scan_type": scan_type,
    }
