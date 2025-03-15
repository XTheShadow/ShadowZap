# This file is for handling the Celery tasks.
from ..services.celery_service import celery # Importing the celery instance from celery_service
from pydantic import AnyHttpUrl
from ..models.scan_model import ScanType
import docker

@celery.task
def run_scan(target_url: AnyHttpUrl, scan_type: ScanType):

    client = docker.from_env()
    if scan_type == "basic":
        try:
            # Run the OWASP ZAP container with baseline scan
            container = client.containers.run(
                'owasp-zap2docker-stable',  # The official docker image for OWASP ZAP
                f'zap-baseline.py -t {target_url}',  # The command used to run basic scan on target URL
                detach=True,  # To make the container runs in background
                volumes={'/reports/outputs': {'bind': '/zap/wrk', 'mode': 'rw'}}  # This mounts reports directory
            )

            # Wait for scan to complete and get results
            result = container.wait()
            logs = container.logs().decode('utf-8')

            # Processing the scan results
            scan_status = "Completed" if result["StatusCode"] == 0 else "Failed"
            scan_output = {
                "status": scan_status,
                "target": target_url,
                "scan_type": scan_type,
                "exit_code": result["StatusCode"],
                "logs": logs
            }

            # Removing container after scan
            container.remove()

            return scan_output

        except Exception as e:
            return {
                "status": "Failed",
                "target": target_url,
                "scan_type": scan_type,
                "error": str(e)
            }

    return {
        "status": "Invalid scan type",
        "target": target_url,
        "scan_type": scan_type
    }
